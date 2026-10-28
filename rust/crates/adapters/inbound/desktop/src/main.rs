//! Desktop app local-first cho ViFastTts.
//!
//! UI egui chỉ gọi application/ports; synth local chạy trong worker thread để
//! không chặn cửa sổ. Remote dùng HTTP client của workspace. Không có logic
//! audio/model riêng ngoài adapter.

use std::collections::HashMap;
use std::fs;
use std::io::Cursor;
use std::path::{Path, PathBuf};
use std::sync::mpsc::{self, Receiver, Sender};
use std::thread;
use std::time::{Duration, Instant};

use directories::ProjectDirs;
use eframe::egui;
use rodio::{Decoder, OutputStream, OutputStreamBuilder, Sink};
use serde::{Deserialize, Serialize};

use vifasttts_app::{
    AppSettings, Dictionary, EtaEstimator, EtaSample, SynthesisMode, parse_dictionary,
};
use vifasttts_http_client::{HttpTtsClient, HttpTtsRequest};
use vifasttts_native::{
    KaraokeDocument, ModelInfo, NativeEngine, SynthesisOptions, SynthesisResult, load,
};
use vifasttts_text::dialect::Dialect;
use vifasttts_text::pipeline::live_parse_options;

const HISTORY_LIMIT: usize = 24;
const DEFAULT_ACOUSTIC: &str = "artifacts/onnx/n0_q/acoustic.onnx";
const DEFAULT_VOCODER: &str = "artifacts/onnx/n0_q/vocoder.onnx";

fn main() -> eframe::Result {
    if std::env::args().any(|argument| argument == "--smoke") {
        return run_smoke();
    }
    let settings = load_settings();
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([1080.0, 760.0])
            .with_min_inner_size([760.0, 560.0])
            .with_title("ViFastTts Desktop"),
        ..Default::default()
    };
    eframe::run_native(
        "ViFastTts Desktop",
        options,
        Box::new(move |cc| Ok(Box::new(DesktopApp::new(cc, settings)))),
    )
}

