//! Backend traits/types dùng chung cho ORT native và ORT Web.
//!
//! Trait là async để browser (Promise ORT Web) và native dùng chung engine.
//! Native backend trả future sẵn sàng ngay; adapter native block_on ở runtime.
#![allow(async_fn_in_trait)]

use std::collections::BTreeMap;

#[derive(Clone, Debug)]
pub struct ModelInfo {
    pub sample_rate: u32,
    pub n_mels: usize,
    pub n_fft: usize,
    pub hop_length: usize,
    pub arch: String,
    pub vocab_version: String,
    pub vocab_hash: String,
    pub acoustic_sha256: String,
    pub vocoder_sha256: String,
    pub metadata: BTreeMap<String, String>,
    pub ort_build: String,
}

#[derive(Clone, Debug)]
pub struct MelSpectrogram {
    pub data: Vec<f32>,
    pub frames: usize,
    pub mels: usize,
}

/// Kết quả acoustic: mel + timing (nếu model xuất).
#[derive(Clone, Debug)]
pub struct AcousticResult {
    pub mel: MelSpectrogram,
    /// `[1 + 5N]`: lead + (O, M, N, C, G) cho từng âm tiết.
    pub slot_durations: Option<Vec<i64>>,
    /// `[N]`: số frame hữu thanh từng âm tiết.
    pub durations: Option<Vec<i64>>,
}

#[derive(Clone, Debug)]
pub struct ComplexSpectrogram {
    pub real: Vec<f32>,
    pub imag: Vec<f32>,
    pub bins: usize,
    pub frames: usize,
}

pub trait AcousticModel {
    /// Chạy acoustic; async để ORT Web chờ Promise mà không cần runtime riêng.
    async fn run(
        &mut self,
        features: &[[i64; 7]],
        speed: f32,
        gate: f32,
    ) -> Result<AcousticResult, String>;
    fn info(&self) -> &ModelInfo;
}

pub trait VocoderModel {
    /// MelSpectrogram → spectrogram; cũng async vì ORT Web trả Promise.
    async fn spectrogram(&mut self, mel: &MelSpectrogram) -> Result<ComplexSpectrogram, String>;
    fn info(&self) -> &ModelInfo;
}
