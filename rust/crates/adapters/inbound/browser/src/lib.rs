//! Browser/WASM adapter: async engine + parse/karaoke/DSP helpers.
//!
//! Model inference do `vifasttts-ort-web` (JS callback) đảm nhiệm. Crate này là
//! adapter ngang hàng `vifasttts-native`: cùng gọi `vifasttts-engine`, chỉ khác
//! backend và kiểu API (wasm async thay vì sync).

#[cfg(target_arch = "wasm32")]
mod wasm {
    use std::collections::HashMap;

    use serde::{Deserialize, Serialize};
    use wasm_bindgen::prelude::*;

    use vifasttts_app::{EtaEstimator, EtaSample, parse_dictionary};
    use vifasttts_audio as audio;
    use vifasttts_engine::{
        StreamControl, SynthesisEngine, SynthesisOptions, timed_units_from_slots,
    };
    use vifasttts_ort_web::{OrtWebContract, OrtWebModelBundle};
    use vifasttts_text::karaoke::{KaraokeDocument, TimedUnit};
    use vifasttts_text::pipeline::{live_parse_options, parse_text};
    use vifasttts_text::types::ParsedSyllable;
    use vifasttts_text::vocab::ComponentVocabs;

    #[derive(Clone, Debug, Serialize, Deserialize)]
    struct ParsedPayload {
        features: Vec<[i64; 7]>,
        items: Vec<ParsedSyllable>,
    }

    fn js_error(error: impl ToString) -> JsValue {
        JsValue::from_str(&error.to_string())
    }

    fn parse_payload(
        text: &str,
        options: &vifasttts_text::pipeline::ParseOptions,
    ) -> Result<JsValue, JsValue> {
        let items = parse_text(text, options);
        let vocabs = ComponentVocabs::default();
        let features = items
            .iter()
            .map(|item| vocabs.encode(item).map(|id| id as i64))
            .collect();
        serde_wasm_bindgen::to_value(&ParsedPayload { features, items })
            .map_err(|err| JsValue::from_str(&err.to_string()))
    }

    /// Dùng chung parser từ điển của `vifasttts-app`; trả JSON
    /// `{rules, warnings, overrides}` để UI/offscreen không parse lại bằng JS.
    #[wasm_bindgen]
    pub fn dictionary_json(text: &str) -> Result<String, JsValue> {
        let dictionary = parse_dictionary(text);
        let payload = serde_json::json!({
            "rules": dictionary.rules,
            "warnings": dictionary.warnings,
            "overrides": dictionary.overrides(),
        });
        serde_json::to_string(&payload)
            .map_err(|error| JsValue::from_str(&format!("dictionary JSON: {error}")))
    }

    /// Ước lượng ETA bằng đúng median `EtaEstimator` của application app.
    #[wasm_bindgen]
    pub fn eta_estimate(
        samples_json: &str,
        mode: &str,
        chars: usize,
        max_samples: usize,
    ) -> Result<JsValue, JsValue> {
        let samples: Vec<EtaSample> = serde_json::from_str(samples_json)
            .map_err(|error| JsValue::from_str(&format!("history JSON: {error}")))?;
        let estimator = EtaEstimator::from_samples(samples, max_samples.max(1));
        serde_wasm_bindgen::to_value(&estimator.estimate_ms(mode, chars))
            .map_err(|error| JsValue::from_str(&error.to_string()))
    }

    #[wasm_bindgen]
    pub fn parse_tts(text: &str, resolve_oov: bool) -> Result<JsValue, JsValue> {
        let mut options = live_parse_options(vifasttts_text::dialect::Dialect::North, None, None);
        options.resolve_oov = resolve_oov;
        parse_payload(text, &options)
    }

    /// Parse có từ điển local (debug/preview).
    #[wasm_bindgen]
    pub fn parse_tts_with_options(
        text: &str,
        resolve_oov: bool,
        overrides_json: &str,
    ) -> Result<JsValue, JsValue> {
        let overrides = parse_map(overrides_json, "overrides").map_err(js_error)?;
        let mut options = live_parse_options(
            vifasttts_text::dialect::Dialect::North,
            Some(&overrides),
            None,
        );
        options.resolve_oov = resolve_oov;
        parse_payload(text, &options)
    }

    #[wasm_bindgen]
    pub fn chunk_text(text: &str, max_chars: usize) -> Result<JsValue, JsValue> {
        let chunks = vifasttts_text::chunking::chunk_text(text, max_chars)
            .map_err(|err| JsValue::from_str(&err))?;
        serde_wasm_bindgen::to_value(&chunks).map_err(|err| JsValue::from_str(&err.to_string()))
    }

    #[wasm_bindgen]
    pub fn split_clauses(text: &str, max_chars: usize) -> Result<JsValue, JsValue> {
        let chunks = vifasttts_text::chunking::split_clauses(text, max_chars)
            .map_err(|err| JsValue::from_str(&err))?;
        serde_wasm_bindgen::to_value(&chunks).map_err(|err| JsValue::from_str(&err.to_string()))
    }

