//! SynthesisEngine end-to-end, backend-agnostic: 7 ID → mel → vocoder → iSTFT → WAV.

use std::collections::HashMap;

use vifasttts_audio as audio;
use vifasttts_text::chunking::{
    STEADY_PAUSE_COMMA, STEADY_PAUSE_DEFAULT, STEADY_PAUSE_PERIOD, chunk_text, pause_seconds,
    split_clauses, steady_pause_seconds,
};
use vifasttts_text::dialect::Dialect;
use vifasttts_text::karaoke::{KaraokeDocument, TimedUnit, UnitKind};
use vifasttts_text::pipeline::{ParseOptions, live_parse_options, parse_text};
use vifasttts_text::types::ParsedSyllable;
use vifasttts_text::vocab::ComponentVocabs;

use vifasttts_ports::{
    AcousticModel, AcousticResult, ComplexSpectrogram, MelSpectrogram, ModelInfo, VocoderModel,
};

#[derive(Clone, Debug)]
pub struct SynthesisOptions {
    pub speed: f32,
    pub fixed_pauses: bool,
    pub alpha: f32,
    pub max_chars: usize,
    pub peak_normalize: bool,
    pub gate_threshold: f32,
    pub pause_comma: f64,
    pub pause_period: f64,
    pub pause_default: f64,
    pub parse: ParseOptions,
}

impl Default for SynthesisOptions {
    fn default() -> Self {
        Self {
            speed: 1.0,
            fixed_pauses: false,
            alpha: 1.5,
            max_chars: 300,
            peak_normalize: false,
            gate_threshold: 0.5,
            pause_comma: STEADY_PAUSE_COMMA,
            pause_period: STEADY_PAUSE_PERIOD,
            pause_default: STEADY_PAUSE_DEFAULT,
            // API mặc định dùng đúng profile production, không phải parser trần.
            parse: live_parse_options(Dialect::North, None, None),
        }
    }
}

#[derive(Clone, Debug)]
pub struct SynthesisResult {
    pub wav: Vec<u8>,
    pub waveform: Vec<f32>,
    pub sample_rate: u32,
    /// `None` nếu model không xuất timing hoặc synthesize từ ID.
    pub karaoke: Option<KaraokeDocument>,
}

struct RenderedChunk {
    audio: Vec<f32>,
    units: Vec<TimedUnit>,
}

/// `slot_durations` = lead + 5 slot/âm tiết (O, M, N, C, G).
/// Trả timing theo sample của audio đã render (đã trim center iSTFT).
pub fn timed_units_from_slots(
    items: &[ParsedSyllable],
    slots: &[i64],
    hop_length: usize,
    sample_rate: u32,
    audio_samples: usize,
    sample_offset: usize,
) -> Vec<TimedUnit> {
    if items.is_empty() || slots.len() != 1 + 5 * items.len() || sample_rate == 0 {
        return Vec::new();
    }
    let hop = hop_length as u64;
    let rate = sample_rate as u64;
    let offset = sample_offset as u64;
    let limit = offset + audio_samples as u64;
    let mut cursor = slots[0].max(0) as u64;
    let mut units = Vec::with_capacity(items.len());
    for (index, item) in items.iter().enumerate() {
        let base = 1 + 5 * index;
        let voiced: u64 = slots[base..base + 4]
            .iter()
            .map(|value| (*value).max(0) as u64)
            .sum();
        let gap = slots[base + 4].max(0) as u64;
        let start_sample = (offset + cursor * hop).min(limit);
        let end_sample = (offset + (cursor + voiced) * hop).min(limit);
        cursor = cursor + voiced + gap;
        if end_sample <= start_sample {
            continue;
        }
        let text = if item.raw.is_empty() {
            item.normalized.clone()
        } else {
            item.raw.clone()
        };
        units.push(TimedUnit {
            text,
            start_ms: start_sample * 1000 / rate,
            end_ms: end_sample * 1000 / rate,
            kind: UnitKind::Syllable,
            punctuation: item.punctuation.clone(),
            sentence_end: item.boundaries.sentence_end,
            phrase_end: item.boundaries.phrase_end,
        });
    }
    units
}

