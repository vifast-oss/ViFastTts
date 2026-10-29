//! Đường ống parse văn bản, tương đương `frontend/pipeline.py`.

use std::collections::HashMap;

use crate::custom_reading::apply_custom_reading;
use crate::dialect::Dialect;
use crate::normalizer::{NormalizerOptions, normalize_text};
use crate::oov::resolve_oov_token;
use crate::syllable::safe_parse_syllable;
use crate::types::{AbstractSyllable, Boundaries, Orthography, ParseStatus, ParsedSyllable, Tone};

#[derive(Clone, Debug)]
pub struct ParseOptions {
    pub normalizer: NormalizerOptions,
    pub resolve_oov: bool,
    /// `None` = profile live (không nạp custom reading local).
    pub custom_reading: Option<HashMap<String, String>>,
}

impl ParseOptions {
    pub fn new(dialect: Dialect) -> Self {
        Self {
            normalizer: NormalizerOptions {
                dialect,
                ..NormalizerOptions::default()
            },
            resolve_oov: false,
            custom_reading: None,
        }
    }

    pub fn with_resolve_oov(mut self, value: bool) -> Self {
        self.resolve_oov = value;
        self
    }

    pub fn with_custom_reading(mut self, table: HashMap<String, String>) -> Self {
        self.custom_reading = Some(table);
        self
    }
}

impl Default for ParseOptions {
    fn default() -> Self {
        Self::new(Dialect::North)
    }
}

fn is_word_char(ch: char) -> bool {
    ch.is_alphanumeric() || ch == '_'
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum Token {
    Word(String),
    Punctuation(String),
}

fn tokenize(text: &str) -> Vec<Token> {
    let mut tokens = Vec::new();
    let mut current = String::new();
    for ch in text.chars() {
        if ch.is_whitespace() {
            if !current.is_empty() {
                tokens.push(Token::Word(std::mem::take(&mut current)));
            }
            continue;
        }
        if is_word_char(ch) {
            current.push(ch);
        } else {
            if !current.is_empty() {
                tokens.push(Token::Word(std::mem::take(&mut current)));
            }
            tokens.push(Token::Punctuation(ch.to_string()));
        }
    }
    if !current.is_empty() {
        tokens.push(Token::Word(current));
    }
    tokens
}

fn fallback_syllable(token: &str) -> ParsedSyllable {
    ParsedSyllable {
        raw: token.to_string(),
        normalized: token.to_lowercase(),
        orthography: Orthography {
            onset: None,
            medial: None,
            nucleus: token.to_string(),
            coda: None,
            tone_location: None,
        },
        abstract_: AbstractSyllable {
            onset: "NONE".to_string(),
            medial: "NONE".to_string(),
            nucleus: "A".to_string(),
            coda: "NONE".to_string(),
            tone: Tone::Ngang,
        },
        boundaries: Boundaries::default(),
        status: ParseStatus::FallbackRequired,
        confidence: 0.0,
        punctuation: None,
    }
}

/// Chuẩn hoá đúng như bước đầu của `parse_text` (custom reading + normalizer).
pub fn normalize_input(text: &str, options: &ParseOptions) -> String {
    let with_custom = apply_custom_reading(text, options.custom_reading.as_ref());
    normalize_text(
        &with_custom,
        options.normalizer.dialect,
        Some(&options.normalizer),
    )
}

fn parse_inner(text: &str, options: &ParseOptions, depth: usize) -> Vec<ParsedSyllable> {
    if depth > 8 {
        return vec![fallback_syllable(text)];
    }
    let normalized = normalize_input(text, options);
    parse_normalized_inner(&normalized, options, depth)
}

/// Parse văn bản đã chuẩn hoá (tránh normalize hai lần trong tool parity).
pub fn parse_normalized(normalized: &str, options: &ParseOptions) -> Vec<ParsedSyllable> {
    parse_normalized_inner(normalized, options, 0)
}

fn parse_normalized_inner(
    normalized: &str,
    options: &ParseOptions,
    depth: usize,
) -> Vec<ParsedSyllable> {
    let mut output: Vec<ParsedSyllable> = Vec::new();
    let mut pending_punctuation = String::new();

    for token in tokenize(normalized) {
        match token {
            Token::Punctuation(punctuation) => {
                if let Some(last) = output.last_mut() {
                    let existing = last.punctuation.take().unwrap_or_default();
                    last.punctuation = Some(existing + &punctuation);
                    if punctuation.chars().any(|ch| ".!?".contains(ch)) {
                        last.boundaries = Boundaries {
                            word_end: true,
                            phrase_end: true,
                            sentence_end: true,
                        };
                    } else if punctuation.chars().any(|ch| ",;:".contains(ch)) {
                        last.boundaries = Boundaries {
                            word_end: true,
                            phrase_end: true,
                            sentence_end: false,
                        };
                    }
                } else {
                    pending_punctuation.push_str(&punctuation);
                }
            }
            Token::Word(token) => {
                let parsed = safe_parse_syllable(&token);
                let mut items = if parsed.is_none() && options.resolve_oov {
                    resolve_oov_token(&token)
                        .map(|respelled| {
                            let mut expanded = parse_inner(&respelled, options, depth + 1);
                            for item in &mut expanded {
                                item.raw = token.clone();
                                item.confidence = item.confidence.min(0.5);
                            }
                            expanded
                        })
                        .unwrap_or_default()
                } else {
                    Vec::new()
                };
                if items.is_empty() {
                    items.push(parsed.unwrap_or_else(|| fallback_syllable(&token)));
                }
                if !pending_punctuation.is_empty() {
                    let first = &mut items[0];
                    let existing = first.punctuation.take().unwrap_or_default();
                    first.punctuation = Some(pending_punctuation.clone() + &existing);
                    pending_punctuation.clear();
                }
                output.extend(items);
            }
        }
    }
    output
}

fn is_word_key(key: &str) -> bool {
    !key.is_empty()
        && key.chars().all(|ch| {
            ch.is_ascii_alphabetic()
                || ('\u{00C0}'..='\u{1EF9}').contains(&ch)
                || ch == 'Đ'
                || ch == 'đ'
        })
}

/// Bảng đọc có sẵn đang live (229 mục), sinh từ Python.
pub fn builtin_overrides() -> &'static HashMap<String, String> {
    static CACHE: std::sync::OnceLock<HashMap<String, String>> = std::sync::OnceLock::new();
    CACHE.get_or_init(|| {
        serde_json::from_str(include_str!("../resources/overrides_vi.json"))
            .expect("overrides_vi.json không hợp lệ")
    })
}

