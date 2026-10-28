//! Port transport cho synthesize remote.
//!
//! HTTP/ureq/URLSession/OkHttp chỉ là adapter; application không cần biết.

use std::collections::BTreeMap;

#[derive(Clone, Debug)]
pub struct SynthesisRequest {
    pub text: String,
    pub speed: f32,
    pub fixed_pauses: bool,
    pub overrides: BTreeMap<String, String>,
}

#[derive(Clone, Debug)]
pub struct SynthesisResponse {
    pub wav: Vec<u8>,
    pub sample_rate: u32,
    /// JSON của `KaraokeDocument` nếu server trả timing.
    pub karaoke_json: Option<String>,
    pub srt: String,
    pub vtt: String,
}

pub trait TtsTransport {
    fn synthesize(&self, request: &SynthesisRequest) -> Result<SynthesisResponse, String>;
}
