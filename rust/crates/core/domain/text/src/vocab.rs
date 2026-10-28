//! Mã hoá 7 ID, tương đương `frontend/vocab.py`.
//!
//! Nguồn canonical là `resources/vocab.json`, sinh từ Python bằng
//! `tools/export_rust_resources.py`. Hash được kiểm ngay khi nạp.

use std::collections::HashMap;
use std::sync::OnceLock;

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::types::ParsedSyllable;

pub const VOCAB_JSON: &str = include_str!("../resources/vocab.json");

#[derive(Clone, Debug, Deserialize)]
struct VocabFile {
    version: String,
    hash: String,
    onset: Vec<String>,
    medial: Vec<String>,
    nucleus: Vec<String>,
    coda: Vec<String>,
    tone: Vec<String>,
    boundary: Vec<String>,
    punctuation: Vec<String>,
}

#[derive(Clone, Debug, Serialize)]
pub struct VocabPayload {
    pub onset: Vec<String>,
    pub medial: Vec<String>,
    pub nucleus: Vec<String>,
    pub coda: Vec<String>,
    pub tone: Vec<String>,
    pub boundary: Vec<String>,
    pub punctuation: Vec<String>,
}

#[derive(Clone, Debug)]
pub struct ComponentVocabs {
    pub version: String,
    pub onset: Vec<String>,
    pub medial: Vec<String>,
    pub nucleus: Vec<String>,
    pub coda: Vec<String>,
    pub tone: Vec<String>,
    pub boundary: Vec<String>,
    pub punctuation: Vec<String>,
    onset_map: HashMap<String, usize>,
    medial_map: HashMap<String, usize>,
    nucleus_map: HashMap<String, usize>,
    coda_map: HashMap<String, usize>,
    tone_map: HashMap<String, usize>,
    boundary_map: HashMap<String, usize>,
    punctuation_map: HashMap<String, usize>,
}

fn map(values: &[String]) -> HashMap<String, usize> {
    values
        .iter()
        .enumerate()
        .map(|(index, value)| (value.clone(), index))
        .collect()
}

impl Default for ComponentVocabs {
    fn default() -> Self {
        static CACHE: OnceLock<ComponentVocabs> = OnceLock::new();
        CACHE.get_or_init(Self::load).clone()
    }
}

impl ComponentVocabs {
    fn load() -> Self {
        let file: VocabFile =
            serde_json::from_str(VOCAB_JSON).expect("resources/vocab.json không hợp lệ");
        let payload = VocabPayload {
            onset: file.onset.clone(),
            medial: file.medial.clone(),
            nucleus: file.nucleus.clone(),
            coda: file.coda.clone(),
            tone: file.tone.clone(),
            boundary: file.boundary.clone(),
            punctuation: file.punctuation.clone(),
        };
        let expected = vocab_hash_from_payload(&payload);
        assert_eq!(
            expected, file.hash,
            "vocab_hash của resources/vocab.json không khớp canonical; chạy lại tools/export_rust_resources.py"
        );
        Self {
            version: file.version,
            onset_map: map(&file.onset),
            medial_map: map(&file.medial),
            nucleus_map: map(&file.nucleus),
            coda_map: map(&file.coda),
            tone_map: map(&file.tone),
            boundary_map: map(&file.boundary),
            punctuation_map: map(&file.punctuation),
            onset: file.onset,
            medial: file.medial,
            nucleus: file.nucleus,
            coda: file.coda,
            tone: file.tone,
            boundary: file.boundary,
            punctuation: file.punctuation,
        }
    }

    pub fn payload(&self) -> VocabPayload {
        VocabPayload {
            onset: self.onset.clone(),
            medial: self.medial.clone(),
            nucleus: self.nucleus.clone(),
            coda: self.coda.clone(),
            tone: self.tone.clone(),
            boundary: self.boundary.clone(),
            punctuation: self.punctuation.clone(),
        }
    }

    pub fn hash(&self) -> String {
        vocab_hash_from_payload(&self.payload())
    }

    fn get(map: &HashMap<String, usize>, value: &str, kind: &str) -> usize {
        *map.get(value)
            .unwrap_or_else(|| panic!("vocab {kind} thiếu token {value:?}"))
    }

    /// `[onset, medial, nucleus, coda, tone, boundary, punctuation]`.
    pub fn encode(&self, item: &ParsedSyllable) -> [usize; 7] {
        let boundary = if item.boundaries.sentence_end {
            "SENTENCE"
        } else if item.boundaries.phrase_end {
            "PHRASE"
        } else {
            "WORD"
        };
        let punct = item.punctuation.as_deref().unwrap_or("");
        let punctuation = if punct.contains('?') {
            "QUESTION"
        } else if punct.contains('!') {
            "EXCLAMATION"
        } else if punct.contains(',') {
            "COMMA"
        } else if punct.contains('.') {
            "PERIOD"
        } else if !punct.is_empty() {
            "OTHER"
        } else {
            "NONE"
        };
        let a = &item.abstract_;
        [
            Self::get(&self.onset_map, &a.onset, "onset"),
            Self::get(&self.medial_map, &a.medial, "medial"),
            Self::get(&self.nucleus_map, &a.nucleus, "nucleus"),
            Self::get(&self.coda_map, &a.coda, "coda"),
            Self::get(&self.tone_map, a.tone.as_str(), "tone"),
            Self::get(&self.boundary_map, boundary, "boundary"),
            Self::get(&self.punctuation_map, punctuation, "punctuation"),
        ]
    }
}

fn vocab_hash_from_payload(payload: &VocabPayload) -> String {
    let canonical = serde_json::to_string(payload).expect("serialize vocab");
    let digest = Sha256::digest(canonical.as_bytes());
    hex::encode(digest)
}

pub fn vocab_version() -> String {
    ComponentVocabs::default().version
}

pub fn vocab_hash() -> String {
    ComponentVocabs::default().hash()
}

/// Kiểm hash nếu artifact có; production Rust sẽ yêu cầu hash (khác Python transitional).
pub fn verify_vocab_hash(value: Option<&str>, source: &str) -> Result<(), String> {
    let Some(value) = value else {
        return Ok(());
    };
    let expected = vocab_hash();
    if value != expected {
        return Err(format!(
            "{source}: vocab_hash không khớp (artifact {value} vs frontend {expected})"
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::syllable::parse_syllable;

    #[test]
    fn hash_matches_python_contract() {
        assert_eq!(
            vocab_hash(),
            "1a33a9622a13443f296ee3c1f6fe5190bd0d72845ec61a1756a3d10784f1785a"
        );
    }

    #[test]
    fn encodes_quoc() {
        let item = parse_syllable("quốc").unwrap();
        let ids = ComponentVocabs::default().encode(&item);
        assert_eq!(ids.len(), 7);
        assert_eq!(ids[0], 24); // Q cuối
        assert_eq!(ids[2], 12); // UÔ
    }
}
