//! Chuẩn hoá văn bản, tương đương `frontend/normalizer.py`.
//!
//! Thứ tự xử lý là hợp đồng: đổi thứ tự sẽ đổi audio. Các regex dùng
//! `fancy-regex` vì Python dùng lookbehind/lookahead; nội dung pattern giữ
//! nguyên bản Python.

use std::collections::HashMap;
use std::sync::{OnceLock, RwLock};

use fancy_regex::{Captures, Regex, RegexBuilder};
use num_bigint::BigInt;
use num_traits::{ToPrimitive, Zero};

use crate::dialect::{Dialect, ReadingProfile, get_profile};
use crate::english::{lookup_case_insensitive_english, lookup_exact_acronym, lookup_product_name};
use crate::orthography::compose_canonical;
use crate::roman::roman_to_int;
use crate::syllable::safe_parse_syllable;
use crate::unicode::normalize_unicode;

const SMALL: [&str; 10] = [
    "không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín",
];

#[derive(Clone, Debug)]
pub struct NormalizerOptions {
    pub dialect: Dialect,
    pub canonical_tone_spelling: bool,
    pub english_fallback: bool,
    pub roman_numerals: bool,
    pub stem_formulas: bool,
    pub exact_overrides: HashMap<String, String>,
    pub english_overrides: HashMap<String, String>,
}

impl Default for NormalizerOptions {
    fn default() -> Self {
        Self {
            dialect: Dialect::North,
            canonical_tone_spelling: true,
            english_fallback: true,
            roman_numerals: true,
            stem_formulas: true,
            exact_overrides: HashMap::new(),
            english_overrides: HashMap::new(),
        }
    }
}

fn regex(pattern: &str) -> &'static Regex {
    static CACHE: OnceLock<RwLock<HashMap<String, &'static Regex>>> = OnceLock::new();
    let cache = CACHE.get_or_init(|| RwLock::new(HashMap::new()));
    if let Some(found) = cache.read().expect("regex cache").get(pattern) {
        return found;
    }
    let compiled =
        Box::leak(Box::new(Regex::new(pattern).unwrap_or_else(|err| {
            panic!("regex frontend không hợp lệ: {err}: {pattern}")
        })));
    cache
        .write()
        .expect("regex cache")
        .insert(pattern.to_string(), compiled);
    compiled
}

fn big(value: i64) -> BigInt {
    BigInt::from(value)
}

fn to_u32(value: &BigInt) -> u32 {
    value.to_u32().expect("nhóm số < 1000")
}

fn small(value: u32) -> &'static str {
    SMALL[value as usize]
}

fn under_100(n: u32, p: ReadingProfile) -> String {
    if n < 10 {
        return small(n).to_string();
    }
    let q = n / 10;
    let r = n % 10;
    let prefix = if q == 1 {
        "mười".to_string()
    } else {
        format!("{} mươi", small(q))
    };
    if r == 0 {
        return prefix;
    }
    let tail = if r == 1 && q > 1 {
        "mốt"
    } else if r == 4 && q > 1 {
        p.four_after_tens
    } else if r == 5 {
        "lăm"
    } else {
        small(r)
    };
    format!("{prefix} {tail}")
}

fn under_1000(n: u32, p: ReadingProfile) -> String {
    if n < 100 {
        return under_100(n, p);
    }
    let q = n / 100;
    let r = n % 100;
    let prefix = format!("{} trăm", small(q));
    if r == 0 {
        return prefix;
    }
    if r < 10 {
        return format!("{prefix} {} {}", p.zero_tens, small(r));
    }
    format!("{prefix} {}", under_100(r, p))
}

fn read_group(g: u32, p: ReadingProfile, started: bool) -> String {
    if started && g < 100 {
        if g < 10 {
            return format!("không trăm {} {}", p.zero_tens, small(g));
        }
        return format!("không trăm {}", under_100(g, p));
    }
    under_1000(g, p)
}

