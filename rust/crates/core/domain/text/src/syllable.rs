//! Tách một âm tiết tiếng Việt, tương đương `frontend/syllable.py`.

use crate::orthography::compose_canonical;
use crate::rules::{
    CONSONANT_CODAS, ONSET_SPELLINGS, coda_abstract, medial_nucleus_compatible, nucleus_abstract,
    onset_abstract, special_vowel, stop_coda,
};
use crate::tone::extract_tone;
use crate::types::{AbstractSyllable, Boundaries, Orthography, ParseStatus, ParsedSyllable, Tone};
use crate::unicode::normalize_unicode;

fn is_word_char(ch: char) -> bool {
    ch.is_alphanumeric() || ch == '_'
}

fn split_edge_punctuation(raw: &str) -> (&str, Option<String>) {
    let chars: Vec<char> = raw.chars().collect();
    let Some(first) = chars.iter().position(|ch| is_word_char(*ch)) else {
        return ("", Some(raw.to_string()));
    };
    let last = chars
        .iter()
        .rposition(|ch| is_word_char(*ch))
        .unwrap_or(first);
    let core: String = chars[first..=last].iter().collect();
    let mut punctuation = String::new();
    punctuation.extend(chars[..first].iter());
    punctuation.extend(chars[last + 1..].iter());
    let punctuation = if punctuation.is_empty() {
        None
    } else {
        Some(punctuation)
    };
    // Trả &str sống theo `raw`: dùng offset byte an toàn.
    let start = chars[..first].iter().map(|c| c.len_utf8()).sum::<usize>();
    let end = start + core.len();
    (&raw[start..end], punctuation)
}

fn match_onset(word: &str) -> (&str, &str, bool) {
    let vowel_letters = "aăâeêioôơuưy";
    let char_at = |index: usize| word.chars().nth(index);
    if word.starts_with("gi")
        && (word.chars().count() == 2
            || char_at(2) == Some('ê')
            || char_at(2).is_some_and(|ch| !vowel_letters.contains(ch)))
    {
        return ("g", &word[1..], false);
    }
    if let Some(rest) = word.strip_prefix("qu") {
        if char_at(2) == Some('ô') {
            return ("q", word.strip_prefix('q').unwrap_or(word), false);
        }
        return ("qu", rest, true);
    }
    for onset in ONSET_SPELLINGS {
        if let Some(rest) = word.strip_prefix(onset) {
            return (onset, rest, false);
        }
    }
    ("", word, false)
}

fn match_consonant_coda(remainder: &str) -> (&str, &str) {
    for coda in CONSONANT_CODAS {
        if remainder.ends_with(coda) && remainder.chars().count() > coda.chars().count() {
            let end = remainder.len() - coda.len();
            return (coda, &remainder[..end]);
        }
    }
    ("", remainder)
}

fn parse_vowel(
    vowel: &str,
    qu_medial: bool,
) -> Result<
    (
        Option<&'static str>,
        &'static str,
        &'static str,
        &'static str,
    ),
    String,
> {
    if qu_medial {
        let nucleus = nucleus_abstract(vowel)
            .ok_or_else(|| format!("Phần nguyên âm sau qu không hợp lệ: {vowel:?}"))?;
        // Trả chính tả (vowel), không phải category abstract (tránh "quÊ").
        return Ok((Some("u"), vowel_static(vowel), "W", nucleus));
    }
    if let Some((medial, nucleus)) = special_vowel(vowel) {
        return Ok((
            Some(medial),
            nucleus,
            "W",
            nucleus_abstract(nucleus).unwrap(),
        ));
    }
    if let Some(nucleus) = nucleus_abstract(vowel) {
        return Ok((None, vowel_static(vowel), "NONE", nucleus));
    }
    Err(format!(
        "Cụm nguyên âm không hợp lệ hoặc chưa có quy tắc: {vowel:?}"
    ))
}

/// `_parse_vowel` cần trả chính tả nucleus sống lâu hơn input; các giá trị đều
/// là chuỗi ngắn cố định. Hàm dưới ánh xạ về `'static` để giữ chữ ký giống bản Python.
fn vowel_static(vowel: &str) -> &'static str {
    match vowel {
        "a" => "a",
        "ă" => "ă",
        "â" => "â",
        "e" => "e",
        "ê" => "ê",
        "i" => "i",
        "y" => "y",
        "o" => "o",
        "ô" => "ô",
        "ơ" => "ơ",
        "u" => "u",
        "ư" => "ư",
        "oo" => "oo",
        "iê" => "iê",
        "yê" => "yê",
        "ia" => "ia",
        "ya" => "ya",
        "uô" => "uô",
        "ua" => "ua",
        "ươ" => "ươ",
        "ưa" => "ưa",
        _ => "",
    }
}

