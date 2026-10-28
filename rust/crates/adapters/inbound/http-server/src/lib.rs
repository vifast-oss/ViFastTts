//! HTTP server tối thiểu: /healthz, /api/config, /api/tts.

use std::collections::HashMap;
use std::convert::Infallible;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

use axum::body::Body;
use axum::extract::{DefaultBodyLimit, State};
use axum::http::{HeaderMap, StatusCode, header};
use axum::response::{IntoResponse, Response};
use axum::routing::{get, post};
use axum::{Json, Router};
use base64::Engine as _;
use base64::engine::general_purpose::STANDARD as BASE64;
use clap::Parser;
use serde::{Deserialize, Serialize};
use tokio::sync::mpsc;
use tokio_stream::wrappers::ReceiverStream;
use tower_http::cors::CorsLayer;
use tower_http::services::ServeDir;
use vifasttts_app::parse_dictionary;
use vifasttts_native::{
    KaraokeDocument, NativeEngine, StreamControl, SynthesisOptions, load, load_verified, load_vfa,
    load_vfa_auto, load_vfts,
};
use vifasttts_text::dialect::Dialect;
use vifasttts_text::pipeline::live_parse_options;

#[derive(Parser, Debug, Clone)]
pub struct Args {
    #[arg(long, default_value = "artifacts/onnx/n0_q/acoustic.onnx")]
    pub acoustic: PathBuf,
    #[arg(long, default_value = "artifacts/onnx/n0_q/vocoder.onnx")]
    pub vocoder: PathBuf,
    #[arg(long)]
    pub manifest: Option<PathBuf>,
    #[arg(long, default_value = "127.0.0.1")]
    pub host: String,
    #[arg(long, default_value_t = 8000)]
    pub port: u16,
    #[arg(long, default_value_t = 3000)]
    pub max_chars: usize,
    /// Bearer token tuỳ chọn; nếu đặt, /api/* yêu cầu Authorization.
    #[arg(long, env = "VIFASTTS_TOKEN")]
    pub token: Option<String>,
    /// Thư mục web đã build (web/dist); server phục vụ SPA tại `/`.
    #[arg(long)]
    pub web_dir: Option<PathBuf>,
    /// Nạp model từ bundle `.vfts` (thay acoustic/vocoder).
    #[arg(long)]
    pub vfts: Option<PathBuf>,
    /// Nạp acoustic-only `.vfa`; cần `--vocoder` dùng chung.
    #[arg(long)]
    pub vfa: Option<PathBuf>,
    /// Cho phép CORS cho web UI chạy ở origin khác (chỉ dùng khi cần).
    #[arg(long)]
    pub cors: bool,
    /// Chỉ chạy API, không phục vụ web dù có `--web-dir`/`web`.
    #[arg(long)]
    pub api_only: bool,
}

struct AppState {
    engine: Mutex<NativeEngine>,
    pub max_chars: usize,
    alpha: f32,
    pub token: Option<String>,
}

fn authorized(headers: &HeaderMap, token: Option<&str>) -> bool {
    let Some(expected) = token else {
        return true;
    };
    headers
        .get(header::AUTHORIZATION)
        .and_then(|value| value.to_str().ok())
        .and_then(|value| value.strip_prefix("Bearer "))
        .is_some_and(|value| value == expected)
}

#[derive(Debug, Deserialize)]
struct HttpTtsRequest {
    text: String,
    #[serde(default = "one")]
    speed: f32,
    #[serde(default)]
    fixed_pauses: bool,
    /// Trả JSON kèm audio base64 + timing/karaoke thay vì WAV.
    #[serde(default)]
    karaoke: bool,
    /// Từ điển local: `{"AI": "ây ai"}`.
    #[serde(default)]
    overrides: Option<HashMap<String, String>>,
    /// Từ điển dạng text `key = cách đọc` (dùng chung parser `vifasttts-app`).
    #[serde(default)]
    dictionary: Option<String>,
}

fn synth_options(
    speed: f32,
    fixed_pauses: bool,
    overrides: Option<&HashMap<String, String>>,
    dictionary: Option<&str>,
) -> SynthesisOptions {
    let mut options = SynthesisOptions {
        speed,
        fixed_pauses,
        alpha: 1.5,
        ..SynthesisOptions::default()
    };
    let mut merged = HashMap::new();
    if let Some(overrides) = overrides {
        merged.extend(
            overrides
                .iter()
                .map(|(key, value)| (key.clone(), value.clone())),
        );
    }
    if let Some(text) = dictionary {
        merged.extend(parse_dictionary(text).overrides());
    }
    if !merged.is_empty() {
        options.parse = live_parse_options(Dialect::North, Some(&merged), None);
    }
    if fixed_pauses {
        options.gate_threshold = 1.01;
    }
    options
}

#[derive(Debug, Serialize)]
struct HttpTtsResponse {
    sample_rate: u32,
    duration_ms: u64,
    audio_base64: String,
    karaoke: KaraokeDocument,
    srt: String,
    vtt: String,
    vtt_karaoke: String,
}