fn read_below_billion(n: &BigInt, p: ReadingProfile, mut started: bool) -> String {
    let mut groups = Vec::new();
    let mut current = n.clone();
    let thousand = big(1000);
    while current > BigInt::zero() {
        let r = &current % &thousand;
        groups.push(to_u32(&r));
        current /= &thousand;
    }
    let scales = ["", p.thousand, "triệu"];
    let mut parts = Vec::new();
    for index in (0..groups.len()).rev() {
        let g = groups[index];
        if g == 0 {
            continue;
        }
        let text = read_group(g, p, started);
        let scale = scales.get(index).copied().unwrap_or("");
        parts.push(format!("{text} {scale}").trim().to_string());
        started = true;
    }
    parts.join(" ")
}

pub fn integer_to_words(value: &BigInt, dialect: Dialect) -> String {
    let p = get_profile(dialect);
    if value < &BigInt::zero() {
        return format!("âm {}", integer_to_words(&(-value), dialect));
    }
    read_number(value, p)
}

fn read_number(value: &BigInt, p: ReadingProfile) -> String {
    if value.is_zero() {
        return SMALL[0].to_string();
    }
    let billion = big(1_000_000_000);
    if value >= &billion {
        let high = value / &billion;
        let rest = value % &billion;
        let mut text = format!("{} tỷ", read_number(&high, p));
        if !rest.is_zero() {
            text.push(' ');
            text.push_str(&read_below_billion(&rest, p, true));
        }
        return text;
    }
    read_below_billion(value, p, false)
}

fn parse_big(value: &str) -> Option<BigInt> {
    value.parse::<BigInt>().ok()
}

pub fn integer_str_to_words(value: &str, dialect: Dialect) -> String {
    parse_big(value)
        .map(|n| integer_to_words(&n, dialect))
        .unwrap_or_else(|| value.to_string())
}

pub fn decimal_to_words(value: &str, dialect: Dialect) -> String {
    let split = value
        .char_indices()
        .find(|(_, ch)| *ch == ',' || *ch == '.')
        .map(|(index, _)| index);
    let Some(index) = split else {
        return integer_str_to_words(value, dialect);
    };
    let left = &value[..index];
    let right = &value[index + 1..];
    let digits = right
        .chars()
        .filter_map(|ch| ch.to_digit(10))
        .map(|d| SMALL[d as usize])
        .collect::<Vec<_>>()
        .join(" ");
    format!("{} phẩy {digits}", integer_str_to_words(left, dialect))
}

fn phone_to_words(text: &str) -> String {
    let mut digits: String = text.chars().filter(|ch| ch.is_ascii_digit()).collect();
    if digits.starts_with("84") && digits.len() >= 11 {
        digits = format!("0{}", &digits[2..]);
    }
    digits
        .chars()
        .filter_map(|ch| ch.to_digit(10))
        .map(|d| SMALL[d as usize])
        .collect::<Vec<_>>()
        .join(" ")
}

fn currency_number_to_words(value: &str, dialect: Dialect) -> String {
    if value.contains(',') || value.contains('.') {
        decimal_to_words(value, dialect)
    } else {
        integer_str_to_words(value, dialect)
    }
}

fn integer_token_to_words(raw: &str, dialect: Dialect) -> String {
    if raw.len() > 1 && raw.starts_with('0') {
        return raw
            .chars()
            .filter_map(|ch| ch.to_digit(10))
            .map(|d| SMALL[d as usize])
            .collect::<Vec<_>>()
            .join(" ");
    }
    integer_str_to_words(raw, dialect)
}

fn hour_minute_words(hour: u32, minute: u32, dialect: Dialect) -> String {
    let p = get_profile(dialect);
    let mut parts = vec![format!(
        "{} giờ",
        integer_to_words(&big(hour as i64), dialect)
    )];
    if minute > 0 {
        let tail = integer_to_words(&big(minute as i64), dialect);
        if minute < 10 {
            parts.push(format!("{} {} phút", p.zero_tens, tail));
        } else {
            parts.push(format!("{tail} phút"));
        }
    }
    parts.join(" ")
}

