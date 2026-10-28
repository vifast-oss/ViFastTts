//! Bảng chính tả ↔ âm vị, tương đương `frontend/rules.py`.

use crate::types::Tone;

/// Thứ tự longest-match quan trọng: giữ đúng như Python.
pub const ONSET_SPELLINGS: &[&str] = &[
    "ngh", "ng", "gh", "gi", "kh", "nh", "ph", "th", "tr", "ch", "qu", "b", "c", "d", "đ", "g",
    "h", "k", "l", "m", "n", "p", "r", "s", "t", "v", "x",
];

pub fn onset_abstract(spelling: &str) -> Option<&'static str> {
    Some(match spelling {
        "" => "NONE",
        "b" => "B",
        "m" => "M",
        "ph" => "PH",
        "v" => "V",
        "t" => "T",
        "th" => "TH",
        "đ" => "Đ",
        "n" => "N",
        "d" => "D",
        "gi" => "GI",
        "r" => "R",
        "x" => "X",
        "s" => "S",
        "ch" => "CH",
        "tr" => "TR",
        "nh" => "NH",
        "l" => "L",
        "c" | "k" => "K",
        "qu" => "Q",
        "kh" => "KH",
        "ng" | "ngh" => "NG",
        "g" | "gh" => "G",
        "h" => "H",
        "p" => "P",
        _ => return None,
    })
}

pub const CONSONANT_CODAS: &[&str] = &["nh", "ng", "ch", "m", "n", "p", "t", "c"];

pub fn coda_abstract(spelling: &str) -> Option<&'static str> {
    Some(match spelling {
        "" => "NONE",
        "m" => "M",
        "n" => "N",
        "ng" => "NG",
        "nh" => "NH",
        "p" => "P",
        "t" => "T",
        "c" => "C",
        "ch" => "CH",
        "i" | "y" => "J",
        "u" | "o" => "W",
        _ => return None,
    })
}

pub fn nucleus_abstract(spelling: &str) -> Option<&'static str> {
    Some(match spelling {
        "a" => "A",
        "ă" => "Ă",
        "â" => "Â",
        "e" => "E",
        "ê" => "Ê",
        "i" | "y" => "I",
        "o" => "O",
        "ô" => "Ô",
        "ơ" => "Ơ",
        "u" => "U",
        "ư" => "Ư",
        "oo" => "OO",
        "iê" | "yê" | "ia" | "ya" => "IÊ",
        "uô" | "ua" => "UÔ",
        "ươ" | "ưa" => "ƯƠ",
        _ => return None,
    })
}

/// (chính tả âm đệm, chính tả âm chính), dài trước.
pub const SPECIAL_VOWELS: &[(&str, (&str, &str))] = &[
    ("uya", ("u", "ya")),
    ("uyê", ("u", "yê")),
    ("oa", ("o", "a")),
    ("oă", ("o", "ă")),
    ("oe", ("o", "e")),
    ("uâ", ("u", "â")),
    ("uê", ("u", "ê")),
    ("uy", ("u", "y")),
    ("uơ", ("u", "ơ")),
];

pub fn special_vowel(spelling: &str) -> Option<(&'static str, &'static str)> {
    SPECIAL_VOWELS
        .iter()
        .find(|(key, _)| *key == spelling)
        .map(|(_, value)| *value)
}

pub const STOP_CODAS: &[&str] = &["P", "T", "C", "CH"];

pub fn stop_coda(coda: &str) -> bool {
    STOP_CODAS.contains(&coda)
}

pub fn medial_nucleus_compatible(medial: &str, nucleus: &str) -> bool {
    match medial {
        "NONE" => matches!(
            nucleus,
            "A" | "Ă"
                | "Â"
                | "E"
                | "Ê"
                | "I"
                | "O"
                | "Ô"
                | "Ơ"
                | "U"
                | "Ư"
                | "IÊ"
                | "UÔ"
                | "ƯƠ"
                | "OO"
        ),
        "W" => matches!(nucleus, "A" | "Ă" | "Â" | "E" | "Ê" | "I" | "Ơ" | "IÊ"),
        _ => false,
    }
}

pub fn coda_tone_compatible(coda: &str, tone: Tone) -> bool {
    match coda {
        "P" | "T" | "C" | "CH" => matches!(tone, Tone::Sac | Tone::Nang),
        "NONE" | "M" | "N" | "NG" | "NH" | "J" | "W" => true,
        _ => false,
    }
}
