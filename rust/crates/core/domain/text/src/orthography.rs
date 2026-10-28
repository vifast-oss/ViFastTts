//! Ghép chính tả canonical, tương đương `frontend/orthography.py`.

use crate::tone::tone_combining;
use crate::types::Tone;
use crate::unicode::{nfc, nfd};

fn tone_target(nucleus: &str) -> usize {
    let lower = nucleus.to_lowercase();
    if lower == "oo" {
        return 1;
    }
    if matches!(lower.as_str(), "ia" | "ya" | "ua" | "ưa") {
        return 0;
    }
    for wanted in "êôơưăâÊÔƠƯĂÂ".chars() {
        if let Some(index) = nucleus.chars().position(|c| c == wanted) {
            return index;
        }
    }
    for wanted in "aAeEoOiIuUyY".chars() {
        if let Some(index) = nucleus.chars().position(|c| c == wanted) {
            return index;
        }
    }
    0
}

pub fn apply_tone(nucleus: &str, tone: Tone) -> String {
    if tone == Tone::Ngang {
        return nucleus.to_string();
    }
    let index = tone_target(nucleus);
    let chars: Vec<char> = nucleus.chars().collect();
    if index >= chars.len() {
        return nucleus.to_string();
    }
    let base = chars[index];
    let composed = nfc(&format!(
        "{}{}",
        nfd(&base.to_string()),
        tone_combining(tone)
    ));
    let mut output = String::with_capacity(nucleus.len() + 2);
    for (position, ch) in chars.iter().enumerate() {
        if position == index {
            output.push_str(&composed);
        } else {
            output.push(*ch);
        }
    }
    output
}

pub fn compose_canonical(
    onset: Option<&str>,
    medial: Option<&str>,
    nucleus: &str,
    coda: Option<&str>,
    tone: Tone,
) -> String {
    let onset = onset.unwrap_or("");
    let written_medial = if onset == "qu" {
        ""
    } else {
        medial.unwrap_or("")
    };
    format!(
        "{onset}{written_medial}{}{}",
        apply_tone(nucleus, tone),
        coda.unwrap_or("")
    )
}