fn one() -> f32 {
    1.0
}

#[derive(Debug, Serialize)]
struct HealthResponse {
    ok: bool,
    sample_rate: u32,
    arch: String,
    vocab_version: String,
    vocab_hash: String,
    alpha: f32,
    pause: &'static str,
}

#[derive(Debug, Serialize)]
struct ConfigResponse {
    pub max_chars: usize,
    rate_limit: u32,
    rate_window: f64,
}

async fn health(State(state): State<Arc<AppState>>) -> Json<HealthResponse> {
    let engine = state.engine.lock().expect("engine lock");
    let info = engine.info();
    Json(HealthResponse {
        ok: true,
        sample_rate: info.sample_rate,
        arch: info.arch.clone(),
        vocab_version: info.vocab_version.clone(),
        vocab_hash: info.vocab_hash.clone(),
        alpha: state.alpha,
        pause: "model",
    })
}

async fn config(State(state): State<Arc<AppState>>) -> Json<ConfigResponse> {
    Json(ConfigResponse {
        max_chars: state.max_chars,
        rate_limit: 0,
        rate_window: 60.0,
    })
}

fn pcm16_base64(samples: &[f32]) -> String {
    let mut bytes = Vec::with_capacity(samples.len() * 2);
    for value in samples {
        let pcm = (value.clamp(-1.0, 1.0) * 32767.0)
            .round_ties_even()
            .clamp(-32768.0, 32767.0) as i16;
        bytes.extend_from_slice(&pcm.to_le_bytes());
    }
    BASE64.encode(bytes)
}

/// NDJSON streaming: audio chunk (PCM16 base64), units, done.
async fn tts_stream(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Json(payload): Json<HttpTtsRequest>,
) -> Response {
    if !authorized(&headers, state.token.as_deref()) {
        return (StatusCode::UNAUTHORIZED, "Bearer token không hợp lệ").into_response();
    }
    let text = payload
        .text
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ");
    if text.is_empty() {
        return (StatusCode::UNPROCESSABLE_ENTITY, "Nhập câu cần đọc").into_response();
    }
    if text.chars().count() > state.max_chars {
        return (
            StatusCode::UNPROCESSABLE_ENTITY,
            format!("Tối đa {} ký tự", state.max_chars),
        )
            .into_response();
    }
    if !text.chars().any(char::is_alphabetic) {
        return (StatusCode::UNPROCESSABLE_ENTITY, "Cần ít nhất một chữ cái").into_response();
    }
    let speed = payload.speed.clamp(0.8, 1.2);
    let fixed_pauses = payload.fixed_pauses;
    let state_ref = Arc::clone(&state);
    let (tx, rx) = mpsc::channel::<Result<String, Infallible>>(64);
    tokio::task::spawn_blocking(move || {
        let mut engine = match state_ref.engine.lock() {
            Ok(engine) => engine,
            Err(_) => {
                let _ = tx.blocking_send(Ok(
                    "{\"type\":\"error\",\"message\":\"engine lock\"}\n".to_string()
                ));
                return;
            }
        };
        let options = synth_options(
            speed,
            fixed_pauses,
            payload.overrides.as_ref(),
            payload.dictionary.as_deref(),
        );
        let audio_tx = tx.clone();
        let units_tx = tx.clone();
        let result = engine.synthesize_stream_with_units(
            &text,
            &options,
            |samples, sample_rate| {
                let event = serde_json::json!({
                    "type": "audio",
                    "sample_rate": sample_rate,
                    "pcm_base64": pcm16_base64(samples),
                });
                match audio_tx.blocking_send(Ok(format!("{event}\n"))) {
                    Ok(()) => StreamControl::Continue,
                    Err(_) => StreamControl::Cancel,
                }
            },
            |units| {
                let event = serde_json::json!({"type": "units", "units": units});
                let _ = units_tx.blocking_send(Ok(format!("{event}\n")));
            },
        );
        let event = match result {
            Ok(summary) => serde_json::json!({
                "type": "done",
                "samples": summary.samples,
                "chunks": summary.chunks,
                "cancelled": summary.cancelled,
                "sample_rate": summary.sample_rate,
            }),
            Err(error) => serde_json::json!({"type": "error", "message": error}),
        };
        let _ = tx.blocking_send(Ok(format!("{event}\n")));
    });
    (
        StatusCode::OK,
        [
            (header::CONTENT_TYPE, "application/x-ndjson"),
            (header::CACHE_CONTROL, "no-store"),
        ],
        Body::from_stream(ReceiverStream::new(rx)),
    )
        .into_response()
}

