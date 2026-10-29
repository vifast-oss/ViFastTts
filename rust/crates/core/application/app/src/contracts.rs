//! Hợp đồng dữ liệu dùng chung cho mọi UI.
//!
//! UI chỉ giữ widget/điều hướng/audio device; defaults, validate, ETA, từ điển
//! và sample text nằm ở đây để desktop/web/extension/Android/iOS không lặp lại.

use serde::{Deserialize, Serialize};

use crate::dictionary::parse_dictionary;
use crate::history::{EtaEstimator, EtaSample};
use crate::settings::AppSettings;

pub const CONTRACT_VERSION: u32 = 1;
pub const DEFAULT_SERVER_URL: &str = "http://127.0.0.1:8000";
pub const HISTORY_LIMIT: usize = 20;

/// Một schema settings duy nhất: `AppSettings` của application app.
///
/// Alias này giữ tên hợp đồng cho UI/FFI/WASM; không tạo struct settings thứ hai.
pub type SynthesisSettings = AppSettings;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct SampleText {
    pub id: String,
    pub label: String,
    pub text: String,
    /// UI nên chọn câu này làm text mặc định cho platform tương ứng.
    pub default: bool,
}

fn sample(id: &str, label: &str, text: &str, default: bool) -> SampleText {
    SampleText {
        id: id.to_string(),
        label: label.to_string(),
        text: text.to_string(),
        default,
    }
}

/// Danh sách sample dùng chung; `platform` chỉ quyết định câu mặc định/thứ tự.
///
/// Yêu cầu sản phẩm: câu mặc định Android có chữ "Android", iOS có chữ "iOS".
pub fn sample_texts(platform: &str) -> Vec<SampleText> {
    let platform = platform.trim().to_ascii_lowercase();
    let greeting = sample(
        "greeting",
        "Chào",
        "Xin chào các bạn, hôm nay trời đẹp.",
        false,
    );
    let android = sample(
        "android",
        "Android",
        "Xin chào các bạn, đây là bản Android của ViFastTts.",
        false,
    );
    let ios = sample(
        "ios",
        "iOS",
        "Xin chào, đây là bản iOS của ViFastTts.",
        false,
    );
    let desktop = sample(
        "desktop",
        "Desktop",
        "Xin chào, đây là bản desktop local-first của ViFastTts.",
        false,
    );
    let tui = sample(
        "tui",
        "TUI",
        "Xin chào, đây là bản TUI của ViFastTts.",
        false,
    );
    let web = sample(
        "web",
        "Web",
        "Xin chào các bạn, đây là bản web của ViFastTts.",
        false,
    );

    match platform.as_str() {
        "android" => vec![
            SampleText {
                default: true,
                ..android
            },
            greeting,
            ios,
        ],
        "ios" => vec![
            SampleText {
                default: true,
                ..ios
            },
            greeting,
        ],
        "desktop" => vec![
            SampleText {
                default: true,
                ..desktop
            },
            greeting,
        ],
        "tui" => vec![
            SampleText {
                default: true,
                ..tui
            },
            greeting,
        ],
        "web" | "extension" => vec![
            SampleText {
                default: true,
                ..web
            },
            greeting,
        ],
        _ => vec![
            SampleText {
                default: true,
                ..greeting
            },
            android,
            ios,
        ],
    }
}

pub fn default_text(platform: &str) -> String {
    sample_texts(platform)
        .into_iter()
        .find(|sample| sample.default)
        .map(|sample| sample.text)
        .unwrap_or_default()
}

pub fn settings_defaults_json() -> Result<String, String> {
    serde_json::to_string_pretty(&SynthesisSettings::default())
        .map_err(|error| format!("settings defaults JSON: {error}"))
}

