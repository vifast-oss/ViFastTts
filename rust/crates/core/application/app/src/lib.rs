//! Application headless dùng chung cho UI:
//! command vào, event ra; không biết DOM, Chrome, ORT hay audio device.

mod dictionary;
mod history;
mod session;
mod settings;

pub use dictionary::{Dictionary, DictionaryRule, parse_dictionary};
pub use history::{EtaEstimator, EtaSample, HistoryService};
pub use session::{AppCommand, AppEvent, SynthesisController};
pub use settings::{AppSettings, SelectionAction, SettingsService, SynthesisMode};
