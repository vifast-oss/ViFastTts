//! Bóc/ghép dấu thanh, tương đương `frontend/tone.py`.

use crate::types::Tone;
use crate::unicode::{nfc, nfd};
use unicode_ccc::{CanonicalCombiningClass, get_canonical_combining_class};

fn tone_mark(ch: char) -> Option<Tone> {
    Some(match ch {
        '\u{0301}' => Tone::Sac,
        '\u{0300}' => Tone::Huyen,
        '\u{0309}' => Tone::Hoi,
        '\u{0303}' => Tone::Nga,
        '\u{0323}' => Tone::Nang,
        _ => return None,
    })
}

/// Trả (chuỗi đã bỏ dấu thanh, thanh, nguyên âm mang thanh).
pub fn extract_tone(syllable: &str) -> Result<(String, Tone, Option<String>), String> {
    let decomposed = nfd(syllable);
    let mut result = String::with_capacity(syllable.len());
    let mut tone = Tone::Ngang;
    let mut tone_location: Option<String> = None;
    let mut last_base: Option<char> = None;
    let mut seen: Vec<Tone> = Vec::new();

    for ch in decomposed.chars() {
        if get_canonical_combining_class(ch) == CanonicalCombiningClass::NotReordered {
            last_base = Some(ch);
            result.push(ch);
            continue;
        }
        if let Some(found) = tone_mark(ch) {
            if !seen.contains(&found) {
                seen.push(found);
            }
            tone = found;
            tone_location = last_base.map(|c| c.to_string());
        } else {
            result.push(ch);
        }
    }

    if seen.len() > 1 {
        return Err(format!("Âm tiết có nhiều dấu thanh: {syllable:?}"));
    }
    Ok((nfc(&result), tone, tone_location))
}

pub const TONE_COMBINING: [(Tone, &str); 6] = [
    (Tone::Ngang, ""),
    (Tone::Huyen, "\u{0300}"),
    (Tone::Sac, "\u{0301}"),
    (Tone::Hoi, "\u{0309}"),
    (Tone::Nga, "\u{0303}"),
    (Tone::Nang, "\u{0323}"),
];

pub fn tone_combining(tone: Tone) -> &'static str {
    TONE_COMBINING
        .iter()
        .find(|(value, _)| *value == tone)
        .map(|(_, mark)| *mark)
        .unwrap_or("")
}
