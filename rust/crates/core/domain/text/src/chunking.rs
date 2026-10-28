//! Chia câu và khoảng nghỉ, tương đương `frontend/chunking.py`.

pub const STEADY_PAUSE_DEFAULT: f64 = 0.08;
pub const STEADY_PAUSE_COMMA: f64 = 0.25;
pub const STEADY_PAUSE_PERIOD: f64 = 0.55;

fn normalize_space(text: &str) -> String {
    text.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn split_after_whitespace(text: &str, delimiters: &str) -> Vec<String> {
    let chars: Vec<(usize, char)> = text.char_indices().collect();
    let mut pieces = Vec::new();
    let mut start = 0usize;
    let mut index = 0usize;
    while index < chars.len() {
        let (byte, ch) = chars[index];
        if delimiters.contains(ch) {
            let mut next = index + 1;
            while next < chars.len() && chars[next].1.is_whitespace() {
                next += 1;
            }
            if next > index + 1 {
                let end = byte + ch.len_utf8();
                let piece = text[start..end].trim();
                if !piece.is_empty() {
                    pieces.push(piece.to_string());
                }
                start = chars.get(next).map(|(b, _)| *b).unwrap_or(text.len());
                index = next;
                continue;
            }
        }
        index += 1;
    }
    if start < text.len() {
        let piece = text[start..].trim();
        if !piece.is_empty() {
            pieces.push(piece.to_string());
        }
    }
    pieces
}

fn pack(parts: &[String], max_chars: usize) -> Vec<String> {
    let mut chunks = Vec::new();
    let mut current = String::new();
    for part in parts {
        let part = part.trim();
        if part.is_empty() {
            continue;
        }
        if current.is_empty() {
            current = part.to_string();
        } else if current.chars().count() + 1 + part.chars().count() <= max_chars {
            current.push(' ');
            current.push_str(part);
        } else {
            chunks.push(current);
            current = part.to_string();
        }
    }
    if !current.is_empty() {
        chunks.push(current);
    }
    chunks
}

pub fn chunk_text(text: &str, max_chars: usize) -> Result<Vec<String>, String> {
    if max_chars == 0 {
        return Err("max_chars phải > 0".to_string());
    }
    let normalized = normalize_space(text);
    if normalized.is_empty() {
        return Ok(Vec::new());
    }
    if normalized.chars().count() <= max_chars {
        return Ok(vec![normalized]);
    }
    let mut pieces = Vec::new();
    for sentence in split_after_whitespace(&normalized, ".!?…") {
        if sentence.chars().count() <= max_chars {
            pieces.push(sentence);
            continue;
        }
        for clause in split_after_whitespace(&sentence, ",;:") {
            if clause.chars().count() <= max_chars {
                pieces.push(clause);
                continue;
            }
            let mut buffer = String::new();
            for word in clause.split(' ') {
                if word.is_empty() {
                    continue;
                }
                if !buffer.is_empty()
                    && buffer.chars().count() + 1 + word.chars().count() > max_chars
                {
                    pieces.push(buffer);
                    buffer = word.to_string();
                } else if buffer.is_empty() {
                    buffer = word.to_string();
                } else {
                    buffer.push(' ');
                    buffer.push_str(word);
                }
            }
            if !buffer.is_empty() {
                pieces.push(buffer);
            }
        }
    }
    Ok(pack(&pieces, max_chars))
}

pub fn split_clauses(text: &str, max_chars: usize) -> Result<Vec<String>, String> {
    let normalized = normalize_space(text);
    if normalized.is_empty() {
        return Ok(Vec::new());
    }
    let mut pieces = Vec::new();
    for part in split_after_whitespace(&normalized, ".!?…,;:") {
        if part.chars().count() <= max_chars {
            pieces.push(part);
        } else {
            pieces.extend(chunk_text(&part, max_chars)?);
        }
    }
    Ok(pieces)
}

pub fn steady_pause_seconds(chunk: &str, comma: f64, period: f64, default: f64) -> f64 {
    let stripped = chunk.trim_end();
    let Some(last) = stripped.chars().last() else {
        return 0.0;
    };
    if ".!?…".contains(last) {
        period
    } else if ",;:".contains(last) {
        comma
    } else {
        default
    }
}

pub fn pause_seconds(chunk: &str) -> f64 {
    let stripped = chunk.trim_end();
    let Some(last) = stripped.chars().last() else {
        return 0.0;
    };
    if ".!?…".contains(last) {
        0.15
    } else if ",;:".contains(last) {
        0.08
    } else {
        0.05
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn chunks_sentences() {
        assert_eq!(chunk_text("Một. Hai!", 100).unwrap(), vec!["Một. Hai!"]);
        assert_eq!(
            split_clauses("Một, hai.", 100).unwrap(),
            vec!["Một,", "hai."]
        );
    }

    #[test]
    fn packs_long() {
        let chunks = chunk_text("một hai ba bốn", 7).unwrap();
        assert_eq!(chunks, vec!["một hai", "ba bốn"]);
    }
}
