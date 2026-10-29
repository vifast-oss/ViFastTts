//! CLI Rust cho ViFastTts.

use std::collections::HashMap;
use std::path::PathBuf;

use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use vifasttts_http_client::{HttpTtsClient, HttpTtsRequest};
use vifasttts_huggingface::bundles_from_siblings;
use vifasttts_model_manager::ModelManager;
use vifasttts_native::{
    KaraokeDocument, PackOptions, StreamControl, SynthesisOptions, TimedUnit, VfaBundle,
    VfaOptions, VftsBundle, from_bytes, load, load_verified, load_vfa, load_vfa_auto, load_vfts,
    ort_info,
};
use vifasttts_text::dialect::Dialect;
use vifasttts_text::pipeline::{ParseOptions, live_parse_options};

#[derive(Subcommand, Debug)]
enum ModelsAction {
    /// Tìm model theo từ khóa (mặc định `vifasttts`).
    Search {
        #[arg(long, default_value = "vifasttts")]
        query: String,
        #[arg(long, default_value_t = 10)]
        limit: usize,
    },
    /// Liệt kê .vfa/.vfts của một repo.
    Files { repo: String },
    /// Tải một file .vfa/.vfts.
    Download {
        repo: String,
        path: String,
        #[arg(long, default_value = "models")]
        output: PathBuf,
    },
    /// Liệt kê bundle đã tải trong thư mục local.
    Installed {
        #[arg(long, default_value = "models")]
        directory: PathBuf,
    },
}

#[derive(Subcommand, Debug)]
enum VfaAction {
    /// Đóng gói acoustic + snapshot frontend, tham chiếu vocoder.
    Pack {
        #[arg(long, default_value = "artifacts/onnx/n0_q/acoustic.onnx")]
        acoustic: PathBuf,
        #[arg(long, default_value = "artifacts/onnx/n0_q/vocoder.onnx")]
        vocoder: PathBuf,
        #[arg(long)]
        output: PathBuf,
        #[arg(long)]
        frontend_dir: Option<PathBuf>,
        #[arg(long, default_value = "vocos-mel-24khz")]
        vocoder_id: String,
    },
    Inspect {
        input: PathBuf,
    },
    Unpack {
        input: PathBuf,
        #[arg(long)]
        output: PathBuf,
    },
}

#[derive(Subcommand, Debug)]
enum VftsAction {
    /// Đóng gói ONNX + snapshot frontend resources.
    Pack {
        #[arg(long, default_value = "artifacts/onnx/n0_q/acoustic.onnx")]
        acoustic: PathBuf,
        #[arg(long, default_value = "artifacts/onnx/n0_q/vocoder.onnx")]
        vocoder: PathBuf,
        #[arg(long)]
        output: PathBuf,
        /// Thư mục `resources/*.json`; mặc định lấy resource chuẩn của repo.
        #[arg(long)]
        frontend_dir: Option<PathBuf>,
    },
    /// Xem manifest/entry/hash, không nạp ORT.
    Inspect { input: PathBuf },
    /// Giải nén bundle ra thư mục.
    Unpack {
        input: PathBuf,
        #[arg(long)]
        output: PathBuf,
    },
}

#[derive(Parser, Debug)]
#[command(
    name = "vifasttts",
    version,
    about = "ViFastTts Rust: TUI mặc định, CLI hoặc server"
)]
struct Cli {
    /// Không truyền subcommand = mở TUI.
    #[command(subcommand)]
    command: Option<Command>,
}