fn date_to_words(caps: &Captures<'_>, dialect: Dialect) -> String {
    let day = caps.get(1).map(|m| m.as_str()).unwrap_or("");
    let month = caps.get(3).map(|m| m.as_str()).unwrap_or("");
    let year = caps.get(4).map(|m| m.as_str()).unwrap_or("");
    let (Ok(day), Ok(month)) = (day.parse::<u32>(), month.parse::<u32>()) else {
        return caps.get(0).map(|m| m.as_str()).unwrap_or("").to_string();
    };
    if !(1..=31).contains(&day) || !(1..=12).contains(&month) {
        return caps.get(0).map(|m| m.as_str()).unwrap_or("").to_string();
    }
    format!(
        "ngày {} tháng {} năm {}",
        integer_to_words(&big(day as i64), dialect),
        integer_to_words(&big(month as i64), dialect),
        integer_str_to_words(year, dialect)
    )
}

fn time_to_words(caps: &Captures<'_>, dialect: Dialect) -> String {
    let hour = caps.get(1).and_then(|m| m.as_str().parse::<u32>().ok());
    let minute = caps.get(2).and_then(|m| m.as_str().parse::<u32>().ok());
    let (Some(hour), Some(minute)) = (hour, minute) else {
        return caps.get(0).map(|m| m.as_str()).unwrap_or("").to_string();
    };
    if hour > 23 || minute > 59 {
        return caps.get(0).map(|m| m.as_str()).unwrap_or("").to_string();
    }
    hour_minute_words(hour, minute, dialect)
}

fn fraction_to_words(caps: &Captures<'_>, dialect: Dialect) -> String {
    let left = caps.get(1).map(|m| m.as_str()).unwrap_or("0");
    let right = caps.get(2).map(|m| m.as_str()).unwrap_or("0");
    format!(
        "{} phần {}",
        integer_str_to_words(left, dialect),
        integer_str_to_words(right, dialect)
    )
}

fn number_token_to_words(value: &str, dialect: Dialect) -> String {
    if value.contains(',') || value.contains('.') {
        decimal_to_words(value, dialect)
    } else {
        integer_str_to_words(value, dialect)
    }
}

fn range_to_words(caps: &Captures<'_>, dialect: Dialect) -> String {
    let left = caps.get(1).map(|m| m.as_str()).unwrap_or("");
    let right = caps.get(2).map(|m| m.as_str()).unwrap_or("");
    let mut text = format!(
        "{} đến {}",
        number_token_to_words(left, dialect),
        number_token_to_words(right, dialect)
    );
    if caps.get(3).is_some() {
        text.push_str(" phần trăm");
    }
    text
}

fn is_viet_letter(ch: char) -> bool {
    ch.is_ascii_alphabetic() || ('\u{00C0}'..='\u{1EF9}').contains(&ch) || ch == 'Đ' || ch == 'đ'
}

fn is_phrase_override_key(key: &str) -> bool {
    !key.chars().all(is_viet_letter)
}

fn apply_phrase_overrides(text: &str, options: &NormalizerOptions) -> String {
    let mut rules: Vec<(String, String)> = options
        .exact_overrides
        .iter()
        .filter(|(key, _)| is_phrase_override_key(key))
        .map(|(key, value)| (normalize_unicode(key), normalize_unicode(value)))
        .collect();
    if rules.is_empty() {
        return text.to_string();
    }
    // Chỉ compile regex khi thật sự có key xuất hiện trong text. Với parser
    // matrix (toàn âm tiết không dấu chấm/space) bước này gần như luôn rỗng.
    let lowered = text.to_lowercase();
    rules.retain(|(key, _)| lowered.contains(&key.to_lowercase()));
    if rules.is_empty() {
        return text.to_string();
    }
    rules.sort_by_key(|(key, _)| std::cmp::Reverse(key.chars().count()));
    let pattern = rules
        .iter()
        .map(|(key, _)| format!(r"(?<![A-Za-z0-9])(?:{})(?![A-Za-z0-9])", regex::escape(key)))
        .collect::<Vec<_>>()
        .join("|");
    let regex = RegexBuilder::new(&pattern)
        .case_insensitive(true)
        .build()
        .expect("phrase override regex");
    let replacements: HashMap<String, String> = rules
        .iter()
        .map(|(key, value)| (key.to_lowercase(), value.clone()))
        .collect();
    regex
        .replace_all(text, |caps: &Captures<'_>| {
            let matched = caps.get(0).map(|m| m.as_str()).unwrap_or("");
            replacements
                .get(&matched.to_lowercase())
                .cloned()
                .unwrap_or_else(|| matched.to_string())
        })
        .into_owned()
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