/// Một chunk đã parse/encode, sẵn sàng gọi backend.
#[derive(Clone, Debug)]
pub struct SynthesisChunk {
    pub text: String,
    pub items: Vec<ParsedSyllable>,
    pub features: Vec<[i64; 7]>,
    pub gate: f32,
    pub pause_seconds: f64,
}

/// Lập kế hoạch synth dùng chung native/browser: chunk → parse → features.
pub struct SynthesisPlan {
    chunks: Vec<String>,
    options: SynthesisOptions,
    index: usize,
}

impl SynthesisPlan {
    pub fn new(text: &str, options: &SynthesisOptions) -> Result<Self, String> {
        let chunks = if options.fixed_pauses {
            split_clauses(text, options.max_chars)?
        } else {
            chunk_text(text, options.max_chars)?
        };
        if chunks.is_empty() {
            return Err("Không có nội dung để đọc".to_string());
        }
        Ok(Self {
            chunks,
            options: options.clone(),
            index: 0,
        })
    }

    pub fn next_chunk(&mut self) -> Result<Option<SynthesisChunk>, String> {
        let vocabs = ComponentVocabs::default();
        while self.index < self.chunks.len() {
            let index = self.index;
            self.index += 1;
            let text = self.chunks[index].clone();
            let items = parse_text(&text, &self.options.parse);
            if items.is_empty() {
                continue;
            }
            let features: Vec<[i64; 7]> = items
                .iter()
                .map(|item| vocabs.encode(item).map(|id| id as i64))
                .collect();
            let gate = if self.options.fixed_pauses {
                1.01
            } else {
                self.options.gate_threshold
            };
            let pause_seconds = if index + 1 < self.chunks.len() {
                if self.options.fixed_pauses {
                    steady_pause_seconds(
                        &text,
                        self.options.pause_comma,
                        self.options.pause_period,
                        self.options.pause_default,
                    )
                } else {
                    pause_seconds(&text)
                }
            } else {
                0.0
            };
            return Ok(Some(SynthesisChunk {
                text,
                items,
                features,
                gate,
                pause_seconds,
            }));
        }
        Ok(None)
    }
}

/// Gom audio/timing dùng chung native/browser.
pub struct SynthesisAssembler {
    options: SynthesisOptions,
    sample_rate: u32,
    hop_length: usize,
    pieces: Vec<f32>,
    units: Vec<TimedUnit>,
    cursor: usize,
}

impl SynthesisAssembler {
    pub fn new(sample_rate: u32, hop_length: usize, options: SynthesisOptions) -> Self {
        Self {
            options,
            sample_rate,
            hop_length,
            pieces: Vec::new(),
            units: Vec::new(),
            cursor: 0,
        }
    }

    pub fn push_chunk(&mut self, audio: &[f32], items: &[ParsedSyllable], slots: Option<&[i64]>) {
        let offset = self.cursor;
        if let Some(slots) = slots {
            self.units.extend(timed_units_from_slots(
                items,
                slots,
                self.hop_length,
                self.sample_rate,
                audio.len(),
                offset,
            ));
        }
        self.pieces.extend_from_slice(audio);
        self.cursor += audio.len();
    }

    pub fn push_pause(&mut self, seconds: f64) {
        if seconds <= 0.0 || self.sample_rate == 0 {
            return;
        }
        let samples = (self.sample_rate as f64 * seconds) as usize;
        if samples == 0 {
            return;
        }
        self.pieces.extend(std::iter::repeat_n(0.0, samples));
        self.cursor += samples;
    }