    #[wasm_bindgen]
    pub fn pause_seconds(chunk: &str) -> f64 {
        vifasttts_text::chunking::pause_seconds(chunk)
    }

    #[wasm_bindgen]
    pub fn steady_pause_seconds(chunk: &str, comma: f64, period: f64, default: f64) -> f64 {
        vifasttts_text::chunking::steady_pause_seconds(chunk, comma, period, default)
    }

    /// `items` là JSON từ `parse_tts`; `slots` là output `slot_durations` (flatten).
    #[wasm_bindgen]
    pub fn karaoke_from_slots(
        items: JsValue,
        slots: &[i64],
        hop_length: usize,
        sample_rate: u32,
        audio_samples: usize,
        sample_offset: usize,
    ) -> Result<JsValue, JsValue> {
        let payload: ParsedPayload = serde_wasm_bindgen::from_value(items)
            .map_err(|err| JsValue::from_str(&err.to_string()))?;
        let units = timed_units_from_slots(
            &payload.items,
            slots,
            hop_length,
            sample_rate,
            audio_samples,
            sample_offset,
        );
        let duration_ms = (sample_offset + audio_samples) as u64 * 1000 / sample_rate.max(1) as u64;
        let document = KaraokeDocument::from_units(units, sample_rate, duration_ms, 80);
        serde_wasm_bindgen::to_value(&document).map_err(|err| JsValue::from_str(&err.to_string()))
    }

    #[wasm_bindgen]
    pub fn sharpen_mel(data: &[f32], frames: usize, mels: usize, alpha: f32) -> Vec<f32> {
        audio::sharpen_mel(data, frames, mels, alpha)
    }

    #[wasm_bindgen]
    pub fn istft(
        real: &[f32],
        imag: &[f32],
        bins: usize,
        frames: usize,
        n_fft: usize,
        hop_length: usize,
    ) -> Result<Vec<f32>, JsValue> {
        audio::istft(real, imag, bins, frames, n_fft, hop_length, None, true)
            .map_err(|err| JsValue::from_str(&err))
    }

    #[wasm_bindgen]
    pub fn wav_bytes(samples: &[f32], sample_rate: u32) -> Vec<u8> {
        audio::wav_bytes(samples, sample_rate)
    }

    #[wasm_bindgen]
    pub fn karaoke_to_srt(document: JsValue) -> Result<String, JsValue> {
        let document: KaraokeDocument = serde_wasm_bindgen::from_value(document)
            .map_err(|err| JsValue::from_str(&err.to_string()))?;
        Ok(document.to_srt())
    }

    #[wasm_bindgen]
    pub fn karaoke_to_vtt(document: JsValue) -> Result<String, JsValue> {
        let document: KaraokeDocument = serde_wasm_bindgen::from_value(document)
            .map_err(|err| JsValue::from_str(&err.to_string()))?;
        Ok(document.to_vtt_karaoke())
    }

    #[derive(Debug, Serialize)]
    struct WasmSynthesis {
        wav: Vec<u8>,
        sample_rate: u32,
        duration_ms: u64,
        karaoke: Option<KaraokeDocument>,
    }

    fn parse_map(json: &str, name: &str) -> Result<HashMap<String, String>, String> {
        if json.trim().is_empty() {
            return Ok(HashMap::new());
        }
        serde_json::from_str(json).map_err(|err| format!("{name} JSON không hợp lệ: {err}"))
    }

    fn build_synth_options(
        speed: f32,
        fixed_pauses: bool,
        overrides_json: &str,
        custom_reading_json: &str,
    ) -> Result<SynthesisOptions, String> {
        let overrides = parse_map(overrides_json, "overrides")?;
        let custom_reading = parse_map(custom_reading_json, "custom_reading")?;
        let mut parse = live_parse_options(
            vifasttts_text::dialect::Dialect::North,
            Some(&overrides),
            None,
        );
        parse.resolve_oov = true;
        if !custom_reading.is_empty() {
            parse.custom_reading = Some(custom_reading);
        }
        let mut options = SynthesisOptions {
            speed,
            fixed_pauses,
            parse,
            ..SynthesisOptions::default()
        };
        if fixed_pauses {
            options.gate_threshold = 1.01;
        }
        Ok(options)
    }

    /// SynthesisEngine browser dùng chung `vifasttts-engine` với native.
    ///
    /// JS cung cấp 2 callback async; `vifasttts-ort-web` chuyển chúng thành
    /// `AcousticModel`/`VocoderModel`, nên wasm không còn loop synth riêng.
    ///
    /// - `acoustic(features, speed, gate)` → `{mel, frames, mels, slot_durations}`
    /// - `vocoder(mel, frames, mels)` → `{real, imag, bins, frames}`
    #[wasm_bindgen]
    pub async fn synthesize(
        text: &str,
        speed: f32,
        fixed_pauses: bool,
        acoustic: js_sys::Function,
        vocoder: js_sys::Function,
    ) -> Result<JsValue, JsValue> {
        synthesize_with_options(text, speed, fixed_pauses, "", "", acoustic, vocoder).await
    }

