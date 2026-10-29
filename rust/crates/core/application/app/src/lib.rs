//! Application headless dùng chung cho UI:
//! command vào, event ra; không biết DOM, Chrome, ORT hay audio device.

mod contracts;
mod dictionary;
mod history;
mod session;
mod settings;

pub use contracts::{
    CONTRACT_VERSION, DEFAULT_SERVER_URL, HISTORY_LIMIT, SampleText, SynthesisSettings,
    api_contract_json, default_text, dictionary_json, eta_estimate_json, sample_texts,
    settings_defaults_json, settings_normalize_json,
};
pub use dictionary::{Dictionary, DictionaryRule, parse_dictionary};
pub use history::{EtaEstimator, EtaSample, HistoryService};
pub use session::{AppCommand, AppEvent, SynthesisController};
pub use settings::{AppSettings, SelectionAction, SettingsService, SynthesisMode};