/// Kiểm tra headless: nạp model + synth + kiểm WAV, không mở cửa sổ.
fn run_smoke() -> eframe::Result {
    let settings = load_settings();
    let acoustic =
        std::env::var("VIFASTT_ACOUSTIC").unwrap_or_else(|_| settings.acoustic_path.clone());
    let vocoder =
        std::env::var("VIFASTT_VOCODER").unwrap_or_else(|_| settings.vocoder_path.clone());
    let mut engine = match load(&acoustic, &vocoder) {
        Ok(engine) => engine,
        Err(error) => {
            eprintln!("SMOKE FAIL load: {error}");
            std::process::exit(1);
        }
    };
    let text = "Xin chào, đây là kiểm tra desktop.";
    match engine.synthesize(text, &SynthesisOptions::default()) {
        Ok(result) => {
            let duration = result.waveform.len() as f64 / result.sample_rate.max(1) as f64;
            let riff = result.wav.starts_with(b"RIFF");
            println!(
                "SMOKE OK {} Hz · {:.2} s · {} B WAV · riff={riff}",
                result.sample_rate,
                duration,
                result.wav.len()
            );
            if !riff || result.waveform.is_empty() {
                std::process::exit(1);
            }
        }
        Err(error) => {
            eprintln!("SMOKE FAIL synth: {error}");
            std::process::exit(1);
        }
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Settings / history
// ---------------------------------------------------------------------------

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(default)]
struct DesktopSettings {
    app: AppSettings,
    acoustic_path: String,
    vocoder_path: String,
    dialect: String,
    peak_normalize: bool,
    resolve_oov: bool,
    auto_play: bool,
    output_dir: String,
    history: Vec<EtaSample>,
}

impl Default for DesktopSettings {
    fn default() -> Self {
        Self {
            app: AppSettings {
                max_chars: 300,
                ..AppSettings::default()
            },
            acoustic_path: DEFAULT_ACOUSTIC.to_string(),
            vocoder_path: DEFAULT_VOCODER.to_string(),
            dialect: "north".to_string(),
            peak_normalize: false,
            resolve_oov: false,
            auto_play: true,
            output_dir: default_output_dir(),
            history: Vec::new(),
        }
    }
}

/// Tìm model trong app bundle nếu path tương đối không tồn tại.
fn resolve_model_path(value: &str) -> PathBuf {
    let path = PathBuf::from(value);
    if path.exists() {
        return path;
    }
    let Some(name) = path.file_name() else {
        return path;
    };
    if let Ok(executable) = std::env::current_exe()
        && let Some(macos_dir) = executable.parent()
    {
        if let Some(contents) = macos_dir.parent() {
            let candidate = contents.join("Resources").join(name);
            if candidate.exists() {
                return candidate;
            }
        }
        let candidate = macos_dir.join(name);
        if candidate.exists() {
            return candidate;
        }
    }
    path
}

fn default_output_dir() -> String {
    directories::UserDirs::new()
        .and_then(|dirs| {
            dirs.audio_dir()
                .or_else(|| dirs.download_dir())
                .map(Path::to_path_buf)
        })
        .or_else(|| std::env::current_dir().ok())
        .unwrap_or_else(|| PathBuf::from("."))
        .display()
        .to_string()
}

fn settings_path() -> PathBuf {
    ProjectDirs::from("com", "vifasttts", "ViFastTts")
        .map(|dirs| dirs.config_dir().join("desktop.json"))
        .unwrap_or_else(|| PathBuf::from("vifasttts-desktop.json"))
}

fn load_settings() -> DesktopSettings {
    let path = settings_path();
    fs::read_to_string(&path)
        .ok()
        .and_then(|text| serde_json::from_str(&text).ok())
        .unwrap_or_default()
}

fn save_settings(settings: &DesktopSettings) {
    let path = settings_path();
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    if let Ok(text) = serde_json::to_string_pretty(settings) {
        let _ = fs::write(path, text);
    }
}

// ---------------------------------------------------------------------------
// Backend events / workers
// ---------------------------------------------------------------------------

#[derive(Clone, Debug)]
struct ModelSummary {
    sample_rate: u32,
    arch: String,
    vocab_version: String,
    acoustic_sha: String,
    vocoder_sha: String,
}

impl From<&ModelInfo> for ModelSummary {
    fn from(info: &ModelInfo) -> Self {
        Self {
            sample_rate: info.sample_rate,
            arch: info.arch.clone(),
            vocab_version: info.vocab_version.clone(),
            acoustic_sha: info.acoustic_sha256.clone(),
            vocoder_sha: info.vocoder_sha256.clone(),
        }
    }
}

#[derive(Clone, Debug)]
struct SynthOutput {
    wav: Vec<u8>,
    sample_rate: u32,
    duration_ms: u64,
    karaoke: Option<KaraokeDocument>,
    elapsed_ms: u64,
    mode: String,
    chars: usize,
}

#[derive(Debug)]
enum BackendEvent {
    ModelLoading,
    ModelReady(ModelSummary),
    ModelError(String),
    Info(String),
    Started { estimated_ms: Option<u64> },
    Finished(SynthOutput),
    Failed(String),
}

enum LocalCommand {
    Load {
        acoustic: PathBuf,
        vocoder: PathBuf,
    },
    Synthesize {
        text: String,
        options: SynthesisOptions,
    },
}

fn spawn_local_worker(event_tx: Sender<BackendEvent>) -> Sender<LocalCommand> {
    let (command_tx, command_rx) = mpsc::channel();
    thread::spawn(move || local_worker(command_rx, event_tx));
    command_tx
}

fn local_worker(command_rx: Receiver<LocalCommand>, event_tx: Sender<BackendEvent>) {
    let mut engine: Option<NativeEngine> = None;
    while let Ok(command) = command_rx.recv() {
        match command {
            LocalCommand::Load { acoustic, vocoder } => {
                engine = None;
                let _ = event_tx.send(BackendEvent::ModelLoading);
                match load(&acoustic, &vocoder) {
                    Ok(loaded) => {
                        let summary = ModelSummary::from(loaded.info());
                        engine = Some(loaded);
                        let _ = event_tx.send(BackendEvent::ModelReady(summary));
                    }
                    Err(error) => {
                        let _ = event_tx.send(BackendEvent::ModelError(error));
                    }
                }
            }
            LocalCommand::Synthesize { text, options } => {
                let Some(engine) = engine.as_mut() else {
                    let _ = event_tx.send(BackendEvent::Failed(
                        "Model local chưa sẵn sàng".to_string(),
                    ));
                    continue;
                };
                let chars = text.chars().count();
                let started = Instant::now();
                match engine.synthesize(&text, &options) {
                    Ok(result) => {
                        let _ = event_tx.send(BackendEvent::Finished(to_output(
                            result,
                            started.elapsed().as_millis() as u64,
                            "local",
                            chars,
                        )));
                    }
                    Err(error) => {
                        let _ = event_tx.send(BackendEvent::Failed(error));
                    }
                }
            }
        }
    }
}

fn to_output(result: SynthesisResult, elapsed_ms: u64, mode: &str, chars: usize) -> SynthOutput {
    let duration_ms = result.waveform.len() as u64 * 1000 / result.sample_rate.max(1) as u64;
    SynthOutput {
        wav: result.wav,
        sample_rate: result.sample_rate,
        duration_ms,
        karaoke: result.karaoke,
        elapsed_ms,
        mode: mode.to_string(),
        chars,
    }
}

fn spawn_remote(
    event_tx: Sender<BackendEvent>,
    text: String,
    speed: f32,
    fixed_pauses: bool,
    server: String,
    token: String,
) {
    thread::spawn(move || {
        let chars = text.chars().count();
        let started = Instant::now();
        let client = HttpTtsClient::new(
            server,
            if token.trim().is_empty() {
                None
            } else {
                Some(token)
            },
        );
        let request = HttpTtsRequest {
            text,
            speed,
            fixed_pauses,
        };
        match client.synthesize_karaoke(&request) {
            Ok(response) => match response.audio_bytes() {
                Ok(wav) => {
                    let duration_ms = response.duration_ms;
                    let karaoke = Some(response.karaoke);
                    let _ = event_tx.send(BackendEvent::Finished(SynthOutput {
                        wav,
                        sample_rate: response.sample_rate,
                        duration_ms,
                        karaoke,
                        elapsed_ms: started.elapsed().as_millis() as u64,
                        mode: "remote".to_string(),
                        chars,
                    }));
                }
                Err(error) => {
                    let _ = event_tx.send(BackendEvent::Failed(error));
                }
            },
            Err(error) => {
                let _ = event_tx.send(BackendEvent::Failed(error));
            }
        }
    });
}

// ---------------------------------------------------------------------------
// Audio playback (rodio)
// ---------------------------------------------------------------------------

struct AudioPlayer {
    stream: Option<OutputStream>,
    sink: Option<Sink>,
    error: Option<String>,
}

impl AudioPlayer {
    fn new() -> Self {
        let mut player = Self {
            stream: None,
            sink: None,
            error: None,
        };
        player.ensure_output();
        player
    }

    fn ensure_output(&mut self) {
        if self.stream.is_some() {
            return;
        }
        match OutputStreamBuilder::open_default_stream() {
            Ok(stream) => {
                self.stream = Some(stream);
                self.error = None;
            }
            Err(error) => {
                self.error = Some(format!("không mở được audio output: {error}"));
            }
        }
    }

    fn play(&mut self, wav: &[u8]) -> Result<(), String> {
        self.ensure_output();
        if let Some(error) = &self.error {
            return Err(error.clone());
        }
        let stream = self
            .stream
            .as_ref()
            .ok_or_else(|| "audio output chưa sẵn sàng".to_string())?;
        let sink = Sink::connect_new(stream.mixer());
        let source = Decoder::new(Cursor::new(wav.to_vec()))
            .map_err(|error| format!("decode WAV: {error}"))?;
        sink.append(source);
        if let Some(old) = self.sink.replace(sink) {
            old.stop();
        }
        Ok(())
    }

    fn stop(&mut self) {
        if let Some(sink) = self.sink.take() {
            sink.stop();
        }
    }

    fn is_playing(&self) -> bool {
        self.sink.as_ref().is_some_and(|sink| !sink.empty())
    }
}

impl Drop for AudioPlayer {
    fn drop(&mut self) {
        self.stop();
    }
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

struct DesktopApp {
    settings: DesktopSettings,
    input: String,
    status: String,
    error: Option<String>,
    busy: bool,
    model_ready: bool,
    model_summary: Option<ModelSummary>,
    output: Option<SynthOutput>,
    last_saved_path: Option<PathBuf>,
    local_tx: Sender<LocalCommand>,
    event_tx: Sender<BackendEvent>,
    events: Receiver<BackendEvent>,
    audio: AudioPlayer,
    eta: EtaEstimator,
    dictionary: Dictionary,
    dictionary_source: String,
    settings_dirty: bool,
    show_dictionary: bool,
}

impl DesktopApp {
    fn new(_cc: &eframe::CreationContext<'_>, mut settings: DesktopSettings) -> Self {
        settings.history.truncate(HISTORY_LIMIT);
        let eta = EtaEstimator::from_samples(settings.history.clone(), HISTORY_LIMIT);
        let (event_tx, events) = mpsc::channel();
        let local_tx = spawn_local_worker(event_tx.clone());
        local_tx
            .send(LocalCommand::Load {
                acoustic: resolve_model_path(&settings.acoustic_path),
                vocoder: resolve_model_path(&settings.vocoder_path),
            })
            .ok();

        let dictionary_source = settings.app.dictionary.clone();
        let dictionary = parse_dictionary(&dictionary_source);

        Self {
            input: "Xin chào, đây là bản desktop local-first của ViFastTts.".to_string(),
            status: "Đang nạp model local…".to_string(),
            error: None,
            busy: false,
            model_ready: false,
            model_summary: None,
            output: None,
            last_saved_path: None,
            local_tx,
            event_tx,
            events,
            audio: AudioPlayer::new(),
            eta,
            dictionary,
            dictionary_source,
            settings,
            settings_dirty: false,
            show_dictionary: false,
        }
    }

    fn poll_events(&mut self) {
        while let Ok(event) = self.events.try_recv() {
            match event {
                BackendEvent::ModelLoading => {
                    self.model_ready = false;
                    self.model_summary = None;
                    self.status = "Đang nạp model local…".to_string();
                }
                BackendEvent::ModelReady(summary) => {
                    self.model_ready = true;
                    self.status = format!(
                        "Local sẵn sàng · {} Hz · {} · {}",
                        summary.sample_rate, summary.arch, summary.vocab_version
                    );
                    self.model_summary = Some(summary);
                }
                BackendEvent::ModelError(error) => {
                    self.model_ready = false;
                    self.model_summary = None;
                    self.status = "Model local lỗi".to_string();
                    self.error = Some(error);
                }
                BackendEvent::Info(message) => {
                    self.status = message;
                }
                BackendEvent::Started { estimated_ms } => {
                    self.busy = true;
                    self.error = None;
                    self.status = match estimated_ms {
                        Some(ms) => format!("Đang tổng hợp… (ETA ~{:.1} s)", ms as f64 / 1000.0),
                        None => "Đang tổng hợp…".to_string(),
                    };
                }
                BackendEvent::Finished(output) => {
                    self.busy = false;
                    self.status = format!(
                        "Xong · {:.2} s audio · {:.0} ms",
                        output.duration_ms as f64 / 1000.0,
                        output.elapsed_ms as f64
                    );
                    self.eta.record(EtaSample {
                        mode: output.mode.clone(),
                        chars: output.chars,
                        elapsed_ms: output.elapsed_ms,
                    });
                    self.settings.history = self.eta.samples().to_vec();
                    self.settings.history.truncate(HISTORY_LIMIT);
                    self.settings_dirty = true;
                    if self.settings.auto_play
                        && let Err(error) = self.audio.play(&output.wav)
                    {
                        self.error = Some(error);
                    }
                    self.output = Some(output);
                    self.save_if_dirty();
                }
                BackendEvent::Failed(error) => {
                    self.busy = false;
                    self.status = "Tổng hợp lỗi".to_string();
                    self.error = Some(error);
                }
            }
        }
    }

    fn mode_key(&self) -> &'static str {
        match self.settings.app.mode {
            SynthesisMode::Local => "local",
            SynthesisMode::Remote => "remote",
        }
    }

    fn estimate_ms(&self) -> Option<u64> {
        self.eta
            .estimate_ms(self.mode_key(), self.input.chars().count())
    }

    fn make_options(&self) -> Result<SynthesisOptions, String> {
        self.settings.app.validate()?;
        let dialect = Dialect::from_name(&self.settings.dialect)?;
        let dictionary = parse_dictionary(&self.settings.app.dictionary);
        let overrides: HashMap<String, String> = dictionary.overrides().into_iter().collect();
        let mut parse = live_parse_options(dialect, Some(&overrides), None);
        parse.resolve_oov = self.settings.resolve_oov;
        let max_chars = if self.settings.app.max_chars == 0 {
            300
        } else {
            self.settings.app.max_chars
        };
        let mut options = SynthesisOptions {
            speed: self.settings.app.speed,
            fixed_pauses: self.settings.app.fixed_pauses,
            alpha: self.settings.app.alpha,
            max_chars,
            peak_normalize: self.settings.peak_normalize,
            parse,
            ..SynthesisOptions::default()
        };
        if options.fixed_pauses {
            options.gate_threshold = 1.01;
        }
        Ok(options)
    }

    fn synthesize(&mut self) {
        let text = self.input.trim().to_string();
        if text.is_empty() {
            self.error = Some("Chưa có text".to_string());
            return;
        }
        let chars = text.chars().count();
        if chars > 50_000 {
            self.error = Some("Text quá dài (tối đa 50.000 ký tự trong desktop)".to_string());
            return;
        }
        let options = match self.make_options() {
            Ok(options) => options,
            Err(error) => {
                self.error = Some(error);
                return;
            }
        };
        let estimate = self.estimate_ms();
        self.busy = true;
        self.error = None;
        self.output = None;
        let _ = self.event_tx.send(BackendEvent::Started {
            estimated_ms: estimate,
        });
        match self.settings.app.mode {
            SynthesisMode::Local => {
                if !self.model_ready {
                    self.busy = false;
                    self.error = Some("Model local chưa sẵn sàng; bấm Nạp model".to_string());
                    return;
                }
                if let Err(error) = self.local_tx.send(LocalCommand::Synthesize {
                    text: text.clone(),
                    options,
                }) {
                    self.busy = false;
                    self.error = Some(format!("worker local đã dừng: {error}"));
                }
            }
            SynthesisMode::Remote => {
                spawn_remote(
                    self.event_tx.clone(),
                    text,
                    options.speed,
                    options.fixed_pauses,
                    self.settings.app.server_url.clone(),
                    self.settings.app.token.clone(),
                );
            }
        }
    }

    fn reload_local(&mut self) {
        self.error = None;
        self.model_ready = false;
        if let Err(error) = self.local_tx.send(LocalCommand::Load {
            acoustic: resolve_model_path(&self.settings.acoustic_path),
            vocoder: resolve_model_path(&self.settings.vocoder_path),
        }) {
            self.error = Some(format!("worker local đã dừng: {error}"));
        }
    }

    fn save_if_dirty(&mut self) {
        if self.settings_dirty {
            save_settings(&self.settings);
            self.settings_dirty = false;
        }
    }

    fn default_output_name(&self, extension: &str) -> String {
        let mode = self.mode_key();
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|value| value.as_secs())
            .unwrap_or(0);
        format!("vifasttts-{mode}-{stamp}.{extension}")
    }

    fn save_wav(&mut self) {
        let Some(output) = &self.output else { return };
        let directory = PathBuf::from(&self.settings.output_dir);
        let dialog = rfd::FileDialog::new()
            .set_directory(&directory)
            .set_file_name(self.default_output_name("wav"))
            .add_filter("WAV", &["wav"]);
        if let Some(path) = dialog.save_file() {
            match fs::write(&path, &output.wav) {
                Ok(()) => {
                    self.last_saved_path = Some(path.clone());
                    self.settings.output_dir = path
                        .parent()
                        .map(|value| value.display().to_string())
                        .unwrap_or_else(|| directory.display().to_string());
                    self.settings_dirty = true;
                    self.status = format!("Đã lưu {}", path.display());
                }
                Err(error) => self.error = Some(format!("lưu WAV: {error}")),
            }
        }
    }

    fn save_subtitle(&mut self, extension: &str) {
        let Some(output) = &self.output else { return };
        let Some(document) = &output.karaoke else {
            self.error = Some("Model không xuất timing/karaoke".to_string());
            return;
        };
        let content = match extension {
            "srt" => document.to_srt(),
            "vtt" => document.to_vtt(),
            _ => return,
        };
        let directory = PathBuf::from(&self.settings.output_dir);
        let dialog = rfd::FileDialog::new()
            .set_directory(&directory)
            .set_file_name(self.default_output_name(extension))
            .add_filter(extension.to_uppercase(), &[extension]);
        if let Some(path) = dialog.save_file() {
            match fs::write(&path, content) {
                Ok(()) => {
                    self.status = format!("Đã lưu {}", path.display());
                    self.settings.output_dir = path
                        .parent()
                        .map(|value| value.display().to_string())
                        .unwrap_or_else(|| directory.display().to_string());
                    self.settings_dirty = true;
                }
                Err(error) => self.error = Some(format!("lưu phụ đề: {error}")),
            }
        }
    }

    fn open_output_dir(&mut self) {
        let path = PathBuf::from(&self.settings.output_dir);
        let result = if cfg!(target_os = "macos") {
            std::process::Command::new("open").arg(&path).spawn()
        } else if cfg!(target_os = "windows") {
            std::process::Command::new("explorer").arg(&path).spawn()
        } else {
            std::process::Command::new("xdg-open").arg(&path).spawn()
        };
        if let Err(error) = result {
            self.error = Some(format!("mở thư mục: {error}"));
        }
    }

    fn refresh_dictionary(&mut self) {
        if self.dictionary_source == self.settings.app.dictionary {
            return;
        }
        self.dictionary_source = self.settings.app.dictionary.clone();
        self.dictionary = parse_dictionary(&self.dictionary_source);
    }

    fn settings_panel(&mut self, ui: &mut egui::Ui) {
        ui.heading("Cấu hình");
        ui.add_space(4.0);
        ui.label("Chế độ");
        ui.horizontal(|ui| {
            ui.selectable_value(&mut self.settings.app.mode, SynthesisMode::Local, "Local");
            ui.selectable_value(&mut self.settings.app.mode, SynthesisMode::Remote, "Remote");
        });

        if self.settings.app.mode == SynthesisMode::Local {
            ui.add_space(6.0);
            ui.label("Acoustic ONNX");
            ui.horizontal(|ui| {
                let changed = ui
                    .add(egui::TextEdit::singleline(&mut self.settings.acoustic_path))
                    .changed();
                if ui.button("…").clicked()
                    && let Some(path) = rfd::FileDialog::new()
                        .add_filter("ONNX", &["onnx"])
                        .pick_file()
                {
                    self.settings.acoustic_path = path.display().to_string();
                    self.settings_dirty = true;
                }
                if changed {
                    self.settings_dirty = true;
                }
            });
            ui.label("Vocoder ONNX");
            ui.horizontal(|ui| {
                let changed = ui
                    .add(egui::TextEdit::singleline(&mut self.settings.vocoder_path))
                    .changed();
                if ui.button("…").clicked()
                    && let Some(path) = rfd::FileDialog::new()
                        .add_filter("ONNX", &["onnx"])
                        .pick_file()
                {
                    self.settings.vocoder_path = path.display().to_string();
                    self.settings_dirty = true;
                }
                if changed {
                    self.settings_dirty = true;
                }
            });
            if ui.button("Nạp model local").clicked() {
                self.reload_local();
            }
            if let Some(summary) = &self.model_summary {
                ui.small(format!(
                    "{} Hz · {} · {}",
                    summary.sample_rate, summary.arch, summary.vocab_version
                ));
                ui.small(format!(
                    "acoustic {}… · vocoder {}…",
                    &summary.acoustic_sha[..summary.acoustic_sha.len().min(10)],
                    &summary.vocoder_sha[..summary.vocoder_sha.len().min(10)]
                ));
            } else {
                ui.small(if self.model_ready {
                    "Model chưa có metadata"
                } else {
                    "Model chưa nạp"
                });
            }
        } else {
            ui.add_space(6.0);
            ui.label("Server URL");
            if ui
                .add(egui::TextEdit::singleline(
                    &mut self.settings.app.server_url,
                ))
                .changed()
            {
                self.settings_dirty = true;
            }
            ui.label("Bearer token (tuỳ chọn)");
            if ui
                .add(egui::TextEdit::singleline(&mut self.settings.app.token).password(true))
                .changed()
            {
                self.settings_dirty = true;
            }
            if ui.button("Kiểm tra server").clicked() {
                let event_tx = self.event_tx.clone();
                let server = self.settings.app.server_url.clone();
                let token = self.settings.app.token.clone();
                thread::spawn(move || {
                    let client = HttpTtsClient::new(
                        server,
                        if token.trim().is_empty() {
                            None
                        } else {
                            Some(token)
                        },
                    );
                    match client.health() {
                        Ok(health) => {
                            let _ = event_tx.send(BackendEvent::Info(format!(
                                "Server OK · {} Hz · {} · {}",
                                health.sample_rate, health.arch, health.vocab_version
                            )));
                        }
                        Err(error) => {
                            let _ = event_tx
                                .send(BackendEvent::Failed(format!("Server health: {error}")));
                        }
                    }
                });
            }
            ui.small("Remote dùng /api/tts karaoke; model/alpha do server quyết định.");
        }

        ui.add_space(8.0);
        ui.separator();
        ui.add_space(8.0);
        ui.label("Âm thanh");
        if ui
            .add(egui::Slider::new(&mut self.settings.app.speed, 0.5..=2.0).text("Tốc độ"))
            .changed()
        {
            self.settings_dirty = true;
        }
        if ui
            .add(egui::Slider::new(&mut self.settings.app.alpha, 0.5..=3.0).text("Độ nét mel"))
            .changed()
        {
            self.settings_dirty = true;
        }
        if ui
            .checkbox(&mut self.settings.app.fixed_pauses, "Pause cố định")
            .changed()
        {
            self.settings_dirty = true;
        }
        if ui
            .checkbox(&mut self.settings.peak_normalize, "Peak normalize")
            .changed()
        {
            self.settings_dirty = true;
        }
        if ui
            .checkbox(&mut self.settings.auto_play, "Tự phát sau khi xong")
            .changed()
        {
            self.settings_dirty = true;
        }
        ui.horizontal(|ui| {
            ui.label("Max ký tự/chunk");
            if ui
                .add(egui::DragValue::new(&mut self.settings.app.max_chars).range(50..=5000))
                .changed()
            {
                self.settings_dirty = true;
            }
        });
        egui::ComboBox::from_label("Phương ngữ")
            .selected_text(match self.settings.dialect.as_str() {
                "central" => "Trung",
                "south" => "Nam",
                _ => "Bắc",
            })
            .show_ui(ui, |ui| {
                for (value, label) in [("north", "Bắc"), ("central", "Trung"), ("south", "Nam")] {
                    if ui
                        .selectable_value(&mut self.settings.dialect, value.to_string(), label)
                        .changed()
                    {
                        self.settings_dirty = true;
                    }
                }
            });
        if ui
            .checkbox(&mut self.settings.resolve_oov, "Resolve OOV")
            .changed()
        {
            self.settings_dirty = true;
        }

        ui.add_space(8.0);
        ui.separator();
        ui.add_space(8.0);
        ui.label("Thư mục xuất");
        ui.horizontal(|ui| {
            if ui
                .add(egui::TextEdit::singleline(&mut self.settings.output_dir))
                .changed()
            {
                self.settings_dirty = true;
            }
            if ui.button("…").clicked()
                && let Some(path) = rfd::FileDialog::new().pick_folder()
            {
                self.settings.output_dir = path.display().to_string();
                self.settings_dirty = true;
            }
        });
        if ui.button("Mở thư mục").clicked() {
            self.open_output_dir();
        }

        ui.add_space(8.0);
        ui.separator();
        ui.add_space(8.0);
        self.dictionary_panel(ui);
    }

    fn dictionary_panel(&mut self, ui: &mut egui::Ui) {
        egui::CollapsingHeader::new(format!(
            "Từ điển local ({} quy tắc{})",
            self.dictionary.rules.len(),
            if self.dictionary.warnings.is_empty() {
                String::new()
            } else {
                format!(", {} cảnh báo", self.dictionary.warnings.len())
            }
        ))
        .default_open(self.show_dictionary)
        .show(ui, |ui| {
            ui.small("Mỗi dòng `key = cách đọc`; dòng # là comment.");
            let response = ui.add(
                egui::TextEdit::multiline(&mut self.settings.app.dictionary)
                    .desired_rows(6)
                    .desired_width(f32::INFINITY)
                    .hint_text("AI = ây ai\nVPS = vi pi ét"),
            );
            if response.changed() {
                self.settings_dirty = true;
            }
            self.refresh_dictionary();
            for warning in self.dictionary.warnings.iter().take(6) {
                ui.small(egui::RichText::new(warning).color(egui::Color32::YELLOW));
            }
            if self.dictionary.warnings.len() > 6 {
                ui.small(format!(
                    "… và {} cảnh báo khác",
                    self.dictionary.warnings.len() - 6
                ));
            }
        });
    }

    fn result_panel(&mut self, ui: &mut egui::Ui) {
        let Some(output) = self.output.clone() else {
            return;
        };
        ui.separator();
        ui.add_space(6.0);
        ui.group(|ui| {
            ui.horizontal(|ui| {
                ui.strong("Kết quả");
                ui.label(format!(
                    "{:.2} s · {} Hz · {} ký tự · {} ms",
                    output.duration_ms as f64 / 1000.0,
                    output.sample_rate,
                    output.chars,
                    output.elapsed_ms
                ));
            });
            if let Some(document) = &output.karaoke {
                ui.small(format!(
                    "Karaoke: {} dòng, {} âm tiết",
                    document.lines.len(),
                    document.units.len()
                ));
            } else {
                ui.small("Không có timing từ model");
            }
            ui.horizontal(|ui| {
                if ui.button("▶ Phát").clicked()
                    && let Err(error) = self.audio.play(&output.wav)
                {
                    self.error = Some(error);
                }
                if ui.button("■ Dừng").clicked() {
                    self.audio.stop();
                }
                if ui.button("Lưu WAV").clicked() {
                    self.save_wav();
                }
                if output.karaoke.is_some() {
                    if ui.button("Lưu SRT").clicked() {
                        self.save_subtitle("srt");
                    }
                    if ui.button("Lưu VTT").clicked() {
                        self.save_subtitle("vtt");
                    }
                }
            });
            if let Some(path) = &self.last_saved_path {
                ui.small(format!("Lần lưu gần nhất: {}", path.display()));
            }
        });
    }

    fn central_panel(&mut self, ui: &mut egui::Ui) {
        ui.heading("ViFastTts");
        ui.label("TTS tiếng Việt local-first · Rust + ONNX Runtime");
        ui.add_space(8.0);

        let chars = self.input.chars().count();
        ui.horizontal(|ui| {
            if ui.button("Mở tệp…").clicked()
                && let Some(path) = rfd::FileDialog::new()
                    .add_filter("Văn bản", &["txt", "md"])
                    .pick_file()
            {
                match fs::read_to_string(&path) {
                    Ok(text) => {
                        self.input = text;
                        self.status = format!("Đã mở {}", path.display());
                    }
                    Err(error) => self.error = Some(format!("đọc {}: {error}", path.display())),
                }
            }
            if ui.button("Xoá").clicked() {
                self.input.clear();
            }
            ui.label(format!("{chars} ký tự"));
            if let Some(eta) = self.estimate_ms() {
                ui.small(format!("ETA ~{:.1} s (lịch sử)", eta as f64 / 1000.0));
            } else {
                ui.small("Chưa có lịch sử ETA cho chế độ này");
            }
        });
        egui::ScrollArea::vertical()
            .id_salt("input_scroll")
            .max_height(330.0)
            .show(ui, |ui| {
                ui.add(
                    egui::TextEdit::multiline(&mut self.input)
                        .desired_width(f32::INFINITY)
                        .desired_rows(14)
                        .hint_text("Nhập văn bản tiếng Việt…"),
                );
            });

        ui.horizontal(|ui| {
            let label = match self.settings.app.mode {
                SynthesisMode::Local => "Đọc local",
                SynthesisMode::Remote => "Đọc remote",
            };
            let enabled =
                !self.busy && (self.settings.app.mode == SynthesisMode::Remote || self.model_ready);
            if ui.add_enabled(enabled, egui::Button::new(label)).clicked() {
                self.synthesize();
            }
            if ui
                .add_enabled(self.busy, egui::Button::new("Huỷ"))
                .clicked()
            {
                self.audio.stop();
                self.busy = false;
                self.status = "Đã huỷ phía UI (local đang chạy sẽ hoàn tất)".to_string();
            }
            if self.busy {
                ui.spinner();
            }
        });

        ui.add_space(4.0);
        let color = if self.error.is_some() {
            egui::Color32::LIGHT_RED
        } else {
            ui.visuals().text_color()
        };
        ui.colored_label(color, &self.status);
        if let Some(error) = &self.error {
            ui.colored_label(egui::Color32::LIGHT_RED, error);
        }

        self.result_panel(ui);

        ui.separator();
        ui.add_space(4.0);
        ui.horizontal(|ui| {
            ui.small(format!(
                "Lịch sử ETA: {} mẫu · {} local / {} remote",
                self.eta.samples().len(),
                self.eta
                    .samples()
                    .iter()
                    .filter(|sample| sample.mode == "local")
                    .count(),
                self.eta
                    .samples()
                    .iter()
                    .filter(|sample| sample.mode == "remote")
                    .count()
            ));
            if ui.small_button("Xoá lịch sử").clicked() {
                self.eta = EtaEstimator::new(HISTORY_LIMIT);
                self.settings.history.clear();
                self.settings_dirty = true;
            }
        });
    }
}