async fn tts(
    State(state): State<Arc<AppState>>,
    headers: HeaderMap,
    Json(payload): Json<HttpTtsRequest>,
) -> Response {
    if !authorized(&headers, state.token.as_deref()) {
        return (StatusCode::UNAUTHORIZED, "Bearer token không hợp lệ").into_response();
    }
    let text = payload
        .text
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ");
    if text.is_empty() {
        return (StatusCode::UNPROCESSABLE_ENTITY, "Nhập câu cần đọc").into_response();
    }
    if text.chars().count() > state.max_chars {
        return (
            StatusCode::UNPROCESSABLE_ENTITY,
            format!("Tối đa {} ký tự", state.max_chars),
        )
            .into_response();
    }
    if !text.chars().any(char::is_alphabetic) {
        return (StatusCode::UNPROCESSABLE_ENTITY, "Cần ít nhất một chữ cái").into_response();
    }
    let speed = payload.speed.clamp(0.8, 1.2);
    let fixed_pauses = payload.fixed_pauses;
    let karaoke = payload.karaoke;
    let overrides = payload.overrides;
    let dictionary = payload.dictionary;
    let state_ref = Arc::clone(&state);
    let result = tokio::task::spawn_blocking(move || {
        let mut engine = state_ref
            .engine
            .lock()
            .map_err(|_| "engine lock".to_string())?;
        let options = synth_options(
            speed,
            fixed_pauses,
            overrides.as_ref(),
            dictionary.as_deref(),
        );
        engine.synthesize(&text, &options)
    })
    .await;
    let synthesis = match result {
        Ok(Ok(value)) => value,
        Ok(Err(error)) => {
            return (StatusCode::INTERNAL_SERVER_ERROR, error).into_response();
        }
        Err(error) => {
            return (StatusCode::INTERNAL_SERVER_ERROR, error.to_string()).into_response();
        }
    };
    let audio_seconds = synthesis.waveform.len() as f64 / synthesis.sample_rate as f64;
    if karaoke {
        let Some(document) = synthesis.karaoke else {
            return (
                StatusCode::UNPROCESSABLE_ENTITY,
                "model không xuất timing (slot_durations)",
            )
                .into_response();
        };
        let payload = HttpTtsResponse {
            sample_rate: synthesis.sample_rate,
            duration_ms: document.duration_ms,
            audio_base64: BASE64.encode(&synthesis.wav),
            srt: document.to_srt(),
            vtt: document.to_vtt(),
            vtt_karaoke: document.to_vtt_karaoke(),
            karaoke: document,
        };
        return (StatusCode::OK, Json(payload)).into_response();
    }
    (
        StatusCode::OK,
        [
            (header::CONTENT_TYPE, "audio/wav"),
            (header::CACHE_CONTROL, "no-store"),
        ],
        synthesis.wav,
    )
        .into_response()
        .tap_audio(audio_seconds)
}

trait TapAudio {
    fn tap_audio(self, seconds: f64) -> Self;
}

impl TapAudio for Response {
    fn tap_audio(mut self, seconds: f64) -> Self {
        if let Ok(value) = header::HeaderValue::from_str(&format!("{seconds:.2}")) {
            self.headers_mut().insert("x-audio-seconds", value);
        }
        self
    }
}

pub async fn serve(args: Args) -> Result<(), String> {
    let engine = if let Some(path) = args.vfa {
        if args.vocoder.exists() {
            load_vfa(path, &args.vocoder)?
        } else {
            load_vfa_auto(path)?
        }
    } else if let Some(path) = args.vfts {
        load_vfts(path)?
    } else {
        match args.manifest {
            Some(path) => load_verified(&args.acoustic, &args.vocoder, path)?,
            None => load(&args.acoustic, &args.vocoder)?,
        }
    };
    let state = Arc::new(AppState {
        engine: Mutex::new(engine),
        max_chars: args.max_chars,
        alpha: 1.5,
        token: args.token.filter(|value| !value.trim().is_empty()),
    });
    let mut app = Router::new()
        .route("/healthz", get(health))
        .route("/api/config", get(config))
        .route("/api/tts", post(tts))
        .route("/api/tts/stream", post(tts_stream))
        .layer(DefaultBodyLimit::max(64 * 1024))
        .with_state(state);
    if !args.api_only
        && let Some(web_dir) = args.web_dir
    {
        if web_dir.is_dir() {
            app = app.fallback_service(ServeDir::new(web_dir));
        } else {
            return Err(format!("web-dir không tồn tại: {}", web_dir.display()));
        }
    }
    if args.cors {
        app = app.layer(CorsLayer::permissive());
    }
    let listener = tokio::net::TcpListener::bind((args.host.as_str(), args.port))
        .await
        .map_err(|err| format!("bind {}:{}: {err}", args.host, args.port))?;
    axum::serve(listener, app)
        .await
        .map_err(|err| format!("serve: {err}"))
}

impl Default for Args {
    fn default() -> Self {
        Self {
            acoustic: PathBuf::from("artifacts/onnx/n0_q/acoustic.onnx"),
            vocoder: PathBuf::from("artifacts/onnx/n0_q/vocoder.onnx"),
            manifest: None,
            host: "127.0.0.1".to_string(),
            port: 8000,
            max_chars: 3000,
            token: None,
            web_dir: None,
            vfts: None,
            vfa: None,
            cors: false,
            api_only: false,
        }
    }
}