    pub fn finish(self) -> Result<SynthesisResult, String> {
        if self.pieces.is_empty() {
            return Err("Không có âm thanh nào được tạo".to_string());
        }
        let waveform = audio::postprocess(
            &self.pieces,
            self.sample_rate as usize,
            if self.options.peak_normalize {
                Some(-3.0)
            } else {
                None
            },
        );
        let duration_ms = (waveform.len() as u64) * 1000 / self.sample_rate.max(1) as u64;
        let karaoke = if self.units.is_empty() {
            None
        } else {
            Some(KaraokeDocument::from_units(
                self.units,
                self.sample_rate,
                duration_ms,
                80,
            ))
        };
        Ok(SynthesisResult {
            wav: audio::wav_bytes(&waveform, self.sample_rate),
            waveform,
            sample_rate: self.sample_rate,
            karaoke,
        })
    }
}

pub struct SynthesisEngine<A: AcousticModel, V: VocoderModel> {
    pub acoustic: A,
    pub vocoder: V,
    pub info: ModelInfo,
}

impl<A: AcousticModel, V: VocoderModel> SynthesisEngine<A, V> {
    pub fn new(acoustic: A, vocoder: V, info: ModelInfo) -> Self {
        Self {
            acoustic,
            vocoder,
            info,
        }
    }

    async fn run_acoustic(
        &mut self,
        features: &[[i64; 7]],
        speed: f32,
        gate: f32,
    ) -> Result<AcousticResult, String> {
        if features.is_empty() {
            return Err("không có âm tiết".to_string());
        }
        self.acoustic.run(features, speed, gate).await
    }

    async fn run_vocoder(&mut self, mel: &MelSpectrogram) -> Result<ComplexSpectrogram, String> {
        self.vocoder.spectrogram(mel).await
    }

    /// MelSpectrogram → waveform **chưa** postprocess (fade/peak chỉ áp một lần ở cuối).
    async fn mel_to_waveform(
        &mut self,
        mel: &MelSpectrogram,
        alpha: f32,
    ) -> Result<(Vec<f32>, u32), String> {
        let sharp = audio::sharpen_mel(&mel.data, mel.frames, mel.mels, alpha);
        let sharp_mel = MelSpectrogram {
            data: sharp,
            frames: mel.frames,
            mels: mel.mels,
        };
        let spec = self.run_vocoder(&sharp_mel).await?;
        let waveform = audio::istft(
            &spec.real,
            &spec.imag,
            spec.bins,
            spec.frames,
            self.info.n_fft,
            self.info.hop_length,
            None,
            true,
        )?;
        Ok((waveform, self.info.sample_rate))
    }

    async fn render_chunk(
        &mut self,
        chunk: &str,
        options: &SynthesisOptions,
        sample_offset: usize,
    ) -> Result<RenderedChunk, String> {
        let vocabs = ComponentVocabs::default();
        let items = parse_text(chunk, &options.parse);
        if items.is_empty() {
            return Ok(RenderedChunk {
                audio: Vec::new(),
                units: Vec::new(),
            });
        }
        let features: Vec<[i64; 7]> = items
            .iter()
            .map(|item| vocabs.encode(item).map(|id| id as i64))
            .collect();
        let gate = if options.fixed_pauses {
            1.01
        } else {
            options.gate_threshold
        };
        let output = self.run_acoustic(&features, options.speed, gate).await?;
        let (audio, _) = self.mel_to_waveform(&output.mel, options.alpha).await?;
        let units = output
            .slot_durations
            .as_deref()
            .map(|slots| {
                timed_units_from_slots(
                    &items,
                    slots,
                    self.info.hop_length,
                    self.info.sample_rate,
                    audio.len(),
                    sample_offset,
                )
            })
            .unwrap_or_default();
        Ok(RenderedChunk { audio, units })
    }