    /// Như `synthesize` nhưng có từ điển local.
    ///
    /// - `overrides_json`: object JSON `{"AI":"ây ai"}` — phrase/token overrides.
    /// - `custom_reading_json`: object JSON cho custom reading token-level.
    #[wasm_bindgen]
    pub async fn synthesize_with_options(
        text: &str,
        speed: f32,
        fixed_pauses: bool,
        overrides_json: &str,
        custom_reading_json: &str,
        acoustic: js_sys::Function,
        vocoder: js_sys::Function,
    ) -> Result<JsValue, JsValue> {
        let options = build_synth_options(speed, fixed_pauses, overrides_json, custom_reading_json)
            .map_err(js_error)?;

        let components = OrtWebModelBundle::new(acoustic, vocoder, OrtWebContract::default());
        let mut engine =
            SynthesisEngine::new(components.acoustic, components.vocoder, components.info);
        let synthesis = engine.synthesize(text, &options).await.map_err(js_error)?;
        let duration_ms =
            (synthesis.waveform.len() as u64) * 1000 / synthesis.sample_rate.max(1) as u64;
        let result = WasmSynthesis {
            wav: synthesis.wav,
            sample_rate: synthesis.sample_rate,
            duration_ms,
            karaoke: synthesis.karaoke,
        };
        serde_wasm_bindgen::to_value(&result).map_err(|err| JsValue::from_str(&err.to_string()))
    }

    #[derive(Serialize)]
    struct WasmStreamSummary {
        chunks: usize,
        samples: usize,
        cancelled: bool,
        sample_rate: u32,
    }

    /// Streaming PCM: callback audio/units được gọi trong lúc engine chạy.
    ///
    /// `on_audio({samples: Float32Array, sample_rate})` trả `false` để huỷ.
    /// `on_units(units)` nhận timing karaoke của chunk.
    #[allow(clippy::too_many_arguments)]
    #[wasm_bindgen]
    pub async fn synthesize_stream_with_options(
        text: &str,
        speed: f32,
        fixed_pauses: bool,
        overrides_json: &str,
        custom_reading_json: &str,
        acoustic: js_sys::Function,
        vocoder: js_sys::Function,
        on_audio: js_sys::Function,
        on_units: js_sys::Function,
    ) -> Result<JsValue, JsValue> {
        let options = build_synth_options(speed, fixed_pauses, overrides_json, custom_reading_json)
            .map_err(js_error)?;

        let components = OrtWebModelBundle::new(acoustic, vocoder, OrtWebContract::default());
        let mut engine =
            SynthesisEngine::new(components.acoustic, components.vocoder, components.info);

        let summary = engine
            .synthesize_stream_with_units(
                text,
                &options,
                |samples, sample_rate| {
                    let event = js_sys::Object::new();
                    let array = js_sys::Float32Array::from(samples);
                    if js_sys::Reflect::set(&event, &"samples".into(), &array).is_err()
                        || js_sys::Reflect::set(
                            &event,
                            &"sample_rate".into(),
                            &JsValue::from_f64(sample_rate as f64),
                        )
                        .is_err()
                    {
                        return StreamControl::Cancel;
                    }
                    match on_audio.call1(&JsValue::NULL, &event) {
                        Ok(value) if value.as_bool() == Some(false) => StreamControl::Cancel,
                        Ok(_) => StreamControl::Continue,
                        Err(_) => StreamControl::Cancel,
                    }
                },
                |units| {
                    if let Ok(value) = serde_wasm_bindgen::to_value(units) {
                        let _ = on_units.call1(&JsValue::NULL, &value);
                    }
                },
            )
            .await
            .map_err(js_error)?;

        let result = WasmStreamSummary {
            chunks: summary.chunks,
            samples: summary.samples,
            cancelled: summary.cancelled,
            sample_rate: summary.sample_rate,
        };
        serde_wasm_bindgen::to_value(&result).map_err(|err| JsValue::from_str(&err.to_string()))
    }

    #[wasm_bindgen]
    pub fn karaoke_from_units(
        units: JsValue,
        sample_rate: u32,
        duration_ms: u32,
        max_chars: usize,
    ) -> Result<JsValue, JsValue> {
        let units: Vec<TimedUnit> = serde_wasm_bindgen::from_value(units)
            .map_err(|err| JsValue::from_str(&err.to_string()))?;
        let document =
            KaraokeDocument::from_units(units, sample_rate, duration_ms as u64, max_chars.max(1));
        serde_wasm_bindgen::to_value(&document).map_err(|err| JsValue::from_str(&err.to_string()))
    }
}

#[cfg(target_arch = "wasm32")]
pub use wasm::*;