/// Cấu hình parse giống demo production: builtin + approved + user override.
pub fn live_parse_options(
    dialect: Dialect,
    user_overrides: Option<&HashMap<String, String>>,
    approved_overrides: Option<&HashMap<String, String>>,
) -> ParseOptions {
    let builtin = builtin_overrides();
    let mut exact = HashMap::new();
    let mut english = HashMap::new();
    for (key, value) in builtin {
        if !is_word_key(key) {
            exact.insert(key.clone(), value.clone());
        }
        english.insert(key.to_lowercase(), value.clone());
    }
    for map in [approved_overrides, user_overrides].into_iter().flatten() {
        for (key, value) in map {
            exact.insert(key.clone(), value.clone());
            if key.is_ascii() {
                english.insert(key.to_lowercase(), value.clone());
            }
        }
    }
    let mut options = ParseOptions::new(dialect);
    options.normalizer.exact_overrides = exact;
    options.normalizer.english_overrides = english;
    options
}

pub fn parse_text(text: &str, options: &ParseOptions) -> Vec<ParsedSyllable> {
    parse_inner(text, options, 0)
}

pub fn parse_text_default(text: &str) -> Vec<ParsedSyllable> {
    parse_text(text, &ParseOptions::default())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_sentence_and_punctuation() {
        let items = parse_text_default("Chào, bạn!");
        assert_eq!(items.len(), 2);
        assert!(items[0].boundaries.phrase_end);
        assert!(items[1].boundaries.sentence_end);
        assert_eq!(items[0].punctuation.as_deref(), Some(","));
        assert_eq!(items[1].punctuation.as_deref(), Some("!"));
    }

    #[test]
    fn ios_uses_english_reading() {
        let options = live_parse_options(Dialect::North, None, None);
        assert_eq!(normalize_input("iOS", &options), "ai âu ét");
    }

    #[test]
    fn android_uses_natural_reading() {
        let options = live_parse_options(Dialect::North, None, None);
        assert_eq!(normalize_input("Android", &options), "an đờ roi");
    }

    #[test]
    fn vifasttts_uses_custom_reading() {
        let options = live_parse_options(Dialect::North, None, None);
        assert_eq!(normalize_input("ViFastTts", &options), "vi phát tê tê ét");
    }

    #[test]
    fn fallback_encodable() {
        let items = parse_text_default("Zibble");
        assert_eq!(items.len(), 1);
        assert_eq!(items[0].status, ParseStatus::FallbackRequired);
    }
}
