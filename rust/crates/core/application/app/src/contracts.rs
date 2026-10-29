//! Hợp đồng dữ liệu dùng chung cho mọi UI.
//!
//! UI chỉ giữ widget/điều hướng/audio device; defaults, validate, ETA, từ điển
//! và sample text nằm ở đây để desktop/web/extension/Android/iOS không lặp lại.

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

use crate::dictionary::parse_dictionary;
use crate::history::{EtaEstimator, EtaSample};

pub const CONTRACT_VERSION: u32 = 1;
pub const DEFAULT_SERVER_URL: &str = "http://127.0.0.1:8000";
pub const DEFAULT_MAX_CHARS: usize = 300;
pub const HISTORY_LIMIT: usize = 20;

/// Cấu hình tổng hợp tối thiểu mà mọi UI đều có.
///
/// Đây là *hợp đồng JSON*, không thay thế `AppSettings` đang lưu của desktop.
/// UI được phép có thêm field riêng (output_dir, auto_play, ...).
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(default)]
pub struct SynthesisSettings {
    /// `local` hoặc `remote`; normalize về `local` nếu lạ.
    pub mode: String,
    pub speed: f32,
    pub alpha: f32,
    pub max_chars: usize,
    pub fixed_pauses: bool,
    pub peak_normalize: bool,
    pub dialect: String,
    pub resolve_oov: bool,
    /// Từ điển text `key = cách đọc`; parser dùng chung ở `parse_dictionary`.
    pub dictionary: String,
    /// Custom reading token-level; FFI/WASM/HTTP đều nhận cùng shape.
    pub custom_reading: BTreeMap<String, String>,
    pub stream: bool,
    pub server_url: String,
    pub token: String,
    pub model_base_url: String,
}

impl Default for SynthesisSettings {
    fn default() -> Self {
        Self {
            mode: "local".to_string(),
            speed: 1.0,
            alpha: 1.5,
            max_chars: DEFAULT_MAX_CHARS,
            fixed_pauses: false,
            peak_normalize: false,
            dialect: "north".to_string(),
            resolve_oov: true,
            dictionary: String::new(),
            custom_reading: BTreeMap::new(),
            stream: false,
            server_url: DEFAULT_SERVER_URL.to_string(),
            token: String::new(),
            model_base_url: String::new(),
        }
    }
}

impl SynthesisSettings {
    /// Chuẩn hoá thay vì từ chối: UI cũ có thể gửi 0/giá trị ngoài khoảng.
    pub fn normalized(mut self) -> Self {
        if self.mode != "remote" {
            self.mode = "local".to_string();
        }
        if !self.speed.is_finite() || !(0.5..=2.0).contains(&self.speed) {
            self.speed = 1.0;
        }
        if !self.alpha.is_finite() || !(0.5..=3.0).contains(&self.alpha) {
            self.alpha = 1.5;
        }
        if self.max_chars == 0 {
            self.max_chars = DEFAULT_MAX_CHARS;
        }
        self.max_chars = self.max_chars.clamp(50, 5000);
        if !matches!(self.dialect.as_str(), "north" | "central" | "south") {
            self.dialect = "north".to_string();
        }
        self.server_url = self.server_url.trim().trim_end_matches('/').to_string();
        self.token = self.token.trim().to_string();
        self.model_base_url = self.model_base_url.trim().trim_end_matches('/').to_string();
        self.custom_reading
            .retain(|key, value| !key.trim().is_empty() && !value.trim().is_empty());
        self
    }

    pub fn validate(&self) -> Result<(), String> {
        if !self.speed.is_finite() || !(0.5..=2.0).contains(&self.speed) {
            return Err("speed phải trong 0.5..2.0".to_string());
        }
        if !self.alpha.is_finite() || !(0.5..=3.0).contains(&self.alpha) {
            return Err("alpha phải trong 0.5..3.0".to_string());
        }
        if self.max_chars < 50 || self.max_chars > 5000 {
            return Err("max_chars phải trong 50..5000".to_string());
        }
        if !matches!(self.dialect.as_str(), "north" | "central" | "south") {
            return Err("dialect phải là north/central/south".to_string());
        }
        if self.mode == "remote" && self.server_url.is_empty() {
            return Err("remote mode cần server_url".to_string());
        }
        Ok(())
    }
}

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
        "history_limit": HISTORY_LIMIT,
    }))
    .map_err(|error| format!("api contract JSON: {error}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults_are_canonical_and_normalize_old_values() {
        let defaults = SynthesisSettings::default();
        assert_eq!(defaults.max_chars, 300);
        assert_eq!(defaults.alpha, 1.5);
        assert!(defaults.resolve_oov);

        let normalized = SynthesisSettings {
            mode: "weird".to_string(),
            speed: 9.0,
            alpha: 9.0,
            max_chars: 0,
            dialect: "unknown".to_string(),
            server_url: "https://tts.example.com/".to_string(),
            ..SynthesisSettings::default()
        }
        .normalized();
        assert_eq!(normalized.mode, "local");
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