    fn pause_for(&self, chunk: &str, options: &SynthesisOptions) -> usize {
        let seconds = if options.fixed_pauses {
            steady_pause_seconds(
                chunk,
                options.pause_comma,
                options.pause_period,
                options.pause_default,
            )
        } else {
            pause_seconds(chunk)
        };
        (self.info.sample_rate as f64 * seconds) as usize
    }

    /// MelSpectrogram thô từ 7 ID (debug/parity).
    pub async fn acoustic_mel(
        &mut self,
        features: &[[i64; 7]],
        speed: f32,
        gate: f32,
    ) -> Result<MelSpectrogram, String> {
        self.run_acoustic(features, speed, gate)
            .await
            .map(|output| output.mel)
    }

    /// Tổng hợp từ 7 ID đã tính (dùng cho parity/Phase 1).
    pub async fn synthesize_ids(
        &mut self,
        features: &[[i64; 7]],
        speed: f32,
        gate: f32,
        alpha: f32,
        peak_normalize: bool,
    ) -> Result<SynthesisResult, String> {
        let mel = self.run_acoustic(features, speed, gate).await?.mel;
        let (raw, sample_rate) = self.mel_to_waveform(&mel, alpha).await?;
        let waveform = audio::postprocess(
            &raw,
            sample_rate as usize,
            if peak_normalize { Some(-3.0) } else { None },
        );
        Ok(SynthesisResult {
            wav: audio::wav_bytes(&waveform, sample_rate),
            waveform,
            sample_rate,
            karaoke: None,
        })
    }

    pub async fn synthesize(
        &mut self,
        text: &str,
        options: &SynthesisOptions,
    ) -> Result<SynthesisResult, String> {
        let mut plan = SynthesisPlan::new(text, options)?;
        let mut assembler =
            SynthesisAssembler::new(self.info.sample_rate, self.info.hop_length, options.clone());
        while let Some(chunk) = plan.next_chunk()? {
            let output = self
                .run_acoustic(&chunk.features, options.speed, chunk.gate)
                .await?;
            let (audio_samples, _) = self.mel_to_waveform(&output.mel, options.alpha).await?;
            assembler.push_chunk(
                &audio_samples,
                &chunk.items,
                output.slot_durations.as_deref(),
            );
            assembler.push_pause(chunk.pause_seconds);
        }
        assembler.finish()
    }
}

/// Helper cho test/CLI: override map đơn giản.
pub fn with_overrides(
    mut options: SynthesisOptions,
    overrides: HashMap<String, String>,
) -> SynthesisOptions {
    options.parse.normalizer.exact_overrides = overrides;
    options
}

