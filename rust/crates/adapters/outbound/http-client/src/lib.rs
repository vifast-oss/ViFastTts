//! HTTP client cho `vifasttts-http-server` (WAV + karaoke JSON).

use base64::Engine as _;
use base64::engine::general_purpose::STANDARD as BASE64;
use serde::{Deserialize, Serialize};
use vifasttts_text::karaoke::KaraokeDocument;

#[derive(Clone, Debug)]
pub struct HttpTtsClient {
    base_url: String,
    token: Option<String>,
    agent: ureq::Agent,
}

#[derive(Clone, Debug, Serialize)]
pub struct HttpTtsRequest {
    pub text: String,
    #[serde(default)]
    pub speed: f32,
    #[serde(default)]
    pub fixed_pauses: bool,
}

impl Default for HttpTtsRequest {
    fn default() -> Self {
        Self {
            text: String::new(),
            speed: 1.0,
            fixed_pauses: false,
        }
    }
}

impl HttpTtsRequest {
    pub fn new(text: impl Into<String>) -> Self {
        Self {
            text: text.into(),
            speed: 1.0,
            fixed_pauses: false,
        }
    }
}

#[derive(Clone, Debug, Deserialize)]
pub struct ServerHealth {
    pub ok: bool,
    pub sample_rate: u32,
    pub arch: String,
    pub vocab_version: String,
    pub vocab_hash: String,
    pub alpha: f32,
    pub pause: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct ServerConfig {
    pub max_chars: usize,
    pub rate_limit: u32,
    pub rate_window: f64,
}

#[derive(Clone, Debug, Deserialize)]
pub struct HttpTtsResponse {
    pub sample_rate: u32,
    pub duration_ms: u64,
    pub audio_base64: String,
    pub karaoke: KaraokeDocument,
    pub srt: String,
    pub vtt: String,
    pub vtt_karaoke: String,
}

impl HttpTtsResponse {
    pub fn audio_bytes(&self) -> Result<Vec<u8>, String> {
        BASE64
            .decode(&self.audio_base64)
            .map_err(|err| format!("decode audio_base64: {err}"))
    }
}

impl HttpTtsClient {
    pub fn new(base_url: impl Into<String>, token: Option<String>) -> Self {
        let mut base_url = base_url.into();
        while base_url.ends_with('/') {
            base_url.pop();
        }
        Self {
            base_url,
            token,
            agent: ureq::Agent::new_with_defaults(),
        }
    }

    fn url(&self, path: &str) -> String {
        format!("{}{}", self.base_url, path)
    }

    fn auth(
        &self,
        request: ureq::RequestBuilder<ureq::typestate::WithBody>,
    ) -> ureq::RequestBuilder<ureq::typestate::WithBody> {
        match &self.token {
            Some(token) => request.header("Authorization", &format!("Bearer {token}")),
            None => request,
        }
    }

    pub fn health(&self) -> Result<ServerHealth, String> {
        let mut response = self
            .agent
            .get(self.url("/healthz"))
            .call()
            .map_err(|err| format!("GET /healthz: {err}"))?;
        response
            .body_mut()
            .read_json::<ServerHealth>()
            .map_err(|err| format!("parse /healthz: {err}"))
    }

    pub fn config(&self) -> Result<ServerConfig, String> {
        let mut response = self
            .agent
            .get(self.url("/api/config"))
            .call()
            .map_err(|err| format!("GET /api/config: {err}"))?;
        response
            .body_mut()
            .read_json::<ServerConfig>()
            .map_err(|err| format!("parse /api/config: {err}"))
    }

    /// Trả WAV bytes từ `/api/tts`.
    pub fn synthesize_wav(&self, options: &HttpTtsRequest) -> Result<Vec<u8>, String> {
        let mut response = self
            .auth(
                self.agent
                    .post(self.url("/api/tts"))
                    .header("Content-Type", "application/json"),
            )
            .send_json(options)
            .map_err(|err| format!("POST /api/tts: {err}"))?;
        response
            .body_mut()
            .read_to_vec()
            .map_err(|err| format!("read /api/tts: {err}"))
    }

    /// Trả WAV + timing từ `/api/tts` với `karaoke: true`.
    pub fn synthesize_karaoke(&self, options: &HttpTtsRequest) -> Result<HttpTtsResponse, String> {
        #[derive(Serialize)]
        struct Request<'a> {
            #[serde(flatten)]
            options: &'a HttpTtsRequest,
            karaoke: bool,
        }
        let mut response = self
            .auth(
                self.agent
                    .post(self.url("/api/tts"))
                    .header("Content-Type", "application/json"),
            )
            .send_json(Request {
                options,
                karaoke: true,
            })
            .map_err(|err| format!("POST /api/tts karaoke: {err}"))?;
        response
            .body_mut()
            .read_json::<HttpTtsResponse>()
            .map_err(|err| format!("parse /api/tts karaoke: {err}"))
    }
}