fn try_semivowel_coda(vowel_part: &str) -> (&str, &str) {
    let chars: Vec<char> = vowel_part.chars().collect();
    if chars.len() < 2 {
        return ("", vowel_part);
    }
    let last = chars[chars.len() - 1];
    if !"iyuo".contains(last) {
        return ("", vowel_part);
    }
    let base: String = chars[..chars.len() - 1].iter().collect();
    if nucleus_abstract(&base).is_some() || special_vowel(&base).is_some() {
        let last_str = match last {
            'i' => "i",
            'y' => "y",
            'u' => "u",
            'o' => "o",
            _ => unreachable!(),
        };
        let end = vowel_part.len() - last_str.len();
        return (last_str, &vowel_part[..end]);
    }
    ("", vowel_part)
}

fn validate(parsed: &ParsedSyllable) -> Result<(), String> {
    let a = &parsed.abstract_;
    if a.nucleus.is_empty() || a.nucleus == "NONE" {
        return Err("Âm tiết phải có nucleus".to_string());
    }
    if !medial_nucleus_compatible(&a.medial, &a.nucleus) {
        return Err(format!(
            "Âm đệm {} không kết hợp với nguyên âm {}",
            a.medial, a.nucleus
        ));
    }
    if stop_coda(&a.coda) && !matches!(a.tone, Tone::Sac | Tone::Nang) {
        return Err("Coda tắc P/T/C/CH chỉ kết hợp với thanh sắc hoặc nặng".to_string());
    }
    Ok(())
}

pub fn parse_syllable(raw: &str) -> Result<ParsedSyllable, String> {
    let normalized = normalize_unicode(raw).to_lowercase();
    let (core, punctuation) = split_edge_punctuation(&normalized);
    if core.is_empty() {
        return Err("Không có âm tiết để phân tích".to_string());
    }
    let (no_tone, tone, tone_location) = extract_tone(core)?;
    let (onset_spelling, remainder, qu_medial) = match_onset(&no_tone);
    let (mut coda_spelling, mut vowel_part) = match_consonant_coda(remainder);
    if coda_spelling.is_empty() && parse_vowel(vowel_part, qu_medial).is_err() {
        (coda_spelling, vowel_part) = try_semivowel_coda(vowel_part);
    }
    let (medial_s, nucleus_s, medial_a, mut nucleus_a) = parse_vowel(vowel_part, qu_medial)?;

    if matches!(coda_spelling, "y" | "u") && nucleus_s == "a" {
        nucleus_a = "Ă";
    }

    let abstract_onset = if matches!(onset_spelling, "q" | "qu") {
        "Q"
    } else if onset_spelling == "g" && no_tone.starts_with("gi") {
        "GI"
    } else {
        onset_abstract(onset_spelling)
            .ok_or_else(|| format!("Không nhận diện được âm đầu: {onset_spelling:?}"))?
    };

    let abstract_coda = coda_abstract(coda_spelling)
        .ok_or_else(|| format!("Không nhận diện được âm cuối: {coda_spelling:?}"))?;

    let parsed = ParsedSyllable {
        raw: raw.to_string(),
        normalized: normalized.clone(),
        orthography: Orthography {
            onset: if onset_spelling.is_empty() {
                None
            } else {
                Some(onset_spelling.to_string())
            },
            medial: medial_s.map(str::to_string),
            nucleus: nucleus_s.to_string(),
            coda: if coda_spelling.is_empty() {
                None
            } else {
                Some(coda_spelling.to_string())
            },
            tone_location: tone_location.map(|value| value.to_string()),
        },
        abstract_: AbstractSyllable {
            onset: abstract_onset.to_string(),
            medial: medial_a.to_string(),
            nucleus: nucleus_a.to_string(),
            coda: abstract_coda.to_string(),
            tone,
        },
        boundaries: Boundaries::default(),
        status: ParseStatus::Valid,
        confidence: 1.0,
        punctuation,
    };
    validate(&parsed)?;
    Ok(parsed)
}

pub fn safe_parse_syllable(raw: &str) -> Option<ParsedSyllable> {
    parse_syllable(raw).ok()
}

/// Dùng trong test/kiểm tra round-trip.
pub fn recompose(parsed: &ParsedSyllable) -> String {
    compose_canonical(
        parsed.orthography.onset.as_deref(),
        parsed.orthography.medial.as_deref(),
        &parsed.orthography.nucleus,
        parsed.orthography.coda.as_deref(),
        parsed.abstract_.tone,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_basic() {
        let item = parse_syllable("Chào").unwrap();
        assert_eq!(item.abstract_.onset, "CH");
        assert_eq!(item.abstract_.nucleus, "A");
        assert_eq!(item.abstract_.tone, Tone::Huyen);
        assert_eq!(item.orthography.onset.as_deref(), Some("ch"));
    }

    #[test]
    fn parses_quoc_as_q() {
        let item = parse_syllable("quốc").unwrap();
        assert_eq!(item.abstract_.onset, "Q");
        assert_eq!(item.abstract_.medial, "NONE");
        assert_eq!(item.abstract_.nucleus, "UÔ");
        assert_eq!(item.abstract_.coda, "C");
    }

    #[test]
    fn parses_gi() {
        let item = parse_syllable("giếng").unwrap();
        assert_eq!(item.abstract_.onset, "GI");
        assert_eq!(item.abstract_.nucleus, "IÊ");
        assert_eq!(item.abstract_.coda, "NG");
    }
}