fn canonicalize_vietnamese_token(token: &str) -> Option<String> {
    let item = safe_parse_syllable(token)?;
    let o = item.orthography;
    let a = item.abstract_;
    let mut result = compose_canonical(
        o.onset.as_deref(),
        o.medial.as_deref(),
        &o.nucleus,
        o.coda.as_deref(),
        a.tone,
    );
    if py_isupper(token) {
        result = result.to_uppercase();
    } else if token.chars().next().is_some_and(|ch| ch.is_uppercase()) {
        let mut chars = result.chars();
        if let Some(first) = chars.next() {
            result = first.to_uppercase().collect::<String>() + chars.as_str();
        }
    }
    Some(result)
}

pub fn normalize_word_token(token: &str, options: &NormalizerOptions) -> String {
    if let Some(value) = options.exact_overrides.get(token) {
        return value.clone();
    }
    if let Some(value) = lookup_exact_acronym(token) {
        return value;
    }
    if let Some(value) = lookup_product_name(token) {
        return value;
    }
    if options.roman_numerals
        && let Some(number) = roman_to_int(token)
    {
        return integer_to_words(&big(number as i64), options.dialect);
    }
    if let Some(value) = canonicalize_vietnamese_token(token) {
        return if options.canonical_tone_spelling {
            value
        } else {
            token.to_string()
        };
    }
    if options.english_fallback {
        if let Some(value) = options.english_overrides.get(&token.to_lowercase()) {
            return value.clone();
        }
        if let Some(value) = lookup_case_insensitive_english(token) {
            return value;
        }
    }
    token.to_string()
}

pub fn normalize_words(text: &str, options: &NormalizerOptions) -> String {
    let mut output = String::with_capacity(text.len());
    let mut current = String::new();
    let mut current_is_word = None;
    for ch in text.chars() {
        let is_word = is_viet_letter(ch);
        if current_is_word.is_none() || current_is_word == Some(is_word) {
            current.push(ch);
            current_is_word = Some(is_word);
        } else {
            if current_is_word == Some(true) {
                output.push_str(&normalize_word_token(&current, options));
            } else {
                output.push_str(&current);
            }
            current.clear();
            current.push(ch);
            current_is_word = Some(is_word);
        }
    }
    if !current.is_empty() {
        if current_is_word == Some(true) {
            output.push_str(&normalize_word_token(&current, options));
        } else {
            output.push_str(&current);
        }
    }
    output
}

fn hour_notation(caps: &Captures<'_>, dialect: Dialect) -> String {
    let hour = caps.get(1).and_then(|m| m.as_str().parse::<u32>().ok());
    let minute = caps
        .get(2)
        .and_then(|m| m.as_str().parse::<u32>().ok())
        .unwrap_or(0);
    hour.map(|h| hour_minute_words(h, minute, dialect))
        .unwrap_or_else(|| caps.get(0).map(|m| m.as_str()).unwrap_or("").to_string())
}

fn email_local_to_words(local: &str, options: &NormalizerOptions) -> String {
    let mut parts = Vec::new();
    for part in local.split('.') {
        if part.is_empty() {
            continue;
        }
        if let Some(canonical) = canonicalize_vietnamese_token(part) {
            parts.push(canonical);
            continue;
        }
        let reading = normalize_word_token(part, options);
        if reading != part {
            parts.push(reading);
            continue;
        }
        let letters: String = part.chars().filter(|ch| ch.is_alphabetic()).collect();
        let digits: String = part.chars().filter(|ch| ch.is_ascii_digit()).collect();
        let spelled = crate::oov::spell_token(&letters);
        let digit_words = digits
            .chars()
            .filter_map(|ch| ch.to_digit(10))
            .map(|d| SMALL[d as usize])
            .collect::<Vec<_>>()
            .join(" ");
        let combined = [spelled, digit_words]
            .into_iter()
            .filter(|value| !value.is_empty())
            .collect::<Vec<_>>()
            .join(" ");
        parts.push(combined);
    }
    parts.join(" chấm ")
}

