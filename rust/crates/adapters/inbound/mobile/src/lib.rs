//! Composition root cho mobile: load model, synth, đẩy PCM vào `AudioSink`.
//!
//! Không biết SwiftUI/Compose/Flutter; UI gọi runtime qua FFI/UniFFI.

use vifasttts_audio_sink::AudioSink;
use vifasttts_model_source::ModelSource;
use vifasttts_native::{
    ModelInfo, NativeEngine, StreamControl, StreamSummary, SynthesisOptions, SynthesisResult,
    from_bytes, load, load_vfa, load_vfts,
};

#[derive(Clone, Debug, Default)]
pub struct MobileConfig {
    /// 0 = không giới hạn; UI vẫn nên có cảnh báo cho text rất dài.
    pub max_text_chars: usize,
}

#[derive(Clone, Debug)]
pub struct MobileStatus {
    pub sample_rate: u32,
    pub arch: String,
    pub vocab_version: String,
    pub max_text_chars: usize,
}

pub struct MobileRuntime {
    engine: NativeEngine,
    config: MobileConfig,
}

impl MobileRuntime {
    pub fn from_paths(
        acoustic: impl AsRef<std::path::Path>,
        vocoder: impl AsRef<std::path::Path>,
        config: MobileConfig,
    ) -> Result<Self, String> {
        Ok(Self {
            engine: load(acoustic, vocoder)?,
            config,
        })
    }

    pub fn from_vfts(
        path: impl AsRef<std::path::Path>,
        config: MobileConfig,
    ) -> Result<Self, String> {
        Ok(Self {
            engine: load_vfts(path)?,
            config,
        })
    }

    /// Nạp acoustic-only `.vfa` với vocoder dùng chung.
    pub fn from_vfa(
        vfa: impl AsRef<std::path::Path>,
        vocoder: impl AsRef<std::path::Path>,
        config: MobileConfig,
    ) -> Result<Self, String> {
        Ok(Self {
            engine: load_vfa(vfa, vocoder)?,
            config,
        })
    }

    pub fn from_bytes(
        acoustic: &[u8],
        vocoder: &[u8],
        config: MobileConfig,
    ) -> Result<Self, String> {
        Ok(Self {
            engine: from_bytes(acoustic, vocoder)?,
            config,
        })
    }

    /// Dùng port `ModelSource` để app cung cấp asset/cache/download.
    pub fn from_source(source: &impl ModelSource, config: MobileConfig) -> Result<Self, String> {
        let bytes = source.load()?;
        Self::from_bytes(&bytes.acoustic, &bytes.vocoder, config)
    }

    pub fn info(&self) -> &ModelInfo {
        self.engine.info()
    }

    pub fn status(&self) -> MobileStatus {
        let info = self.engine.info();
        MobileStatus {
            sample_rate: info.sample_rate,
            arch: info.arch.clone(),
            vocab_version: info.vocab_version.clone(),
            max_text_chars: self.config.max_text_chars,
        }
    }

    fn validate_text(&self, text: &str) -> Result<(), String> {
        let limit = self.config.max_text_chars;
        if limit > 0 && text.chars().count() > limit {
            return Err(format!("Tối đa {limit} ký tự"));
        }
        Ok(())
    }

    pub fn synthesize(
        &mut self,
        text: &str,
        options: &SynthesisOptions,
    ) -> Result<SynthesisResult, String> {
        self.validate_text(text)?;
        self.engine.synthesize(text, options)
    }

    /// Stream PCM vào audio sink của nền tảng (AVAudioEngine/AAudio/...).
    ///
    /// `sink.push` lỗi hoặc callback trả `Cancel` sẽ dừng stream.
    pub fn synthesize_to_sink<S: AudioSink>(
        &mut self,
        text: &str,
        options: &SynthesisOptions,
        sink: &mut S,
    ) -> Result<StreamSummary, String> {
        self.validate_text(text)?;
        sink.start(self.engine.info().sample_rate)?;
        let mut sink_error: Option<String> = None;
        let result = self.engine.synthesize_stream(text, options, |samples, _| {
            if let Err(error) = sink.push(samples) {
                sink_error = Some(error);
                return StreamControl::Cancel;
            }
            StreamControl::Continue
        });
        let stop_result = sink.stop();
        let summary = result?;
        stop_result?;
        if let Some(error) = sink_error {
            return Err(error);
        }
        Ok(summary)
    }
}
