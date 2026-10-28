//! Parse/parity frontend tools (không link ONNX Runtime).

use std::collections::HashMap;
use std::io::{BufRead, BufReader, BufWriter, Write};
use std::path::PathBuf;

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use vifasttts_text::dialect::Dialect;
use vifasttts_text::pipeline::{
    ParseOptions, live_parse_options, normalize_input, parse_normalized, parse_text,
};
use vifasttts_text::vocab::ComponentVocabs;

#[derive(Parser, Debug)]
#[command(
    name = "vifasttts-parse",
    version,
    about = "ViFastTts parse/parity tools (text-only)"
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand, Debug)]
enum Command {
    /// Parse nhiều dòng JSONL (đối chiếu Python).
    ParseBatch {
        #[arg(long)]
        input: PathBuf,
        #[arg(long)]
        output: Option<PathBuf>,
    },
    /// Parse text -> JSONL (đối chiếu Python).
    Parse {
        #[arg(long)]
        text: String,
        #[arg(long, default_value = "north")]
        dialect: String,
        #[arg(long)]
        resolve_oov: bool,
        #[arg(long)]
        overrides: Option<PathBuf>,
        #[arg(long)]
        custom_reading: Option<PathBuf>,
        /// Ghi mỗi âm tiết một dòng JSON thay vì một object.
        #[arg(long)]
        jsonl: bool,
    },
}

fn load_map(path: &Option<PathBuf>) -> Result<Option<HashMap<String, String>>> {
    let Some(path) = path else {
        return Ok(None);
    };
    let text = std::fs::read_to_string(path).with_context(|| format!("đọc {}", path.display()))?;
    let map =
        serde_json::from_str(&text).with_context(|| format!("parse JSON {}", path.display()))?;
    Ok(Some(map))
}

fn parse_options(
    dialect: &str,
    resolve_oov: bool,
    overrides: &Option<PathBuf>,
    custom_reading: &Option<PathBuf>,
) -> Result<ParseOptions> {
    let dialect = Dialect::from_name(dialect).map_err(anyhow::Error::msg)?;
    let user = load_map(overrides)?;
    let mut options = live_parse_options(dialect, user.as_ref(), None);
    options.resolve_oov = resolve_oov;
    if let Some(map) = user {
        for (key, value) in &map {
            options
                .normalizer
                .exact_overrides
                .insert(key.clone(), value.clone());
            if key.is_ascii() {
                options
                    .normalizer
                    .english_overrides
                    .insert(key.to_lowercase(), value.clone());
            }
        }
    }
    if let Some(map) = load_map(custom_reading)? {
        options.custom_reading = Some(map);
    }
    Ok(options)
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::ParseBatch { input, output } => {
            let source =
                std::fs::File::open(&input).with_context(|| format!("mở {}", input.display()))?;
            let reader = BufReader::new(source);
            let mut writer: Box<dyn Write> = match output {
                Some(path) => Box::new(BufWriter::new(std::fs::File::create(&path)?)),
                None => Box::new(BufWriter::new(std::io::stdout())),
            };
            let vocabs = ComponentVocabs::default();
            let mut cached: Option<(String, bool, bool, ParseOptions)> = None;
            for line in reader.lines() {
                let line = line?;
                if line.trim().is_empty() {
                    continue;
                }
                let row: serde_json::Value = serde_json::from_str(&line)?;
                let dialect = row
                    .get("dialect")
                    .and_then(|v| v.as_str())
                    .unwrap_or("north");
                let resolve_oov = row
                    .get("resolve_oov")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false);
                let live = row.get("live").and_then(|v| v.as_bool()).unwrap_or(false);
                let has_overrides = row.get("overrides").is_some();
                let has_custom = row.get("custom_reading").is_some();
                let base = if !has_overrides && !has_custom {
                    let hit = cached
                        .as_ref()
                        .filter(|(d, l, r, _)| d == dialect && *l == live && *r == resolve_oov)
                        .map(|(_, _, _, options)| options.clone());
                    if let Some(options) = hit {
                        options
                    } else {
                        let dialect_value =
                            Dialect::from_name(dialect).map_err(anyhow::Error::msg)?;
                        let mut options = if live {
                            live_parse_options(dialect_value, None, None)
                        } else {
                            ParseOptions::new(dialect_value)
                        };
                        options.resolve_oov = resolve_oov;
                        cached = Some((dialect.to_string(), live, resolve_oov, options.clone()));
                        options
                    }
                } else {
                    let dialect_value = Dialect::from_name(dialect).map_err(anyhow::Error::msg)?;
                    let mut options = if live {
                        live_parse_options(dialect_value, None, None)
                    } else {
                        ParseOptions::new(dialect_value)
                    };
                    options.resolve_oov = resolve_oov;
                    if let Some(map) = row.get("overrides") {
                        let map: HashMap<String, String> = serde_json::from_value(map.clone())?;
                        for (key, value) in &map {
                            options
                                .normalizer
                                .exact_overrides
                                .insert(key.clone(), value.clone());
                            if key.is_ascii() {
                                options
                                    .normalizer
                                    .english_overrides
                                    .insert(key.to_lowercase(), value.clone());
                            }
                        }
                    }
                    if let Some(map) = row.get("custom_reading") {
                        options.custom_reading = Some(serde_json::from_value(map.clone())?);
                    }
                    options
                };
                let text = row.get("text").and_then(|v| v.as_str()).unwrap_or("");
                let normalized = normalize_input(text, &base);
                let items = parse_normalized(&normalized, &base);
                let parsed: Vec<serde_json::Value> = items
                    .iter()
                    .map(|item| serde_json::json!({"parsed": item, "ids": vocabs.encode(item)}))
                    .collect();
                let payload = serde_json::json!({
                    "text": text,
                    "normalized": normalized,
                    "items": parsed,
                });
                writer.write_all(serde_json::to_string(&payload)?.as_bytes())?;
                writer.write_all(b"\n")?;
            }
            writer.flush()?;
        }
        Command::Parse {
            text,
            dialect,
            resolve_oov,
            overrides,
            custom_reading,
            jsonl,
        } => {
            let options = parse_options(&dialect, resolve_oov, &overrides, &custom_reading)?;
            let items = parse_text(&text, &options);
            let vocabs = ComponentVocabs::default();
            let payload: Vec<serde_json::Value> = items
                .iter()
                .map(|item| {
                    serde_json::json!({
                        "parsed": item,
                        "ids": vocabs.encode(item),
                    })
                })
                .collect();
            if jsonl {
                for item in payload {
                    println!("{}", serde_json::to_string(&item)?);
                }
            } else {
                println!("{}", serde_json::to_string_pretty(&payload)?);
            }
        }
    }
    Ok(())
}
