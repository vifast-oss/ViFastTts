//! Karaoke/timing model + export SRT/WebVTT.
//!
//! Canonical là JSON `KaraokeDocument`; SRT/VTT chỉ là định dạng export.
//! Timing do engine sinh từ `slot_durations` của acoustic, không phải căn chỉnh lại.

use serde::{Deserialize, Serialize};

pub const KARAOKE_VERSION: u32 = 1;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum UnitKind {
    Syllable,
    Word,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct TimedUnit {
    pub text: String,
    pub start_ms: u64,
    pub end_ms: u64,
    pub kind: UnitKind,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub punctuation: Option<String>,
    #[serde(default)]
    pub sentence_end: bool,
    #[serde(default)]
    pub phrase_end: bool,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct KaraokeLine {
    pub text: String,
    pub start_ms: u64,
    pub end_ms: u64,
    pub units: Vec<TimedUnit>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct KaraokeDocument {
    pub version: u32,
    pub sample_rate: u32,
    pub duration_ms: u64,
    pub units: Vec<TimedUnit>,
    pub lines: Vec<KaraokeLine>,
}

impl KaraokeDocument {
    /// `units` phải theo đúng thứ tự audio; `duration_ms` lấy từ waveform.
    pub fn from_units(
        units: Vec<TimedUnit>,
        sample_rate: u32,
        duration_ms: u64,
        max_line_chars: usize,
    ) -> Self {
        let lines = group_lines(&units, max_line_chars);
        Self {
            version: KARAOKE_VERSION,
            sample_rate,
            duration_ms,
            units,
            lines,
        }
    }

    pub fn to_srt(&self) -> String {
        let mut output = String::new();
        let mut cue = 0usize;
        for line in &self.lines {
            if line.end_ms <= line.start_ms || line.text.is_empty() {
                continue;
            }
            cue += 1;
            output.push_str(&cue.to_string());
            output.push('\n');
            output.push_str(&format_timestamp(line.start_ms, ','));
            output.push_str(" --> ");
            output.push_str(&format_timestamp(line.end_ms, ','));
            output.push('\n');
            output.push_str(&line.text);
            output.push_str("\n\n");
        }
        output
    }

    pub fn to_vtt(&self) -> String {
        let mut output = String::from("WEBVTT\n\n");
        for line in &self.lines {
            if line.end_ms <= line.start_ms || line.text.is_empty() {
                continue;
            }
            output.push_str(&format_timestamp(line.start_ms, '.'));
            output.push_str(" --> ");
            output.push_str(&format_timestamp(line.end_ms, '.'));
            output.push('\n');
            output.push_str(&line.text);
            output.push_str("\n\n");
        }
        output
    }

    /// WebVTT karaoke: timestamp nội dòng cho từng âm tiết.
    pub fn to_vtt_karaoke(&self) -> String {
        let mut output = String::from("WEBVTT\n\n");
        for line in &self.lines {
            if line.end_ms <= line.start_ms || line.text.is_empty() {
                continue;
            }
            output.push_str(&format_timestamp(line.start_ms, '.'));
            output.push_str(" --> ");
            output.push_str(&format_timestamp(line.end_ms, '.'));
            output.push('\n');
            for (index, unit) in line.units.iter().enumerate() {
                if index > 0 {
                    output.push(' ');
                }
                output.push('<');
                output.push_str(&format_timestamp(unit.start_ms, '.'));
                output.push('>');
                output.push_str(&unit.text);
                if let Some(punctuation) = &unit.punctuation {
                    output.push_str(punctuation);
                }
            }
            output.push_str("\n\n");
        }
        output
    }
}

pub fn group_lines(units: &[TimedUnit], max_chars: usize) -> Vec<KaraokeLine> {
    let max_chars = max_chars.max(1);
    let mut lines = Vec::new();
    let mut current: Vec<TimedUnit> = Vec::new();
    let mut chars = 0usize;
    for unit in units {
        if unit.end_ms <= unit.start_ms {
            continue;
        }
        let extra = unit.text.chars().count()
            + unit
                .punctuation
                .as_deref()
                .map(|value| value.chars().count())
                .unwrap_or(0)
            + usize::from(!current.is_empty());
        current.push(unit.clone());
        chars += extra;
        let should_close = unit.sentence_end || unit.phrase_end || chars >= max_chars;
        if should_close {
            lines.push(finish_line(std::mem::take(&mut current)));
            chars = 0;
        }
    }
    if !current.is_empty() {
        lines.push(finish_line(current));
    }
    lines
}

fn finish_line(units: Vec<TimedUnit>) -> KaraokeLine {
    let start_ms = units.first().map(|unit| unit.start_ms).unwrap_or(0);
    let end_ms = units.last().map(|unit| unit.end_ms).unwrap_or(start_ms);
    let mut text = String::new();
    for unit in &units {
        if !text.is_empty() {
            text.push(' ');
        }
        text.push_str(&unit.text);
        if let Some(punctuation) = &unit.punctuation {
            text.push_str(punctuation);
        }
    }
    KaraokeLine {
        text,
        start_ms,
        end_ms,
        units,
    }
}

pub fn format_timestamp(ms: u64, separator: char) -> String {
    let hours = ms / 3_600_000;
    let minutes = (ms / 60_000) % 60;
    let seconds = (ms / 1_000) % 60;
    let millis = ms % 1_000;
    format!("{hours:02}:{minutes:02}:{seconds:02}{separator}{millis:03}")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn unit(text: &str, start: u64, end: u64, sentence_end: bool) -> TimedUnit {
        TimedUnit {
            text: text.to_string(),
            start_ms: start,
            end_ms: end,
            kind: UnitKind::Syllable,
            punctuation: None,
            sentence_end,
            phrase_end: sentence_end,
        }
    }

    #[test]
    fn formats_timestamps() {
        assert_eq!(format_timestamp(3_723_045, ','), "01:02:03,045");
        assert_eq!(format_timestamp(0, '.'), "00:00:00.000");
    }

    #[test]
    fn groups_lines_and_exports() {
        let units = vec![
            unit("Xin", 0, 200, false),
            unit("chào", 200, 500, true),
            unit("bạn", 700, 900, true),
        ];
        let doc = KaraokeDocument::from_units(units, 24_000, 1_000, 80);
        assert_eq!(doc.lines.len(), 2);
        assert_eq!(doc.lines[0].text, "Xin chào");
        let srt = doc.to_srt();
        assert!(srt.contains("00:00:00,000 --> 00:00:00,500"));
        assert!(srt.contains("00:00:00,700 --> 00:00:00,900"));
        let vtt = doc.to_vtt_karaoke();
        assert!(vtt.starts_with("WEBVTT"));
        assert!(vtt.contains("<00:00:00.200>chào"));
    }
}
