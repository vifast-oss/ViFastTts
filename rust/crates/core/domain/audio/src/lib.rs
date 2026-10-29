//! Audio DSP thuần Rust cho ViFastTts (không model, không I/O).

pub mod audio;

pub use audio::{
    fade, hann_window, istft, peak_normalize, postprocess, sharpen_mel, wav_bytes, wav_bytes_pcm16,
};
