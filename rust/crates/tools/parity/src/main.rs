//! Parity/debug tools cho ViFastTts (tách khỏi CLI production).

use std::path::PathBuf;

use anyhow::Result;
use clap::{Parser, Subcommand};
use vifasttts_native::{load, ort_info};

#[derive(Parser, Debug)]
#[command(
    name = "vifasttts-tools",
    version,
    about = "ViFastTts parity/debug tools"
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand, Debug)]
enum Command {
    /// Xuất mel thô từ 7 ID (parity/debug).
    MelIds {
        #[arg(long)]
        features: PathBuf,
        #[arg(long)]
        output: PathBuf,
        #[arg(long, default_value = "artifacts/onnx/n0_q/acoustic.onnx")]
        acoustic: PathBuf,
        #[arg(long, default_value = "artifacts/onnx/n0_q/vocoder.onnx")]
        vocoder: PathBuf,
        #[arg(long, default_value_t = 1.0)]
        speed: f32,
        #[arg(long, default_value_t = 0.5)]
        gate: f32,
    },
    /// Tổng hợp từ mảng 7 ID đã tính (parity/Phase 1).
    SynthIds {
        #[arg(long)]
        features: PathBuf,
        #[arg(long, default_value = "out-rust.wav")]
        output: PathBuf,
        #[arg(long, default_value = "artifacts/onnx/n0_q/acoustic.onnx")]
        acoustic: PathBuf,
        #[arg(long, default_value = "artifacts/onnx/n0_q/vocoder.onnx")]
        vocoder: PathBuf,
        #[arg(long, default_value_t = 1.0)]
        speed: f32,
        #[arg(long, default_value_t = 0.5)]
        gate: f32,
        #[arg(long, default_value_t = 1.5)]
        alpha: f32,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Command::MelIds {
            features,
            output,
            acoustic,
            vocoder,
            speed,
            gate,
        } => {
            let text = std::fs::read_to_string(&features)?;
            let rows: Vec<[i64; 7]> = serde_json::from_str(&text)?;
            let mut engine = load(&acoustic, &vocoder).map_err(anyhow::Error::msg)?;
            let mel = engine
                .acoustic_mel(&rows, speed, gate)
                .map_err(anyhow::Error::msg)?;
            let bytes: Vec<u8> = mel
                .data
                .iter()
                .flat_map(|value| value.to_le_bytes())
                .collect();
            std::fs::write(&output, bytes)?;
            eprintln!("{} frames, {} mels ({})", mel.frames, mel.mels, ort_info());
        }
        Command::SynthIds {
            features,
            output,
            acoustic,
            vocoder,
            speed,
            gate,
            alpha,
        } => {
            let text = std::fs::read_to_string(&features)?;
            let rows: Vec<[i64; 7]> = serde_json::from_str(&text)?;
            let mut engine = load(&acoustic, &vocoder).map_err(anyhow::Error::msg)?;
            let synthesis = engine
                .synthesize_ids(&rows, speed, gate, alpha, false)
                .map_err(anyhow::Error::msg)?;
            std::fs::write(&output, &synthesis.wav)?;
            eprintln!(
                "wrote {} ({} samples @ {} Hz)",
                output.display(),
                synthesis.waveform.len(),
                synthesis.sample_rate
            );
        }
    }
    Ok(())
}