pub fn normalize_text(text: &str, dialect: Dialect, options: Option<&NormalizerOptions>) -> String {
    let owned_options;
    let options = match options {
        Some(options) => options,
        None => {
            owned_options = NormalizerOptions {
                dialect,
                ..NormalizerOptions::default()
            };
            &owned_options
        }
    };
    let mut text = normalize_unicode(text);
    text = apply_phrase_overrides(&text, options);

    // Fast path: không có chữ số/ký hiệu toán/STEM thì các rule số-ngày-tiền
    // không thể khớp; chỉ cần canonicalize từ. Quan trọng cho parser matrix.
    let has_digit = text.chars().any(|ch| ch.is_ascii_digit());
    let has_special = text.chars().any(|ch| "\\$%@+=&<>×÷^_{}".contains(ch));
    if !has_digit && !has_special {
        return normalize_words(&text, options)
            .split_whitespace()
            .collect::<Vec<_>>()
            .join(" ");
    }

    let hour_re = regex(r"(?<![\p{L}\p{N}_])(\d{1,2})h(\d{2})?(?![\p{L}\p{N}_])");
    text = hour_re
        .replace_all(&text, |caps: &Captures<'_>| {
            hour_notation(caps, options.dialect)
        })
        .into_owned();

    if options.stem_formulas {
        text = crate::stem::normalize_stem(&text, &|n| integer_to_words(&big(n), options.dialect));
    }

    let thousand_dot = regex(r"(?<=\d)\.(?=\d{3}(?!\d))");
    text = thousand_dot.replace_all(&text, "").into_owned();
    let thousand_space = regex(r"(?<=\d) (?=\d{3}(?!\d))");
    text = thousand_space.replace_all(&text, "").into_owned();

    let date_re = regex(r"(?<![\d/.,-])(?:[Nn]gày\s+)?(\d{1,2})([/.-])(\d{1,2})\2(\d{4})(?!\d)");
    text = date_re
        .replace_all(&text, |caps: &Captures<'_>| {
            date_to_words(caps, options.dialect)
        })
        .into_owned();

    let time_re = regex(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)");
    text = time_re
        .replace_all(&text, |caps: &Captures<'_>| {
            time_to_words(caps, options.dialect)
        })
        .into_owned();

    let phone_re = regex(r"(?<![\p{L}\p{N}_])(?:\+84\d{9,10}|0\d{9,10})(?![\p{L}\p{N}_])");
    text = phone_re
        .replace_all(&text, |caps: &Captures<'_>| {
            phone_to_words(caps.get(0).unwrap().as_str())
        })
        .into_owned();

    let email_re = regex(
        r"(?<![\p{L}\p{N}_.+-])([A-Za-z0-9][\p{L}\p{N}_.+-]*?)@([\p{L}\p{N}_-]+(?:\.[\p{L}\p{N}_-]+)+)(?![\p{L}\p{N}_-])",
    );
    text = email_re
        .replace_all(&text, |caps: &Captures<'_>| {
            let local = caps.get(1).map(|m| m.as_str()).unwrap_or("");
            let domain = caps.get(2).map(|m| m.as_str()).unwrap_or("");
            format!(
                "{} a còng {}",
                email_local_to_words(local, options),
                domain.replace('.', " chấm ")
            )
        })
        .into_owned();

    let math_rules = [
        (r"(?<=\d)\s*\+\s*(?=\d)", " cộng "),
        (r"(?<=\d)\s*[x×]\s*(?=\d)", " nhân "),
        (r"(?<=\d)\s*÷\s*(?=\d)", " chia "),
        (
            r"(?<=[\p{L}\p{N}_])\s*(?<![=<>!])=(?!=)\s*(?=[\p{L}\p{N}_])",
            " bằng ",
        ),
        (r"(?<=[\p{L}\p{N}_])\s*&\s*(?=[\p{L}\p{N}_])", " và "),
        (
            r"(?<=[\p{L}\p{N}_%])\s*(?:>=|≥)\s*(?=[\p{L}\p{N}_])",
            " lớn hơn hoặc bằng ",
        ),
        (
            r"(?<=[\p{L}\p{N}_%])\s*(?:<=|≤)\s*(?=[\p{L}\p{N}_])",
            " nhỏ hơn hoặc bằng ",
        ),
        (r"(?<=[\p{L}\p{N}_%])\s*>\s*(?=[\p{L}\p{N}_])", " lớn hơn "),
        (r"(?<=[\p{L}\p{N}_%])\s*<\s*(?=[\p{L}\p{N}_])", " nhỏ hơn "),
    ];
    for (pattern, replacement) in math_rules {
        text = regex(pattern).replace_all(&text, replacement).into_owned();
    }

    #[allow(clippy::type_complexity)]
    let currency_rules: &[(&str, fn(&Captures<'_>, Dialect) -> String)] = &[
        (
            r"(?<![\p{L}\p{N}_])(\d+(?:[,.]\d+)?)\s*(?:đồng|đ|vnd|VND)(?![A-Za-zÀ-ỹĐđ])",
            |caps, dialect| {
                format!(
                    "{} đồng",
                    currency_number_to_words(caps.get(1).unwrap().as_str(), dialect)
                )
            },
        ),
        (
            r"(?<![\p{L}\p{N}_])(\d{4,}(?:[,.]\d+)?)\s*d(?![A-Za-zÀ-ỹĐđ])",
            |caps, dialect| {
                format!(
                    "{} đồng",
                    currency_number_to_words(caps.get(1).unwrap().as_str(), dialect)
                )
            },
        ),
        (r"\$\s*(\d+(?:[,.]\d+)?)", |caps, dialect| {
            format!(
                "{} đô la",
                currency_number_to_words(caps.get(1).unwrap().as_str(), dialect)
            )
        }),
        (
            r"(?<![\p{L}\p{N}_])(\d+(?:[,.]\d+)?)\s*\$(?![A-Za-zÀ-ỹĐđ])",
            |caps, dialect| {
                format!(
                    "{} đô la",
                    currency_number_to_words(caps.get(1).unwrap().as_str(), dialect)
                )
            },
        ),
    ];
    for (pattern, replacer) in currency_rules {
        text = regex(pattern)
            .replace_all(&text, |caps: &Captures<'_>| replacer(caps, options.dialect))
            .into_owned();
    }

    // "1/2%" phải đọc cả "phần trăm" trước khi rule phân số thường cắt mất "%".
    let fraction_percent_re = regex(r"(?<![\d/.,])(\d+)\s*/\s*(\d+)\s*%");
    text = fraction_percent_re
        .replace_all(&text, |caps: &Captures<'_>| {
            format!("{} phần trăm", fraction_to_words(caps, options.dialect))
        })
        .into_owned();

    // Cho phép khoảng trắng quanh "/" và dấu câu sau mẫu số, nhưng không
    // nhận "1/2.5" hay "1/2/2024".
    let fraction_re = regex(r"(?<![\d/.,])(\d+)\s*/\s*(\d+)(?![\d/]|[.,]\d)");
    text = fraction_re
        .replace_all(&text, |caps: &Captures<'_>| {
            fraction_to_words(caps, options.dialect)
        })
        .into_owned();

    let range_re =
        regex(r"(?<![\d.,-])(\d+(?:[.,]\d+)?)\s*[-–—]\s*(\d+(?:[.,]\d+)?)(?:\s*(%))?(?![\d.,])");
    text = range_re
        .replace_all(&text, |caps: &Captures<'_>| {
            range_to_words(caps, options.dialect)
        })
        .into_owned();

    let percent_decimal = regex(r"(?<![\p{L}\p{N}_.])(\d+[,.]\d+)\s*%");
    text = percent_decimal
        .replace_all(&text, |caps: &Captures<'_>| {
            format!(
                "{} phần trăm",
                decimal_to_words(caps.get(1).unwrap().as_str(), options.dialect)
            )
        })
        .into_owned();
    let percent_int = regex(r"(?<![\p{L}\p{N}_])(\d+)\s*%");
    text = percent_int
        .replace_all(&text, |caps: &Captures<'_>| {
            format!(
                "{} phần trăm",
                integer_str_to_words(caps.get(1).unwrap().as_str(), options.dialect)
            )
        })
        .into_owned();

    let decimal_re = regex(r"(?<![\p{L}\p{N}_.])(\d+[,.]\d+)(?![\p{L}\p{N}_.])");
    text = decimal_re
        .replace_all(&text, |caps: &Captures<'_>| {
            decimal_to_words(caps.get(1).unwrap().as_str(), options.dialect)
        })
        .into_owned();

    let integer_re = regex(r"(?<![\p{L}\p{N}_.])(-?\d+)(?![\p{L}\p{N}_/.:])");
    text = integer_re
        .replace_all(&text, |caps: &Captures<'_>| {
            integer_token_to_words(caps.get(1).unwrap().as_str(), options.dialect)
        })
        .into_owned();

    // Chữ số còn sót cạnh "/" nhưng không phải phân số (vd "1/hai")
    // vẫn phải đọc thành số, tránh fallback thành âm "a".
    let digit_slash_re = regex(r"(?<![\p{L}\p{N}_.])(\d+)(?=\s*/(?!\d))");
    text = digit_slash_re
        .replace_all(&text, |caps: &Captures<'_>| {
            integer_str_to_words(caps.get(1).unwrap().as_str(), options.dialect)
        })
        .into_owned();

    let integer_punct_re = regex(r"(?<![\p{L}\p{N}_.])(-?\d+)(?=[.:](?:\s|$))");
    text = integer_punct_re
        .replace_all(&text, |caps: &Captures<'_>| {
            integer_token_to_words(caps.get(1).unwrap().as_str(), options.dialect)
        })
        .into_owned();

    let generation_re = regex(r"(?<![\p{L}\p{N}_])([2-6])\s*G(?![\p{L}\p{N}_])");
    text = generation_re
        .replace_all(&text, |caps: &Captures<'_>| {
            let digit = caps.get(1).unwrap().as_str().parse::<usize>().unwrap_or(0);
            format!("{} giê", SMALL[digit])
        })
        .into_owned();

    let text = normalize_words(&text, options);
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reads_numbers() {
        assert_eq!(
            integer_str_to_words("1500", Dialect::North),
            "một nghìn năm trăm"
        );
        assert_eq!(integer_str_to_words("1000000", Dialect::North), "một triệu");
        assert_eq!(
            integer_str_to_words("1050000", Dialect::North),
            "một triệu không trăm năm mươi nghìn"
        );
        assert_eq!(
            integer_str_to_words("2500000000", Dialect::North),
            "hai tỷ năm trăm triệu"
        );
    }

    #[test]
    fn reads_fractions_with_punctuation_spaces_percent() {
        assert_eq!(
            normalize_text("1/2.", Dialect::North, None),
            "một phần hai."
        );
        assert_eq!(
            normalize_text("1/2,", Dialect::North, None),
            "một phần hai,"
        );
        assert_eq!(
            normalize_text("1 / 2", Dialect::North, None),
            "một phần hai"
        );
        assert_eq!(
            normalize_text("1/2%", Dialect::North, None),
            "một phần hai phần trăm"
        );
        assert_eq!(
            normalize_text("Số 1/2, số 1/4, đọc thế nào?", Dialect::North, None),
            "Số một phần hai, số một phần bốn, đọc thế nào?"
        );
        assert_eq!(normalize_text("1/hai", Dialect::North, None), "một/hai");
    }

    #[test]
    fn normalizes_basic() {
        assert_eq!(
            normalize_text("Hôm nay 14h30, giá 50.000đ.", Dialect::North, None),
            "Hôm nay mười bốn giờ ba mươi phút, giá năm mươi nghìn đồng."
        );
    }
}
