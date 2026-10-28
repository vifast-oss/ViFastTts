//! Chuẩn hoá Unicode giống `frontend/unicode.py`.

use unicode_normalization::UnicodeNormalization;

pub fn normalize_unicode(text: &str) -> String {
    let nfc: String = text.nfc().collect();
    let replaced = nfc
        .replace('…', "...")
        .replace(['“', '”'], "\"")
        .replace(['‘', '’'], "'");
    replaced.split_whitespace().collect::<Vec<_>>().join(" ")
}

pub fn nfc(text: &str) -> String {
    text.nfc().collect()
}

pub fn nfd(text: &str) -> String {
    text.nfd().collect()
}