pub fn settings_normalize_json(raw: &str) -> Result<String, String> {
    let settings: SynthesisSettings = if raw.trim().is_empty() {
        SynthesisSettings::default()
    } else {
        serde_json::from_str(raw).map_err(|error| format!("settings JSON không hợp lệ: {error}"))?
    };
    let settings = settings.normalized();
    settings.validate()?;
    serde_json::to_string(&settings).map_err(|error| format!("settings JSON: {error}"))
}

/// ETA bằng đúng median `EtaEstimator`; history có thể chứa field UI riêng.
pub fn eta_estimate_json(
    history_json: &str,
    mode: &str,
    chars: u32,
    max_samples: u32,
) -> Result<String, String> {
    let samples: Vec<EtaSample> = if history_json.trim().is_empty() {
        Vec::new()
    } else {
        serde_json::from_str(history_json)
            .map_err(|error| format!("history JSON không hợp lệ: {error}"))?
    };
    let estimator = EtaEstimator::from_samples(samples, max_samples as usize);
    serde_json::to_string(&estimator.estimate_ms(mode, chars as usize))
        .map_err(|error| format!("ETA JSON: {error}"))
}

/// Kết quả parser từ điển dùng chung: rules/warnings/overrides.
pub fn dictionary_json(text: &str) -> Result<String, String> {
    let dictionary = parse_dictionary(text);
    serde_json::to_string(&serde_json::json!({
        "rules": dictionary.rules,
        "warnings": dictionary.warnings,
        "overrides": dictionary.overrides(),
    }))
    .map_err(|error| format!("dictionary JSON: {error}"))
}

/// Hợp đồng endpoint tối thiểu; UI không tự ghép path/health khác nhau.
pub fn api_contract_json() -> Result<String, String> {
    serde_json::to_string_pretty(&serde_json::json!({
        "version": CONTRACT_VERSION,
        "tts": "/api/tts",
        "tts_stream": "/api/tts/stream",
        "health": "/healthz",
        "config": "/api/config",
        "models_search": "/api/models/search",
        "models_files": "/api/models/files",
        "models_download": "/api/models/download",
        "openapi": "/api/openapi.json",
        "history_limit": HISTORY_LIMIT,
    }))
    .map_err(|error| format!("api contract JSON: {error}"))
}