impl eframe::App for DesktopApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.poll_events();

        if ctx.input(|input| input.modifiers.command && input.key_pressed(egui::Key::Enter))
            && !self.busy
            && (self.settings.app.mode == SynthesisMode::Remote || self.model_ready)
        {
            self.synthesize();
        }
        if ctx.input(|input| input.key_pressed(egui::Key::Escape)) {
            self.audio.stop();
        }

        ctx.set_visuals(egui::Visuals::dark());
        egui::TopBottomPanel::top("top").show(ctx, |ui| {
            ui.horizontal(|ui| {
                ui.heading("ViFastTts Desktop");
                ui.separator();
                ui.label(match self.settings.app.mode {
                    SynthesisMode::Local => "Local ONNX",
                    SynthesisMode::Remote => "Remote server",
                });
                ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                    if self.model_ready {
                        ui.colored_label(egui::Color32::LIGHT_GREEN, "● model ready");
                    } else if self.settings.app.mode == SynthesisMode::Remote {
                        ui.colored_label(egui::Color32::LIGHT_BLUE, "● remote");
                    } else {
                        ui.colored_label(egui::Color32::YELLOW, "● loading");
                    }
                    if self.audio.is_playing() {
                        ui.small("🔊 playing");
                    }
                });
            });
        });

        egui::SidePanel::right("settings")
            .resizable(true)
            .default_width(360.0)
            .min_width(300.0)
            .show(ctx, |ui| {
                egui::ScrollArea::vertical().show(ui, |ui| {
                    self.settings_panel(ui);
                });
            });

        egui::CentralPanel::default().show(ctx, |ui| {
            egui::ScrollArea::vertical()
                .id_salt("main_scroll")
                .show(ui, |ui| self.central_panel(ui));
        });

        self.save_if_dirty();
        if self.busy {
            ctx.request_repaint_after(Duration::from_millis(100));
        }
    }
}

impl Drop for DesktopApp {
    fn drop(&mut self) {
        self.save_if_dirty();
    }
}
