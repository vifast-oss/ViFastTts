//! Port phát audio realtime.
//!
//! Core/application chỉ đẩy PCM; adapter nền tảng quyết định Web Audio,
//! AVAudioEngine, AAudio, CoreAudio, WASAPI...

/// Đầu ra PCM cho streaming.
pub trait AudioSink {
    fn start(&mut self, sample_rate: u32) -> Result<(), String>;
    fn push(&mut self, samples: &[f32]) -> Result<(), String>;
    fn stop(&mut self) -> Result<(), String>;
}
