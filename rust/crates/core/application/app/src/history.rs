//! ETA estimator + persistence qua `SettingsStore`.

use serde::{Deserialize, Serialize};
use vifasttts_settings::SettingsStore;

pub const HISTORY_KEY: &str = "vifasttts_history_v1";

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct EtaSample {
    pub mode: String,
    pub chars: usize,
    pub elapsed_ms: u64,
}

/// Ước lượng thời gian theo median ms/ký tự của các lần chạy gần nhất.
#[derive(Clone, Debug, Default)]
pub struct EtaEstimator {
    samples: Vec<EtaSample>,
    max_samples: usize,
}

impl EtaEstimator {
    pub fn new(max_samples: usize) -> Self {
        Self {
            samples: Vec::new(),
            max_samples: max_samples.max(1),
        }
    }

    pub fn from_samples(samples: Vec<EtaSample>, max_samples: usize) -> Self {
        let mut estimator = Self::new(max_samples);
        for sample in samples {
            estimator.record(sample);
        }
        estimator
    }

    pub fn samples(&self) -> &[EtaSample] {
        &self.samples
    }

    pub fn record(&mut self, sample: EtaSample) {
        if sample.chars == 0 || sample.elapsed_ms == 0 {
            return;
        }
        self.samples.push(sample);
        if self.samples.len() > self.max_samples {
            let drain = self.samples.len() - self.max_samples;
            self.samples.drain(0..drain);
        }
    }

    pub fn estimate_ms(&self, mode: &str, chars: usize) -> Option<u64> {
        if chars == 0 {
            return None;
        }
        let mut rates: Vec<f64> = self
            .samples
            .iter()
            .filter(|sample| sample.mode == mode && sample.chars > 0)
            .map(|sample| sample.elapsed_ms as f64 / sample.chars as f64)
            .collect();
        if rates.is_empty() {
            return None;
        }
        rates.sort_by(f64::total_cmp);
        let median = rates[rates.len() / 2];
        Some((median * chars as f64).round() as u64)
    }
}

pub struct HistoryService<S: SettingsStore> {
    store: S,
    max_samples: usize,
}

impl<S: SettingsStore> HistoryService<S> {
    pub fn new(store: S, max_samples: usize) -> Self {
        Self { store, max_samples }
    }

    pub fn load(&self) -> Result<Vec<EtaSample>, String> {
        let Some(raw) = self.store.get(HISTORY_KEY) else {
            return Ok(Vec::new());
        };
        serde_json::from_str(&raw).map_err(|error| format!("history JSON: {error}"))
    }

    pub fn save(&mut self, samples: &[EtaSample]) -> Result<(), String> {
        let raw =
            serde_json::to_string(samples).map_err(|error| format!("history JSON: {error}"))?;
        self.store.set(HISTORY_KEY, &raw)
    }

    pub fn estimator(&self) -> Result<EtaEstimator, String> {
        Ok(EtaEstimator::from_samples(self.load()?, self.max_samples))
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
    fn eta_uses_matching_mode_median() {
        let mut eta = EtaEstimator::new(8);
        eta.record(EtaSample {
            mode: "local".to_string(),
            chars: 100,
            elapsed_ms: 500,
        });
        eta.record(EtaSample {
            mode: "local".to_string(),
            chars: 100,
            elapsed_ms: 600,
        });
        eta.record(EtaSample {
            mode: "remote".to_string(),
            chars: 100,
            elapsed_ms: 9000,
        });
        assert_eq!(eta.estimate_ms("local", 200), Some(1200));
        assert_eq!(eta.estimate_ms("remote", 100), Some(9000));
        assert_eq!(eta.estimate_ms("missing", 100), None);
    }

    #[test]
    fn history_roundtrip() {
        let mut history = HistoryService::new(MemoryStore::default(), 8);
        history
            .save(&[EtaSample {
                mode: "local".to_string(),
                chars: 10,
                elapsed_ms: 100,
            }])
            .unwrap();
        let estimator = history.estimator().unwrap();
        assert_eq!(estimator.estimate_ms("local", 10), Some(100));
    }
}
