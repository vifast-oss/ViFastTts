//! Typed settings + validation; storage thật do `SettingsStore` adapter lo.

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use vifasttts_settings::SettingsStore;

pub const SETTINGS_KEY: &str = "vifasttts_settings_v1";

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum SynthesisMode {
    #[default]
    Local,
    Remote,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum SelectionAction {
    #[default]
    Hidden,
    Popup,
    Tab,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
pub struct AppSettings {
    pub mode: SynthesisMode,
    pub speed: f32,
    pub fixed_pauses: bool,
    pub alpha: f32,
    pub peak_normalize: bool,
    pub max_chars: usize,
    pub dialect: String,
    pub resolve_oov: bool,
    pub custom_reading: BTreeMap<String, String>,
    pub stream: bool,
    pub selection_action: SelectionAction,
    pub dictionary: String,
    pub server_url: String,
    pub token: String,
    pub model_base_url: String,
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            mode: SynthesisMode::Local,
            speed: 1.0,
            fixed_pauses: false,
            alpha: 1.5,
            peak_normalize: false,
            max_chars: 300,
            dialect: "north".to_string(),
            resolve_oov: true,
            custom_reading: BTreeMap::new(),
            stream: false,
            selection_action: SelectionAction::Hidden,
            dictionary: String::new(),
            server_url: "http://127.0.0.1:8000".to_string(),
            token: String::new(),
            model_base_url: String::new(),
        }
    }
}

impl AppSettings {
    /// Chuẩn hoá dữ liệu cũ/lạ; UI có thể gửi 0 hoặc giá trị ngoài khoảng.
    pub fn normalized(mut self) -> Self {
        if !self.speed.is_finite() || !(0.5..=2.0).contains(&self.speed) {
            self.speed = 1.0;
        }
        if !self.alpha.is_finite() || !(0.5..=3.0).contains(&self.alpha) {
            self.alpha = 1.5;
        }
        if self.max_chars == 0 {
            self.max_chars = 300;
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
        // 0 = settings cũ dùng mặc định 300; normalized() đổi thành 300.
        if self.max_chars != 0 && !(50..=5000).contains(&self.max_chars) {
            return Err("max_chars phải trong 50..5000".to_string());
        }
        if !matches!(self.dialect.as_str(), "north" | "central" | "south") {
            return Err("dialect phải là north/central/south".to_string());
        }
        if self.mode == SynthesisMode::Remote && self.server_url.trim().is_empty() {
            return Err("remote mode cần server_url".to_string());
        }
        Ok(())
    }
}

pub struct SettingsService<S: SettingsStore> {
    store: S,
}

impl<S: SettingsStore> SettingsService<S> {
    pub fn new(store: S) -> Self {
        Self { store }
    }

    pub fn store(&self) -> &S {
        &self.store
    }

    pub fn store_mut(&mut self) -> &mut S {
        &mut self.store
    }

    pub fn load(&self) -> Result<AppSettings, String> {
        let Some(raw) = self.store.get(SETTINGS_KEY) else {
            return Ok(AppSettings::default());
        };
        let settings: AppSettings = serde_json::from_str(&raw)
            .map_err(|error| format!("settings JSON không hợp lệ: {error}"))?;
        settings.validate()?;
        Ok(settings)
    }

    pub fn save(&mut self, settings: &AppSettings) -> Result<(), String> {
        settings.validate()?;
        let raw = serde_json::to_string(settings)
            .map_err(|error| format!("serialize settings: {error}"))?;
        self.store.set(SETTINGS_KEY, &raw)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    #[derive(Default)]
    struct MemoryStore(HashMap<String, String>);

    impl SettingsStore for MemoryStore {
        fn get(&self, key: &str) -> Option<String> {
            self.0.get(key).cloned()
        }

        fn set(&mut self, key: &str, value: &str) -> Result<(), String> {
            self.0.insert(key.to_string(), value.to_string());
            Ok(())
        }

        fn remove(&mut self, key: &str) -> Result<(), String> {
            self.0.remove(key);
            Ok(())
        }
    }

    #[test]
    fn settings_roundtrip_and_validation() {
        let mut service = SettingsService::new(MemoryStore::default());
        assert_eq!(service.load().unwrap().mode, SynthesisMode::Local);

        let mut settings = AppSettings {
            mode: SynthesisMode::Remote,
            server_url: "https://tts.example.com".to_string(),
            selection_action: SelectionAction::Tab,
            ..AppSettings::default()
        };
        service.save(&settings).unwrap();

        let loaded = service.load().unwrap();
        assert_eq!(loaded.mode, SynthesisMode::Remote);
        assert_eq!(loaded.selection_action, SelectionAction::Tab);

        settings.speed = 5.0;
        assert!(service.save(&settings).is_err());
    }
}