pub fn default_parse(dialect: Dialect) -> ParseOptions {
    ParseOptions::new(dialect)
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StreamControl {
    Continue,
    Cancel,
}

#[derive(Clone, Copy, Debug, Default)]
pub struct StreamSummary {
    pub chunks: usize,
    pub samples: usize,
    pub cancelled: bool,
    pub sample_rate: u32,
}

struct StreamSink<'a, F>
where
    F: FnMut(&[f32], u32) -> StreamControl,
{
    emit: &'a mut F,
    pending: Vec<f32>,
    emitted: usize,
    fade_in: usize,
    fade_out: usize,
    sample_rate: u32,
    cancelled: bool,
    chunks: usize,
}

impl<'a, F> StreamSink<'a, F>
where
    F: FnMut(&[f32], u32) -> StreamControl,
{
    fn new(emit: &'a mut F, sample_rate: u32) -> Self {
        Self {
            emit,
            pending: Vec::new(),
            emitted: 0,
            fade_in: (sample_rate as usize * 10 / 1000).max(1),
            fade_out: (sample_rate as usize * 20 / 1000).max(1),
            sample_rate,
            cancelled: false,
            chunks: 0,
        }
    }

    fn push(&mut self, samples: &[f32]) {
        if self.cancelled {
            return;
        }
        self.pending.extend_from_slice(samples);
        if self.pending.len() <= self.fade_out {
            return;
        }
        let count = self.pending.len() - self.fade_out;
        let mut ready: Vec<f32> = self.pending[..count].to_vec();
        self.apply_fade_in(&mut ready);
        self.pending.drain(..count);
        if (self.emit)(&ready, self.sample_rate) == StreamControl::Cancel {
            self.cancelled = true;
            return;
        }
        self.emitted += ready.len();
        self.chunks += 1;
    }

    fn apply_fade_in(&self, samples: &mut [f32]) {
        if self.fade_in <= 1 {
            return;
        }
        for (index, sample) in samples.iter_mut().enumerate() {
            let global = self.emitted + index;
            if global >= self.fade_in {
                break;
            }
            *sample *= global as f32 / (self.fade_in - 1) as f32;
        }
    }

    fn finish(mut self) -> Result<StreamSummary, String> {
        if self.cancelled {
            return Ok(StreamSummary {
                chunks: self.chunks,
                samples: self.emitted + self.pending.len(),
                cancelled: true,
                sample_rate: self.sample_rate,
            });
        }
        if !self.pending.is_empty() {
            let count = self.pending.len().min(self.fade_out);
            let start = self.pending.len() - count;
            if count > 1 {
                for j in 0..count {
                    let gain = 1.0 - j as f32 / (count - 1) as f32;
                    self.pending[start + j] *= gain;
                }
            }
            let ready = std::mem::take(&mut self.pending);
            if (self.emit)(&ready, self.sample_rate) == StreamControl::Cancel {
                self.cancelled = true;
            } else {
                self.emitted += ready.len();
                self.chunks += 1;
            }
        }
        Ok(StreamSummary {
            chunks: self.chunks,
            samples: self.emitted,
            cancelled: self.cancelled,
            sample_rate: self.sample_rate,
        })
    }
}

impl<A: AcousticModel, V: VocoderModel> SynthesisEngine<A, V> {
    /// Streaming PCM theo chunk. `emit` trả `Cancel` để dừng giữa chừng.
    ///
    /// Fade-in/out giống `postprocess` nhưng chỉ giữ `fade_out` mẫu cuối trong
    /// RAM, không gom cả file. `peak_normalize` chưa hỗ trợ streaming.
    pub async fn synthesize_stream<F>(
        &mut self,
        text: &str,
        options: &SynthesisOptions,
        emit: F,
    ) -> Result<StreamSummary, String>
    where
        F: FnMut(&[f32], u32) -> StreamControl,
    {
        self.synthesize_stream_with_units(text, options, emit, |_units| {})
            .await
    }

    /// Như `synthesize_stream`, nhưng phát thêm timing karaoke tuyệt đối theo chunk.
    ///
    /// `units_emit` được gọi trước audio chunk tương ứng; timing tính theo sample
    /// của toàn bộ stream (đã gồm pause giữa chunk), không phải theo chunk cục bộ.
    pub async fn synthesize_stream_with_units<F, U>(
        &mut self,
        text: &str,
        options: &SynthesisOptions,
        mut emit: F,
        mut units_emit: U,
    ) -> Result<StreamSummary, String>
    where
        F: FnMut(&[f32], u32) -> StreamControl,
        U: FnMut(&[TimedUnit]),
    {
        if options.peak_normalize {
            return Err("peak_normalize chưa hỗ trợ streaming".to_string());
        }
        let chunks = if options.fixed_pauses {
            split_clauses(text, options.max_chars)?
        } else {
            chunk_text(text, options.max_chars)?
        };
        if chunks.is_empty() {
            return Err("Không có nội dung để đọc".to_string());
        }
        let sample_rate = self.info.sample_rate;
        let mut sink = StreamSink::new(&mut emit, sample_rate);
        let mut cursor_samples = 0usize;
        for (index, chunk) in chunks.iter().enumerate() {
            let rendered = self.render_chunk(chunk, options, cursor_samples).await?;
            if !rendered.units.is_empty() {
                units_emit(&rendered.units);
            }
            cursor_samples += rendered.audio.len();
            sink.push(&rendered.audio);
            if sink.cancelled {
                break;
            }
            if index < chunks.len() - 1 {
                let pause = self.pause_for(chunk, options);
                if pause > 0 {
                    sink.push(&vec![0.0; pause]);
                    cursor_samples += pause;
                }
            }
        }
        sink.finish()
    }
}

#[cfg(test)]
mod tests {
    use std::future::Future;
    use std::task::Poll;

    use super::*;

    struct FakeAcoustic;

    impl AcousticModel for FakeAcoustic {
        async fn run(
            &mut self,
            features: &[[i64; 7]],
            _speed: f32,
            _gate: f32,
        ) -> Result<AcousticResult, String> {
            Ok(AcousticResult {
                mel: MelSpectrogram {
                    data: vec![0.0; 4 * features.len().max(1)],
                    frames: 4,
                    mels: features.len().max(1),
                },
                slot_durations: None,
                durations: None,
            })
        }

        fn info(&self) -> &ModelInfo {
            unreachable!()
        }
    }

    struct FakeVocoder;

    impl VocoderModel for FakeVocoder {
        async fn spectrogram(
            &mut self,
            _mel: &MelSpectrogram,
        ) -> Result<ComplexSpectrogram, String> {
            Err("fake vocoder không dùng trong test này".to_string())
        }

        fn info(&self) -> &ModelInfo {
            unreachable!()
        }
    }

    fn block_on<F: Future>(future: F) -> F::Output {
        let waker = std::task::Waker::noop();
        let mut context = std::task::Context::from_waker(waker);
        let mut future = std::pin::pin!(future);
        match future.as_mut().poll(&mut context) {
            Poll::Ready(value) => value,
            Poll::Pending => panic!("fake backend không được pending"),
        }
    }

    #[test]
    fn async_engine_calls_backend_trait() {
        let info = ModelInfo {
            sample_rate: 24_000,
            n_mels: 1,
            n_fft: 1024,
            hop_length: 256,
            arch: "v2_slot5".to_string(),
            vocab_version: "test".to_string(),
            vocab_hash: "test".to_string(),
            acoustic_sha256: String::new(),
            vocoder_sha256: String::new(),
            metadata: Default::default(),
            ort_build: "fake".to_string(),
        };
        let mut engine = SynthesisEngine::new(FakeAcoustic, FakeVocoder, info);
        let mel = block_on(engine.acoustic_mel(&[[0; 7]], 1.0, 0.5)).unwrap();
        assert_eq!((mel.frames, mel.mels), (4, 1));
    }

    #[test]
    fn timing_from_slots_is_absolute() {
        let options = ParseOptions::default();
        let items = parse_text("Xin chào", &options);
        assert_eq!(items.len(), 2);
        // lead=10, mỗi âm tiết O+M+N+C=20, gap=5.
        let slots = vec![10, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5];
        let units = timed_units_from_slots(&items, &slots, 256, 24_000, 100_000, 1_000);
        assert_eq!(units.len(), 2);
        // 1000 + 10*256 = 3560 sample -> 148 ms; +20*256 -> 361 ms.
        assert_eq!((units[0].start_ms, units[0].end_ms), (148, 361));
        // 1000 + 35*256 = 9960 -> 415 ms.
        assert_eq!((units[1].start_ms, units[1].end_ms), (415, 628));
    }

    #[test]
    fn timing_missing_or_mismatched_slots_is_empty() {
        let items = parse_text("Xin chào", &ParseOptions::default());
        assert!(timed_units_from_slots(&items, &[], 256, 24_000, 1_000, 0).is_empty());
        assert!(timed_units_from_slots(&items, &[1, 2, 3], 256, 24_000, 1_000, 0).is_empty());
    }
}
