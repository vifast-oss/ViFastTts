//! Kiểu dữ liệu lõi, tương đương `src/vifasttts/types.py`.

use serde::{Deserialize, Serialize};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum Tone {
    Ngang,
    Huyen,
    Sac,
    Hoi,
    Nga,
    Nang,
}

impl Tone {
    pub const ALL: [Tone; 6] = [
        Tone::Ngang,
        Tone::Huyen,
        Tone::Sac,
        Tone::Hoi,
        Tone::Nga,
        Tone::Nang,
    ];

    pub fn as_str(self) -> &'static str {
        match self {
            Tone::Ngang => "NGANG",
            Tone::Huyen => "HUYEN",
            Tone::Sac => "SAC",
            Tone::Hoi => "HOI",
            Tone::Nga => "NGA",
            Tone::Nang => "NANG",
        }
    }

    pub fn from_code(value: &str) -> Option<Self> {
        Some(match value {
            "NGANG" => Tone::Ngang,
            "HUYEN" => Tone::Huyen,
            "SAC" => Tone::Sac,
            "HOI" => Tone::Hoi,
            "NGA" => Tone::Nga,
            "NANG" => Tone::Nang,
            _ => return None,
        })
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum ParseStatus {
    Valid,
    Invalid,
    #[serde(rename = "FALLBACK_REQUIRED")]
    FallbackRequired,
}

impl ParseStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            ParseStatus::Valid => "VALID",
            ParseStatus::Invalid => "INVALID",
            ParseStatus::FallbackRequired => "FALLBACK_REQUIRED",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Orthography {
    pub onset: Option<String>,
    pub medial: Option<String>,
    pub nucleus: String,
    pub coda: Option<String>,
    pub tone_location: Option<String>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct AbstractSyllable {
    pub onset: String,
    pub medial: String,
    pub nucleus: String,
    pub coda: String,
    pub tone: Tone,
}

impl AbstractSyllable {
    pub fn rime(&self) -> (&str, &str, &str) {
        (&self.medial, &self.nucleus, &self.coda)
    }

    pub fn rime_key(&self) -> String {
        let (medial, nucleus, coda) = self.rime();
        format!("{medial}+{nucleus}+{coda}")
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct Boundaries {
    pub word_end: bool,
    pub phrase_end: bool,
    pub sentence_end: bool,
}

impl Default for Boundaries {
    fn default() -> Self {
        Self {
            word_end: true,
            phrase_end: false,
            sentence_end: false,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct ParsedSyllable {
    pub raw: String,
    pub normalized: String,
    pub orthography: Orthography,
    #[serde(rename = "abstract")]
    pub abstract_: AbstractSyllable,
    pub boundaries: Boundaries,
    pub status: ParseStatus,
    pub confidence: f32,
    pub punctuation: Option<String>,
}

// Python dùng tên `abstract`; Rust không thể đặt field `abstract` (từ khoá).
// Serde đổi tên để JSON vẫn khớp schema Python.
impl ParsedSyllable {
    pub fn abstract_syllable(&self) -> &AbstractSyllable {
        &self.abstract_
    }
}
