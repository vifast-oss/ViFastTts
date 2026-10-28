//! ONNX Runtime Web backend (wasm32): JS callback → `AcousticModel`/`VocoderModel`.
//!
//! JS chỉ chạy model và trả tensor; crate này kiểm shape/contract rồi trả type
//! backend chuẩn. Engine không biết ORT Web, cũng không cần callback riêng.

#[cfg(target_arch = "wasm32")]
mod wasm {
    use std::collections::BTreeMap;

    use js_sys::Promise;
    use wasm_bindgen::prelude::*;
    use wasm_bindgen_futures::JsFuture;

    use vifasttts_ports::{
        AcousticModel, AcousticResult, ComplexSpectrogram, MelSpectrogram, ModelInfo, VocoderModel,
    };

    /// Hợp đồng model tối thiểu cho browser.
    #[derive(Clone, Debug)]
    pub struct OrtWebContract {
        pub sample_rate: u32,
        pub n_mels: usize,
        pub n_fft: usize,
        pub hop_length: usize,
        pub arch: String,
        pub vocab_version: String,
        pub vocab_hash: String,
    }

    impl Default for OrtWebContract {
        fn default() -> Self {
            Self {
                sample_rate: 24_000,
                n_mels: 100,
                n_fft: 1024,
                hop_length: 256,
                arch: "v2_slot5".to_string(),
                vocab_version: String::new(),
                vocab_hash: String::new(),
            }
        }
    }

    impl OrtWebContract {
        pub fn model_info(&self) -> ModelInfo {
            ModelInfo {
                sample_rate: self.sample_rate,
                n_mels: self.n_mels,
                n_fft: self.n_fft,
                hop_length: self.hop_length,
                arch: self.arch.clone(),
                vocab_version: self.vocab_version.clone(),
                vocab_hash: self.vocab_hash.clone(),
                acoustic_sha256: String::new(),
                vocoder_sha256: String::new(),
                metadata: BTreeMap::new(),
                ort_build: "onnxruntime-web".to_string(),
            }
        }
    }

    /// JS callback `acoustic(features, speed, gate) → Promise<AcousticResult>`.
    pub struct OrtWebAcousticModel {
        function: js_sys::Function,
        info: ModelInfo,
    }

    /// JS callback `vocoder(mel, frames, mels) → Promise<ComplexSpectrogram>`.
    pub struct OrtWebVocoderModel {
        function: js_sys::Function,
        info: ModelInfo,
    }

    pub struct OrtWebModelBundle {
        pub acoustic: OrtWebAcousticModel,
        pub vocoder: OrtWebVocoderModel,
        pub info: ModelInfo,
    }

    impl OrtWebModelBundle {
        /// Tạo cặp backend từ 2 callback JS và contract model.
        pub fn new(
            acoustic: js_sys::Function,
            vocoder: js_sys::Function,
            config: OrtWebContract,
        ) -> Self {
            let info = config.model_info();
            Self {
                acoustic: OrtWebAcousticModel {
                    function: acoustic,
                    info: info.clone(),
                },
                vocoder: OrtWebVocoderModel {
                    function: vocoder,
                    info: info.clone(),
                },
                info,
            }
        }
    }

    fn js_error(context: &str, error: JsValue) -> String {
        format!("{context}: {error:?}")
    }

    fn property(value: &JsValue, name: &str) -> Result<JsValue, String> {
        js_sys::Reflect::get(value, &JsValue::from_str(name))
            .map_err(|error| js_error(&format!("thuộc tính {name}"), error))
    }

    fn usize_property(value: &JsValue, name: &str) -> Result<usize, String> {
        property(value, name)?
            .as_f64()
            .map(|number| number as usize)
            .ok_or_else(|| format!("{name} không phải số"))
    }

    fn f32_array(value: &JsValue, name: &str) -> Result<Vec<f32>, String> {
        let array = property(value, name)?
            .dyn_into::<js_sys::Float32Array>()
            .map_err(|_| format!("{name} không phải Float32Array"))?;
        Ok(array.to_vec())
    }