/// OpenAPI 3.1 tối thiểu cho client/generated DTO.
///
/// Chỉ mô tả phần ổn định của HTTP API; UI/audio/storage vẫn native. Dùng
/// `openapi_json` thay vì tự chép field schema sang từng ngôn ngữ.
pub fn openapi_json() -> Result<String, String> {
    let payload = serde_json::json!({
        "openapi": "3.1.0",
        "info": {
            "title": "ViFastTts HTTP API",
            "version": env!("CARGO_PKG_VERSION"),
            "description": "TTS local/remote; PCM stream NDJSON; catalog .vfa/.vfts."
        },
        "servers": [{"url": "http://127.0.0.1:8000", "description": "local"}],
        "paths": {
            "/healthz": {
                "get": {
                    "summary": "Health + model metadata",
                    "responses": {"200": {"description": "OK", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Health"}}}}}
                }
            },
            "/api/config": {
                "get": {
                    "summary": "Public limits",
                    "responses": {"200": {"description": "OK", "content": {"application/json": {"schema": {"type": "object", "properties": {"max_chars": {"type": "integer"}, "rate_limit": {"type": "integer"}, "rate_window": {"type": "number"}}}}}}}
                }
            },
            "/api/tts": {
                "post": {
                    "summary": "Synthesize WAV or JSON+karaoke",
                    "requestBody": {"required": true, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/TtsRequest"}}}},
                    "responses": {
                        "200": {
                            "description": "WAV bytes or JSON when karaoke=true",
                            "content": {
                                "audio/wav": {"schema": {"type": "string", "format": "binary"}},
                                "application/json": {"schema": {"$ref": "#/components/schemas/TtsResponse"}}
                            }
                        },
                        "422": {"description": "Invalid text/options"},
                        "429": {"description": "Rate limited"},
                        "503": {"description": "Busy"}
                    }
                }
            },
            "/api/tts/stream": {
                "post": {
                    "summary": "Stream PCM16 NDJSON",
                    "requestBody": {"required": true, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/TtsRequest"}}}},
                    "responses": {"200": {"description": "NDJSON events", "content": {"application/x-ndjson": {"schema": {"$ref": "#/components/schemas/StreamEvent"}}}}}
                }
            },
            "/api/models/search": {
                "get": {
                    "summary": "Search HuggingFace models",
                    "parameters": [
                        {"name": "q", "in": "query", "schema": {"type": "string", "default": "vifasttts"}},
                        {"name": "limit", "in": "query", "schema": {"type": "integer", "default": 20, "maximum": 50}}
                    ],
                    "responses": {"200": {"description": "Normalized models", "content": {"application/json": {"schema": {"type": "array", "items": {"$ref": "#/components/schemas/ModelSummary"}}}}}}
                }
            },
            "/api/models/files": {
                "get": {
                    "summary": "List .vfa/.vfts bundles",
                    "parameters": [{"name": "repo", "in": "query", "required": true, "schema": {"type": "string"}}],
                    "responses": {"200": {"description": "Bundles", "content": {"application/json": {"schema": {"type": "array", "items": {"$ref": "#/components/schemas/ModelFile"}}}}}}
                }
            },
            "/api/models/download": {
                "get": {
                    "summary": "Download a bundle",
                    "parameters": [
                        {"name": "repo", "in": "query", "required": true, "schema": {"type": "string"}},
                        {"name": "path", "in": "query", "required": true, "schema": {"type": "string"}}
                    ],
                    "responses": {"200": {"description": "Bundle bytes", "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}}}}
                }
            },
            "/api/openapi.json": {
                "get": {"summary": "This document", "responses": {"200": {"description": "OpenAPI JSON"}}}
            }
        },
        "components": {
            "schemas": {
                "TtsRequest": {
                    "type": "object",
                    "required": ["text"],
                    "properties": {
                        "text": {"type": "string"},
                        "speed": {"type": "number", "minimum": 0.5, "maximum": 2.0, "default": 1.0},
                        "alpha": {"type": "number", "minimum": 0.5, "maximum": 3.0, "default": 1.5},
                        "max_chars": {"type": "integer", "minimum": 50, "maximum": 5000, "default": 300},
                        "fixed_pauses": {"type": "boolean", "default": false},
                        "peak_normalize": {"type": "boolean", "default": false},
                        "dialect": {"type": "string", "enum": ["north", "central", "south"], "default": "north"},
                        "resolve_oov": {"type": "boolean", "default": true},
                        "dictionary": {"type": "string", "description": "key = cách đọc"},
                        "custom_reading": {"type": "object", "additionalProperties": {"type": "string"}},
                        "overrides": {"type": "object", "additionalProperties": {"type": "string"}},
                        "karaoke": {"type": "boolean", "default": false},
                        "visitor_id": {"type": "string"},
                        "source": {"type": "string", "enum": ["web", "space", "api"], "default": "api"}
                    }
                },
                "TtsResponse": {
                    "type": "object",
                    "required": ["sample_rate", "duration_ms", "audio_base64"],
                    "properties": {
                        "sample_rate": {"type": "integer"},
                        "duration_ms": {"type": "integer"},
                        "audio_base64": {"type": "string", "format": "byte"},
                        "karaoke": {"$ref": "#/components/schemas/Karaoke"},
                        "srt": {"type": "string"},
                        "vtt": {"type": "string"},
                        "vtt_karaoke": {"type": "string"}
                    }
                },
                "Karaoke": {
                    "type": "object",
                    "properties": {
                        "duration_ms": {"type": "integer"},
                        "sample_rate": {"type": "integer"},
                        "units": {"type": "array", "items": {"type": "object"}},
                        "lines": {"type": "array", "items": {"type": "object"}}
                    }
                },
                "ModelSummary": {
                    "type": "object",
                    "required": ["id", "bundle_count"],
                    "properties": {"id": {"type": "string"}, "bundle_count": {"type": "integer"}}
                },
                "ModelFile": {
                    "type": "object",
                    "required": ["path", "size"],
                    "properties": {"path": {"type": "string"}, "size": {"type": "integer"}}
                },
                "StreamEvent": {
                    "type": "object",
                    "required": ["type"],
                    "properties": {
                        "type": {"type": "string", "enum": ["units", "audio", "done", "error"]},
                        "units": {"type": "array", "items": {"type": "object"}},
                        "sample_rate": {"type": "integer"},
                        "pcm_base64": {"type": "string", "format": "byte"},
                        "samples": {"type": "integer"},
                        "chunks": {"type": "integer"},
                        "cancelled": {"type": "boolean"},
                        "message": {"type": "string"}
                    }
                },
                "Health": {
                    "type": "object",
                    "properties": {
                        "ok": {"type": "boolean"},
                        "sample_rate": {"type": "integer"},
                        "arch": {"type": "string"},
                        "vocab_version": {"type": "string"},
                        "vocab_hash": {"type": "string"},
                        "alpha": {"type": "number"},
                        "pause": {"type": "string"}
                    }
                }
            }
        }
    });
    serde_json::to_string_pretty(&payload).map_err(|error| format!("openapi JSON: {error}"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::settings::SynthesisMode;

    #[test]
    fn defaults_are_canonical_and_normalize_old_values() {
        let defaults = SynthesisSettings::default();
        assert_eq!(defaults.max_chars, 300);
        assert_eq!(defaults.alpha, 1.5);
        assert!(defaults.resolve_oov);

        let normalized = SynthesisSettings {
            mode: SynthesisMode::Local,
            speed: 9.0,
            alpha: 9.0,
            max_chars: 0,
            dialect: "unknown".to_string(),
            server_url: "https://tts.example.com/".to_string(),
            ..SynthesisSettings::default()
        }
        .normalized();
        assert_eq!(normalized.mode, SynthesisMode::Local);
        assert_eq!(normalized.speed, 1.0);
        assert_eq!(normalized.alpha, 1.5);
        assert_eq!(normalized.max_chars, 300);
        assert_eq!(normalized.dialect, "north");
        assert_eq!(normalized.server_url, "https://tts.example.com");
        normalized.validate().unwrap();
    }

    #[test]
    fn platform_samples_follow_product_rule() {
        let android = sample_texts("android");
        assert!(
            android
                .iter()
                .any(|sample| sample.default && sample.text.contains("Android"))
        );
        let ios = sample_texts("ios");
        assert!(
            ios.iter()
                .any(|sample| sample.default && sample.text.contains("iOS"))
        );
        assert!(default_text("android").contains("Android"));
        assert!(default_text("ios").contains("iOS"));
    }

    #[test]
    fn eta_ignores_ui_only_history_fields() {
        let json = r#"[
            {"mode":"local","chars":100,"elapsed_ms":500,"audio_seconds":1.0,"at":1,"text":"x"},
            {"mode":"local","chars":100,"elapsed_ms":700,"audio_seconds":1.0,"at":2,"text":"y"},
            {"mode":"remote","chars":100,"elapsed_ms":9000,"audio_seconds":1.0,"at":3,"text":"z"}
        ]"#;
        assert_eq!(eta_estimate_json(json, "local", 200, 20).unwrap(), "1400");
    }

    #[test]
    fn dictionary_and_api_contract_are_json() {
        let dictionary: serde_json::Value =
            serde_json::from_str(&dictionary_json("AI = ây ai\n").unwrap()).unwrap();
        assert_eq!(dictionary["rules"].as_array().unwrap().len(), 1);
        let contract: serde_json::Value =
            serde_json::from_str(&api_contract_json().unwrap()).unwrap();
        assert_eq!(contract["tts"], "/api/tts");
    }
}
