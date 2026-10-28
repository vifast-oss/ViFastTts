//! OOV resolver, tương đương `frontend/oov.py`.

use std::collections::HashMap;
use std::sync::OnceLock;

use crate::english::{lookup_case_insensitive_english, lookup_exact_acronym, lookup_product_name};

fn letters() -> &'static HashMap<String, String> {
    static CACHE: OnceLock<HashMap<String, String>> = OnceLock::new();
    CACHE.get_or_init(|| {
        serde_json::from_str(include_str!("../resources/letter_readings.json"))
            .expect("letter_readings.json không hợp lệ")
    })
}

fn py_isupper(value: &str) -> bool {
    let mut cased = false;
    for ch in value.chars() {
        if ch.is_lowercase() {
            return false;
        }
        if ch.is_uppercase() {
            cased = true;
        }
    }
    cased
}

fn py_isdigit(ch: char) -> bool {
    // Bao phủ ASCII + digit Unicode phổ biến; `to_digit` chỉ nhận ASCII,
    // nên dùng numeric cho gần Python `str.isdigit`.
    ch.is_numeric()
}

pub fn spell_token(token: &str) -> String {
    let table = letters();
    let mut output: Vec<&str> = Vec::new();
    for ch in token.chars() {
        let lower = ch.to_lowercase().collect::<String>();
        if let Some(reading) = table.get(&lower) {
            output.push(reading);
        }
    }
    output.join(" ")
}

pub fn resolve_oov_token(token: &str) -> Option<String> {
    if let Some(reading) = lookup_exact_acronym(token)
        .or_else(|| lookup_product_name(token))
        .or_else(|| lookup_case_insensitive_english(token))
    {
        return Some(reading);
    }

    let chars: Vec<char> = token.chars().collect();
    let letters_only: String = chars.iter().filter(|ch| ch.is_alphabetic()).collect();
    let mixed = letters_only.chars().count() != chars.len();
    let all_known = !letters_only.is_empty()
        && letters_only
            .chars()
            .all(|ch| letters().contains_key(&ch.to_lowercase().collect::<String>()));
    if all_known && (py_isupper(token) || mixed || letters_only.chars().count() <= 4) {
        let spelled = spell_token(&letters_only);
        let digits: String = chars.iter().filter(|ch| py_isdigit(**ch)).collect();
        return Some(if digits.is_empty() {
            spelled
        } else {
            format!("{spelled} {digits}")
        });
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn spells_short_upper() {
        assert_eq!(resolve_oov_token("VNG").as_deref(), Some("vê en giê"));
        assert_eq!(resolve_oov_token("wav").as_deref(), Some("vê kép a vê"));
    }
}