    fn i64_array_opt(value: &JsValue, name: &str) -> Result<Option<Vec<i64>>, String> {
        let value = property(value, name)?;
        if value.is_null() || value.is_undefined() {
            return Ok(None);
        }
        let array = value
            .dyn_into::<js_sys::BigInt64Array>()
            .map_err(|_| format!("{name} không phải BigInt64Array"))?;
        Ok(Some(array.to_vec()))
    }

    async fn await_js(value: JsValue, context: &str) -> Result<JsValue, String> {
        JsFuture::from(Promise::resolve(&value))
            .await
            .map_err(|error| js_error(context, error))
    }

    async fn call_acoustic(
        function: &js_sys::Function,
        features: &[[i64; 7]],
        speed: f32,
        gate: f32,
    ) -> Result<AcousticResult, String> {
        let features = serde_wasm_bindgen::to_value(features)
            .map_err(|error| format!("serialize features: {error}"))?;
        let value = function
            .call3(
                &JsValue::NULL,
                &features,
                &JsValue::from_f64(speed as f64),
                &JsValue::from_f64(gate as f64),
            )
            .map_err(|error| js_error("gọi acoustic", error))?;
        let value = await_js(value, "acoustic Promise").await?;
        parse_acoustic(value)
    }

    async fn call_vocoder(
        function: &js_sys::Function,
        mel: &MelSpectrogram,
    ) -> Result<ComplexSpectrogram, String> {
        let data = serde_wasm_bindgen::to_value(&mel.data)
            .map_err(|error| format!("serialize mel: {error}"))?;
        let value = function
            .call3(
                &JsValue::NULL,
                &data,
                &JsValue::from_f64(mel.frames as f64),
                &JsValue::from_f64(mel.mels as f64),
            )
            .map_err(|error| js_error("gọi vocoder", error))?;
        let value = await_js(value, "vocoder Promise").await?;
        parse_vocoder(value)
    }

    fn parse_acoustic(value: JsValue) -> Result<AcousticResult, String> {
        let frames = usize_property(&value, "frames")?;
        let mels = usize_property(&value, "mels")?;
        if frames == 0 || mels == 0 {
            return Err(format!("mel rỗng: {frames} frame × {mels} kênh"));
        }
        let data = f32_array(&value, "mel")?;
        if data.len() != frames * mels {
            return Err(format!("mel data {} != {frames} × {mels}", data.len()));
        }
        Ok(AcousticResult {
            mel: MelSpectrogram { data, frames, mels },
            slot_durations: i64_array_opt(&value, "slot_durations")?,
            durations: i64_array_opt(&value, "durations")?,
        })
    }

    fn parse_vocoder(value: JsValue) -> Result<ComplexSpectrogram, String> {
        let bins = usize_property(&value, "bins")?;
        let frames = usize_property(&value, "frames")?;
        if bins == 0 || frames == 0 {
            return Err(format!("spectrogram rỗng: {bins} bin × {frames} frame"));
        }
        let real = f32_array(&value, "real")?;
        let imag = f32_array(&value, "imag")?;
        let expected = bins * frames;
        if real.len() != expected || imag.len() != expected {
            return Err(format!(
                "spec length {}/{} != {bins} × {frames}",
                real.len(),
                imag.len()
            ));
        }
        Ok(ComplexSpectrogram {
            real,
            imag,
            bins,
            frames,
        })
    }

    impl AcousticModel for OrtWebAcousticModel {
        async fn run(
            &mut self,
            features: &[[i64; 7]],
            speed: f32,
            gate: f32,
        ) -> Result<AcousticResult, String> {
            if features.is_empty() {
                return Err("không có âm tiết".to_string());
            }
            let output = call_acoustic(&self.function, features, speed, gate).await?;
            if output.mel.mels != self.info.n_mels {
                return Err(format!(
                    "mel có {} kênh, cần {}",
                    output.mel.mels, self.info.n_mels
                ));
            }
            Ok(output)
        }

        fn info(&self) -> &ModelInfo {
            &self.info
        }
    }

    impl VocoderModel for OrtWebVocoderModel {
        async fn spectrogram(
            &mut self,
            mel: &MelSpectrogram,
        ) -> Result<ComplexSpectrogram, String> {
            call_vocoder(&self.function, mel).await
        }

        fn info(&self) -> &ModelInfo {
            &self.info
        }
    }
}

#[cfg(target_arch = "wasm32")]
pub use wasm::*;
