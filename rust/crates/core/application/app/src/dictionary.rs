//! Parse/validate từ điển local dạng `key = cách đọc`.

use std::collections::{BTreeMap, HashSet};

use serde::{Deserialize, Serialize};
use vifasttts_text::dialect::Dialect;
use vifasttts_text::pipeline::{live_parse_options, parse_text};
use vifasttts_text::types::ParseStatus;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DictionaryRule {
    pub key: String,
    pub value: String,
    pub line: usize,
}

#[derive(Clone, Debug, Default)]
pub struct Dictionary {
    pub rules: Vec<DictionaryRule>,
    pub warnings: Vec<String>,
}

impl Dictionary {
    pub fn overrides(&self) -> BTreeMap<String, String> {
        self.rules
            .iter()
            .map(|rule| (rule.key.clone(), rule.value.clone()))
            .collect()
    }

    pub fn to_json(&self) -> Result<String, String> {
        serde_json::to_string(&self.overrides())
            .map_err(|error| format!("serialize dictionary: {error}"))
    }
}

/// Parse từng dòng:
/// - bỏ dòng trống/`#`;
/// - tách ở dấu `=` đầu tiên;
/// - cảnh báo key/value rỗng, trùng key, value fallback.
pub fn parse_dictionary(input: &str) -> Dictionary {
    let mut dictionary = Dictionary::default();
    let mut seen = HashSet::new();
    let parse_options = live_parse_options(Dialect::North, None, None);
    for (index, raw_line) in input.lines().enumerate() {
        let line_number = index + 1;
        let line = raw_line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let Some((key, value)) = line.split_once('=') else {
            dictionary
                .warnings
                .push(format!("dòng {line_number}: thiếu dấu ="));
            continue;
        };
        let key = key.trim();
        let value = value.trim();
        if key.is_empty() || value.is_empty() {
            dictionary
                .warnings
                .push(format!("dòng {line_number}: key/value rỗng"));
            continue;
        }
        if !seen.insert(key.to_string()) {
            dictionary
                .warnings
                .push(format!("dòng {line_number}: key `{key}` bị trùng"));
        }
        let items = parse_text(value, &parse_options);
        if items.is_empty() {
            dictionary.warnings.push(format!(
                "dòng {line_number}: value `{value}` không parse được"
            ));
        } else if items
            .iter()
            .any(|item| item.status == ParseStatus::FallbackRequired)
        {
            dictionary.warnings.push(format!(
                "dòng {line_number}: `{value}` có âm tiết fallback; audio có thể đọc khác"
            ));
        }
        dictionary.rules.push(DictionaryRule {
            key: key.to_string(),
            value: value.to_string(),
            line: line_number,
        });
    }
    dictionary
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_comments_duplicates_and_warns_fallback() {
        let dictionary = parse_dictionary(
            "# comment\nAI = ây ai\nVPS = vi pi ét\nAI = ây ai lần hai\nxyzabc = zét\n",
        );
        assert_eq!(dictionary.rules.len(), 4);
        assert!(
            dictionary
                .warnings
                .iter()
                .any(|line| line.contains("bị trùng"))
        );
        assert!(
            dictionary
                .warnings
                .iter()
                .any(|line| line.contains("fallback"))
        );
        assert_eq!(
            dictionary.overrides().get("AI"),
            Some(&"ây ai lần hai".to_string())
        );
    }
}