#[derive(Subcommand, Debug)]
enum Command {
    /// Xem metadata/input/output của model.
    Inspect {
        #[arg(long, default_value = "artifacts/onnx/n0_q/acoustic.onnx")]
        acoustic: PathBuf,
        #[arg(long, default_value = "artifacts/onnx/n0_q/vocoder.onnx")]
        vocoder: PathBuf,
        #[arg(long)]
        manifest: Option<PathBuf>,
        /// Nạp model từ bundle `.vfts`.
        #[arg(long)]
        vfts: Option<PathBuf>,
        /// Nạp model từ bytes (kiểm API mobile/embedded).
        #[arg(long)]
        from_bytes: bool,
    },
    /// Tổng hợp từ text.
    Synth {
        #[arg(long)]
        text: String,
        #[arg(long, default_value = "out-rust.wav")]
        output: PathBuf,
        #[arg(long, default_value = "artifacts/onnx/n0_q/acoustic.onnx")]
        acoustic: PathBuf,
        #[arg(long, default_value = "artifacts/onnx/n0_q/vocoder.onnx")]
        vocoder: PathBuf,
        #[arg(long, default_value_t = 1.0)]
        speed: f32,
        #[arg(long, default_value_t = 1.5)]
        alpha: f32,
        #[arg(long, default_value_t = 300)]
        max_chars: usize,
        #[arg(long)]
        fixed_pauses: bool,
        #[arg(long)]
        peak_normalize: bool,
        #[arg(long)]
        resolve_oov: bool,
        #[arg(long, default_value = "north")]
        dialect: String,
        #[arg(long)]
        overrides: Option<PathBuf>,
        #[arg(long)]
        custom_reading: Option<PathBuf>,
        /// Nạp model từ bundle `.vfts`.
        #[arg(long)]
        vfts: Option<PathBuf>,
        /// Nạp acoustic-only `.vfa` (dùng `--vocoder` làm vocoder chung).
        #[arg(long)]
        vfa: Option<PathBuf>,
        /// Gọi server thay vì chạy local (ví dụ http://127.0.0.1:8000).
        #[arg(long)]
        server: Option<String>,
        /// Bearer token nếu server yêu cầu.
        #[arg(long)]
        token: Option<String>,
        /// Xuất SRT (line-level) từ timing acoustic.
        #[arg(long)]
        srt: Option<PathBuf>,
        /// Xuất WebVTT (line-level).
        #[arg(long)]
        vtt: Option<PathBuf>,
        /// Xuất WebVTT karaoke (timestamp từng âm tiết).
        #[arg(long)]
        vtt_karaoke: Option<PathBuf>,
        /// Xuất JSON timing/karaoke.
        #[arg(long)]
        karaoke: Option<PathBuf>,
    },
    /// Streaming PCM (callback); CLI gom lại để kiểm tra WAV.
    Stream {
        #[arg(long)]
        text: String,
        #[arg(long, default_value = "out-stream.wav")]
        output: PathBuf,
        #[arg(long, default_value = "artifacts/onnx/n0_q/acoustic.onnx")]
        acoustic: PathBuf,
        #[arg(long, default_value = "artifacts/onnx/n0_q/vocoder.onnx")]
        vocoder: PathBuf,
        #[arg(long, default_value_t = 1.0)]
        speed: f32,
        #[arg(long, default_value_t = 1.5)]
        alpha: f32,
        #[arg(long, default_value_t = 300)]
        max_chars: usize,
        #[arg(long)]
        fixed_pauses: bool,
        /// Xuất SRT sau khi stream xong.
        #[arg(long)]
        srt: Option<PathBuf>,
        #[arg(long)]
        vtt: Option<PathBuf>,
        #[arg(long)]
        vtt_karaoke: Option<PathBuf>,
        #[arg(long)]
        karaoke: Option<PathBuf>,
    },
    /// Tìm/tải bundle model public trên HuggingFace.
    Models {
        #[command(subcommand)]
        action: ModelsAction,
    },
    /// Đóng gói acoustic-only `.vfa` (dùng chung vocoder).
    Vfa {
        #[command(subcommand)]
        action: VfaAction,
    },
    /// Đóng gói/kiểm tra/giải nén model `.vfts`.
    Vfts {
        #[command(subcommand)]
        action: VftsAction,
    },
    /// Mở TUI (tương đương chạy không tham số).
    Tui,
    /// Chạy HTTP server + web UI (mặc định dùng thư mục `web` nếu có).
    Server {
        #[arg(long, default_value = "artifacts/onnx/n0_q/acoustic.onnx")]
        acoustic: PathBuf,
        #[arg(long, default_value = "artifacts/onnx/n0_q/vocoder.onnx")]
        vocoder: PathBuf,
        #[arg(long)]
        manifest: Option<PathBuf>,
        #[arg(long)]
        vfts: Option<PathBuf>,
        /// Acoustic-only `.vfa`; dùng vocoder trong `--vocoder`.
        #[arg(long)]
        vfa: Option<PathBuf>,
        #[arg(long, default_value = "127.0.0.1")]
        host: String,
        #[arg(long, default_value_t = 8000)]
        port: u16,
        #[arg(long, default_value_t = 3000)]
        max_chars: usize,
        #[arg(long)]
        token: Option<String>,
        #[arg(long)]
        web_dir: Option<PathBuf>,
        /// Cho phép web UI ở origin khác gọi API (CORS).
        #[arg(long)]
        cors: bool,
        /// Chỉ chạy API, không phục vụ web.
        #[arg(long)]
        api_only: bool,
        #[arg(long, default_value = "models")]
        model_dir: PathBuf,
    },
    /// Benchmark trong một process (load một lần, chạy nhiều lần).
    Bench {
        #[arg(long)]
        text: String,
        #[arg(long, default_value_t = 10)]
        runs: usize,
        #[arg(long, default_value_t = 3)]
        warmup: usize,
        #[arg(long, default_value = "artifacts/onnx/n0_q/acoustic.onnx")]
        acoustic: PathBuf,
        #[arg(long, default_value = "artifacts/onnx/n0_q/vocoder.onnx")]
        vocoder: PathBuf,
        #[arg(long, default_value_t = 1.0)]
        speed: f32,
        #[arg(long, default_value_t = 1.5)]
        alpha: f32,
        #[arg(long, default_value_t = 300)]
        max_chars: usize,
        #[arg(long)]
        fixed_pauses: bool,
    },
}

