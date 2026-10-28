//! Cách đọc riêng theo token, tương đương `frontend/custom_reading.py`.
//!
//! Bảng mặc định được nhúng nhưng **không tự nạp** trong profile live; caller
//! truyền bảng nếu muốn (xem `ParseOptions`).

use std::collections::HashMap;
use std::sync::OnceLock;

use fancy_regex::RegexBuilder;

pub fn embedded_custom_map() -> &'static HashMap<String, String> {
    static CACHE: OnceLock<HashMap<String, String>> = OnceLock::new();
    CACHE.get_or_init(|| {
        serde_json::from_str(include_str!("../resources/custom_reading.json"))
            .expect("custom_reading.json không hợp lệ")
    })
}

pub fn apply_custom_reading(text: &str, table: Option<&HashMap<String, String>>) -> String {
    let Some(table) = table else {
        return text.to_string();
    };
    if table.is_empty() {
        return text.to_string();
    }
    let mut keys: Vec<&String> = table.keys().collect();
    keys.sort_by(|a, b| {
        b.chars()
            .count()
            .cmp(&a.chars().count())
            .then_with(|| a.cmp(b))
    });
    let pattern = keys
        .iter()
        .map(|key| regex::escape(key))
        .collect::<Vec<_>>()
        .join("|");
    let pattern = format!(r"(?<![\p{{L}}\p{{N}}_])({pattern})(?![\p{{L}}\p{{N}}_])");
    let Ok(regex) = RegexBuilder::new(&pattern).case_insensitive(true).build() else {
        return text.to_string();
    };
    regex
        .replace_all(text, |caps: &fancy_regex::Captures<'_>| {
            let matched = caps.get(0).map(|m| m.as_str()).unwrap_or("");
            table
                .get(&matched.to_lowercase())
                .cloned()
                .unwrap_or_else(|| matched.to_string())
        })
        .into_owned()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn table() -> HashMap<String, String> {
        [
            ("vba", "vi be a"),
            ("vb", "vi be"),
            ("vps", "vi pi ét"),
            ("ps", "pi ét"),
            ("vs", "vi ét"),
            ("ch", "xê hát"),
        ]
        .into_iter()
        .map(|(a, b)| (a.to_string(), b.to_string()))
        .collect()
    }

    #[test]
    fn longest_first_and_boundaries() {
        let table = table();
        assert_eq!(
            apply_custom_reading("Dùng VBA để mở", Some(&table)),
            "Dùng vi be a để mở"
        );
        assert_eq!(
            apply_custom_reading("PS và VPS khác nhau", Some(&table)),
            "pi ét và vi pi ét khác nhau"
        );
        assert_eq!(apply_custom_reading("VPSX", Some(&table)), "VPSX");
        assert_eq!(apply_custom_reading("(VPS)", Some(&table)), "(vi pi ét)");
    }
}