fn default_frontend_dir() -> Option<PathBuf> {
    [
        PathBuf::from("rust/crates/core/domain/text/resources"),
        PathBuf::from("crates/core/domain/text/resources"),
    ]
    .into_iter()
    .find(|path| path.is_dir())
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
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "vifasttts_rs=info,ort=warn".into()),
        )
        .init();
    let cli = Cli::parse();
    let command = match cli.command {
        Some(command) => command,
        None => {
            return vifasttts_tui::run(vifasttts_tui::TuiArgs::default())
                .map_err(anyhow::Error::msg);
        }
    };
    match command {
        Command::Inspect {
            acoustic,
            vocoder,
            manifest,
            vfts,
            from_bytes: use_bytes,
        } => {
            let engine = if let Some(path) = vfts {
                load_vfts(path).map_err(anyhow::Error::msg)?
            } else if use_bytes {
                let acoustic_bytes = std::fs::read(&acoustic)?;
                let vocoder_bytes = std::fs::read(&vocoder)?;
                from_bytes(&acoustic_bytes, &vocoder_bytes).map_err(anyhow::Error::msg)?
            } else {
                match manifest {
                    Some(path) => {
                        load_verified(&acoustic, &vocoder, path).map_err(anyhow::Error::msg)?
                    }
                    None => load(&acoustic, &vocoder).map_err(anyhow::Error::msg)?,
                }
            };
            println!("ort: {}", ort_info());
            println!("acoustic: {}", acoustic.display());
            println!("vocoder:  {}", vocoder.display());
            let info = engine.info();
            println!("sha256 acoustic: {}", info.acoustic_sha256);
            println!("sha256 vocoder:  {}", info.vocoder_sha256);
            println!("metadata: {:?}", info.metadata);
            println!("inputs: {:?}", engine.acoustic().input_names);
            println!("outputs: {:?}", engine.acoustic().output_names);
        }
        Command::Synth {
            text,
            output,
            acoustic,
            vocoder,
            speed,
            alpha,
            max_chars,
            fixed_pauses,
            peak_normalize,
            resolve_oov,
            dialect,
            overrides,
            custom_reading,
            vfts,
            vfa,
            server,
            token,
            srt,
            vtt,
            vtt_karaoke,
            karaoke,
        } => {
            if let Some(server_url) = server {
                let client = HttpTtsClient::new(server_url.clone(), token);
                let request = HttpTtsRequest {
                    text: text.clone(),
                    speed,
                    fixed_pauses,
                };
                let wants_subtitles =
                    srt.is_some() || vtt.is_some() || vtt_karaoke.is_some() || karaoke.is_some();
                if wants_subtitles {
                    let response = client
                        .synthesize_karaoke(&request)
                        .map_err(anyhow::Error::msg)?;
                    std::fs::write(&output, response.audio_bytes().map_err(anyhow::Error::msg)?)?;
                    if let Some(path) = srt {
                        std::fs::write(&path, &response.srt)?;
                    }
                    if let Some(path) = vtt {
                        std::fs::write(&path, &response.vtt)?;
                    }
                    if let Some(path) = vtt_karaoke {
                        std::fs::write(&path, &response.vtt_karaoke)?;
                    }
                    if let Some(path) = karaoke {
                        std::fs::write(&path, serde_json::to_string_pretty(&response.karaoke)?)?;
                    }
                    eprintln!(
                        "server {}: wrote {} ({} ms, {} units, {} lines)",
                        server_url,
                        output.display(),
                        response.duration_ms,
                        response.karaoke.units.len(),
                        response.karaoke.lines.len()
                    );
                } else {
                    let wav = client
                        .synthesize_wav(&request)
                        .map_err(anyhow::Error::msg)?;
                    std::fs::write(&output, wav)?;
                    eprintln!("server {}: wrote {}", server_url, output.display());
                }
                return Ok(());
            }
            let mut engine = if let Some(path) = vfa {
                if vocoder.exists() {
                    load_vfa(path, &vocoder).map_err(anyhow::Error::msg)?
                } else {
                    load_vfa_auto(path).map_err(anyhow::Error::msg)?
                }
            } else if let Some(path) = vfts {
                load_vfts(path).map_err(anyhow::Error::msg)?
            } else {
                load(&acoustic, &vocoder).map_err(anyhow::Error::msg)?
            };
            let mut options = SynthesisOptions {
                speed,
                alpha,
                max_chars,
                fixed_pauses,
                peak_normalize,
                parse: parse_options(&dialect, resolve_oov, &overrides, &custom_reading)?,
                ..SynthesisOptions::default()
            };
            if fixed_pauses {
                options.gate_threshold = 1.01;
            }
            let synthesis = engine
                .synthesize(&text, &options)
                .map_err(anyhow::Error::msg)?;
            std::fs::write(&output, &synthesis.wav)?;
            if let Some(document) = &synthesis.karaoke {
                if let Some(path) = srt {
                    std::fs::write(&path, document.to_srt())?;
                }
                if let Some(path) = vtt {
                    std::fs::write(&path, document.to_vtt())?;
                }
                if let Some(path) = vtt_karaoke {
                    std::fs::write(&path, document.to_vtt_karaoke())?;
                }
                if let Some(path) = karaoke {
                    std::fs::write(&path, serde_json::to_string_pretty(document)?)?;
                }
            } else if srt.is_some() || vtt.is_some() || vtt_karaoke.is_some() || karaoke.is_some() {
                eprintln!("model không xuất timing (slot_durations); bỏ qua phụ đề");
            }
            eprintln!(
                "wrote {} ({} samples, {:.2}s @ {} Hz)",
                output.display(),
                synthesis.waveform.len(),
                synthesis.waveform.len() as f64 / synthesis.sample_rate as f64,
                synthesis.sample_rate
            );
        }
        Command::Stream {
            text,
            output,
            acoustic,
            vocoder,
            speed,
            alpha,
            max_chars,
            fixed_pauses,
            srt,
            vtt,
            vtt_karaoke,
            karaoke,
        } => {
            let mut engine = load(&acoustic, &vocoder).map_err(anyhow::Error::msg)?;
            let mut options = SynthesisOptions {
                speed,
                alpha,
                max_chars,
                fixed_pauses,
                ..SynthesisOptions::default()
            };
            if fixed_pauses {
                options.gate_threshold = 1.01;
            }
            let mut all = Vec::new();
            let mut units: Vec<TimedUnit> = Vec::new();
            let summary = engine
                .synthesize_stream_with_units(
                    &text,
                    &options,
                    |samples, _| {
                        all.extend_from_slice(samples);
                        StreamControl::Continue
                    },
                    |chunk_units| units.extend_from_slice(chunk_units),
                )
                .map_err(anyhow::Error::msg)?;
            let wav = vifasttts_audio::wav_bytes(&all, summary.sample_rate);
            std::fs::write(&output, wav)?;
            if !units.is_empty() {
                let duration_ms = (all.len() as u64) * 1000 / summary.sample_rate.max(1) as u64;
                let document =
                    KaraokeDocument::from_units(units, summary.sample_rate, duration_ms, 80);
                if let Some(path) = srt {
                    std::fs::write(&path, document.to_srt())?;
                }
                if let Some(path) = vtt {
                    std::fs::write(&path, document.to_vtt())?;
                }
                if let Some(path) = vtt_karaoke {
                    std::fs::write(&path, document.to_vtt_karaoke())?;
                }
                if let Some(path) = karaoke {
                    std::fs::write(&path, serde_json::to_string_pretty(&document)?)?;
                }
            }
            eprintln!(
                "wrote {} ({} samples, {} chunks, cancelled={})",
                output.display(),
                all.len(),
                summary.chunks,
                summary.cancelled
            );
        }
        Command::Tui => {
            vifasttts_tui::run(vifasttts_tui::TuiArgs::default()).map_err(anyhow::Error::msg)?
        }
        Command::Server {
            acoustic,
            vocoder,
            manifest,
            vfts,
            vfa,
            host,
            port,
            max_chars,
            token,
            web_dir,
            cors,
            api_only,
            model_dir,
        } => {
            let web_dir = web_dir.or_else(|| {
                let dist = PathBuf::from("web/dist");
                if dist.is_dir() {
                    return Some(dist);
                }
                let web = PathBuf::from("web");
                web.is_dir().then_some(web)
            });
            let acoustic = if acoustic.exists() {
                acoustic
            } else {
                let packaged = PathBuf::from("models/acoustic.onnx");
                if packaged.exists() {
                    packaged
                } else {
                    acoustic
                }
            };
            let vocoder = if vocoder.exists() {
                vocoder
            } else {
                let packaged = PathBuf::from("models/vocoder.onnx");
                if packaged.exists() { packaged } else { vocoder }
            };
            let config = vifasttts_http_server::Args {
                acoustic,
                vocoder,
                manifest,
                vfts,
                vfa,
                host,
                port,
                max_chars,
                token,
                web_dir,
                cors,
                api_only,
                model_dir,
            };
            let runtime = tokio::runtime::Runtime::new().map_err(anyhow::Error::msg)?;
            runtime
                .block_on(vifasttts_http_server::serve(config))
                .map_err(anyhow::Error::msg)?;
        }
        Command::Models { action } => match action {
            ModelsAction::Search { query, limit } => {
                let models = ModelManager::new("models")
                    .search(&query, limit)
                    .map_err(anyhow::Error::msg)?;
                for model in models {
                    let bundles = bundles_from_siblings(&model);
                    println!(
                        "{}  downloads={} likes={} bundles={}",
                        model.id,
                        model.downloads,
                        model.likes,
                        if bundles.is_empty() {
                            "none".to_string()
                        } else {
                            bundles.join(",")
                        }
                    );
                }
            }
            ModelsAction::Files { repo } => {
                let files = ModelManager::new("models")
                    .files(&repo)
                    .map_err(anyhow::Error::msg)?;
                for file in files {
                    println!("{}	{} B", file.path, file.size);
                }
            }
            ModelsAction::Download { repo, path, output } => {
                let file = ModelManager::new(output)
                    .install(&repo, &path)
                    .map_err(anyhow::Error::msg)?;
                println!("wrote {} ({} B)", file.path.display(), file.size);
            }
            ModelsAction::Installed { directory } => {
                for model in ModelManager::new(directory).installed() {
                    println!("{}	{}	{} B", model.kind, model.path.display(), model.size);
                }
            }
        },
        Command::Vfa { action } => match action {
            VfaAction::Pack {
                acoustic,
                vocoder,
                output,
                frontend_dir,
                vocoder_id,
            } => {
                let frontend = frontend_dir.or_else(default_frontend_dir);
                let mut options = VfaOptions::default();
                options.vocoder.id = vocoder_id;
                let bundle =
                    VfaBundle::from_paths(&acoustic, &vocoder, frontend.as_deref(), options)
                        .map_err(anyhow::Error::msg)?;
                bundle.verify_runtime_vocab().map_err(anyhow::Error::msg)?;
                bundle.write_path(&output).map_err(anyhow::Error::msg)?;
                println!(
                    "wrote {} ({} B)",
                    output.display(),
                    std::fs::metadata(&output)?.len()
                );
            }
            VfaAction::Inspect { input } => {
                let bundle = VfaBundle::read_path(&input).map_err(anyhow::Error::msg)?;
                println!("{}", serde_json::to_string_pretty(&bundle.manifest)?);
                println!(
                    "acoustic: {} B; frontend: {}",
                    bundle.acoustic.len(),
                    bundle.frontend.len()
                );
                bundle.verify_runtime_vocab().map_err(anyhow::Error::msg)?;
                println!("runtime vocab: OK");
            }
            VfaAction::Unpack { input, output } => {
                let bundle = VfaBundle::read_path(&input).map_err(anyhow::Error::msg)?;
                bundle.unpack_to(&output).map_err(anyhow::Error::msg)?;
                println!("unpacked {}", output.display());
            }
        },
        Command::Vfts { action } => match action {
            VftsAction::Pack {
                acoustic,
                vocoder,
                output,
                frontend_dir,
            } => {
                let frontend = frontend_dir.or_else(default_frontend_dir);
                let bundle = VftsBundle::from_paths(
                    &acoustic,
                    &vocoder,
                    frontend.as_deref(),
                    PackOptions::default(),
                )
                .map_err(anyhow::Error::msg)?;
                bundle.verify_runtime_vocab().map_err(anyhow::Error::msg)?;
                bundle.write_path(&output).map_err(anyhow::Error::msg)?;
                println!(
                    "wrote {} ({} B)",
                    output.display(),
                    std::fs::metadata(&output)?.len()
                );
            }
            VftsAction::Inspect { input } => {
                let bundle = VftsBundle::read_path(&input).map_err(anyhow::Error::msg)?;
                println!("{}", serde_json::to_string_pretty(&bundle.manifest)?);
                println!(
                    "bytes: acoustic={} vocoder={}",
                    bundle.acoustic.len(),
                    bundle.vocoder.len()
                );
                println!(
                    "frontend: {}",
                    bundle
                        .frontend
                        .keys()
                        .cloned()
                        .collect::<Vec<_>>()
                        .join(", ")
                );
                bundle.verify_runtime_vocab().map_err(anyhow::Error::msg)?;
                println!("runtime vocab: OK");
            }
            VftsAction::Unpack { input, output } => {
                let bundle = VftsBundle::read_path(&input).map_err(anyhow::Error::msg)?;
                bundle.unpack_to(&output).map_err(anyhow::Error::msg)?;
                println!("unpacked {}", output.display());
            }
        },
        Command::Bench {
            text,
            runs,
            warmup,
            acoustic,
            vocoder,
            speed,
            alpha,
            max_chars,
            fixed_pauses,
        } => {
            let load_started = std::time::Instant::now();
            let mut engine = load(&acoustic, &vocoder).map_err(anyhow::Error::msg)?;
            let load_ms = load_started.elapsed().as_secs_f64() * 1000.0;
            let mut options = SynthesisOptions {
                speed,
                alpha,
                max_chars,
                fixed_pauses,
                ..SynthesisOptions::default()
            };
            options.parse = live_parse_options(Dialect::North, None, None);
            if fixed_pauses {
                options.gate_threshold = 1.01;
            }
            for _ in 0..warmup {
                engine
                    .synthesize(&text, &options)
                    .map_err(anyhow::Error::msg)?;
            }
            let mut times = Vec::with_capacity(runs);
            let mut audio_seconds = 0.0;
            for _ in 0..runs {
                let started = std::time::Instant::now();
                let result = engine
                    .synthesize(&text, &options)
                    .map_err(anyhow::Error::msg)?;
                times.push(started.elapsed().as_secs_f64());
                audio_seconds = result.waveform.len() as f64 / result.sample_rate as f64;
            }
            times.sort_by(f64::total_cmp);
            let p50 = times
                .get(times.len().saturating_sub(1) / 2)
                .copied()
                .unwrap_or(0.0);
            let p95_index = ((times.len() as f64 * 0.95).ceil() as usize).saturating_sub(1);
            let p95 = times
                .get(p95_index.min(times.len().saturating_sub(1)))
                .copied()
                .unwrap_or(0.0);
            let mean = times.iter().sum::<f64>() / times.len().max(1) as f64;
            let rtf = if audio_seconds > 0.0 {
                mean / audio_seconds
            } else {
                0.0
            };
            println!(
                "{}",
                serde_json::to_string(&serde_json::json!({
                    "load_ms": load_ms,
                    "runs": runs,
                    "chars": text.chars().count(),
                    "audio_seconds": audio_seconds,
                    "mean_ms": mean * 1000.0,
                    "p50_ms": p50 * 1000.0,
                    "p95_ms": p95 * 1000.0,
                    "rtf": rtf,
                }))?
            );
        }
    }
    Ok(())
}
