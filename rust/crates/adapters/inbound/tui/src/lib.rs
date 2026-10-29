//! TUI tối giản cho ViFastTts: nhập text, synth local/remote, lưu WAV.
//!
//! Chỉ phụ thuộc ratatui/crossterm + native/http-client; không biết UI web.

use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use std::sync::mpsc::{self, Receiver, Sender};
use std::thread;
use std::time::{Duration, Instant};

use anyhow::{Context, Result};
use clap::Parser;
use crossterm::event::{
    self, Event as CrosstermEvent, KeyCode, KeyEvent, KeyEventKind, KeyModifiers,
};
use crossterm::execute;
use crossterm::terminal::{
    EnterAlternateScreen, LeaveAlternateScreen, disable_raw_mode, enable_raw_mode,
};
use ratatui::backend::CrosstermBackend;
use ratatui::layout::{Constraint, Direction, Layout};
use ratatui::style::{Color, Modifier, Style};
use ratatui::text::{Line, Span, Text};
use ratatui::widgets::{Block, Borders, Clear, Paragraph, Wrap};
use ratatui::{Frame, Terminal};

use vifasttts_app::{default_text, parse_dictionary};
use vifasttts_http_client::{HttpTtsClient, HttpTtsRequest};
use vifasttts_huggingface::{HfFile, HfModel};
use vifasttts_model_manager::ModelManager;
use vifasttts_native::{NativeEngine, SynthesisOptions, load, load_vfa, load_vfts};
use vifasttts_text::dialect::Dialect;
use vifasttts_text::karaoke::KaraokeDocument;
use vifasttts_text::pipeline::live_parse_options;

#[derive(Parser, Debug)]
#[command(name = "vifasttts-tui", version, about = "Terminal UI cho ViFastTts")]
pub struct TuiArgs {
    #[arg(long, default_value = "Xin chào, đây là bản TUI của ViFastTts.")]
    pub text: String,
    #[arg(long, default_value = "out-tui.wav")]
    pub output: PathBuf,
    #[arg(long, default_value = "artifacts/onnx/n0_q/acoustic.onnx")]
    pub acoustic: PathBuf,
    #[arg(long, default_value = "artifacts/onnx/n0_q/vocoder.onnx")]
    pub vocoder: PathBuf,
    /// Dùng server HTTP thay vì nạp model local.
    #[arg(long)]
    pub server: Option<String>,
    #[arg(long)]
    pub token: Option<String>,
    #[arg(long, default_value_t = 1.0)]
    pub speed: f32,
    #[arg(long, default_value_t = 1.5)]
    pub alpha: f32,
    #[arg(long, default_value_t = 300)]
    pub max_chars: usize,
    #[arg(long)]
    pub fixed_pauses: bool,
    #[arg(long)]
    pub peak_normalize: bool,
    #[arg(long, default_value = "north")]
    pub dialect: String,
    #[arg(long)]
    pub resolve_oov: bool,
    /// File từ điển `key = cách đọc` (tuỳ chọn).
    #[arg(long)]
    pub dictionary: Option<PathBuf>,
    /// Nạp model từ bundle `.vfts`.
    #[arg(long)]
    pub vfts: Option<PathBuf>,
    /// Nạp acoustic-only `.vfa` (dùng `--vocoder`).
    #[arg(long)]
    pub vfa: Option<PathBuf>,
    /// Xuất SRT sau khi đọc xong.
    #[arg(long)]
    pub srt: Option<PathBuf>,
    /// Xuất WebVTT sau khi đọc xong.
    #[arg(long)]
    pub vtt: Option<PathBuf>,
    /// Thư mục model dùng cho model browser (Ctrl+O).
    #[arg(long, default_value = "models")]
    pub model_dir: PathBuf,
}

fn default_model(name: &str) -> PathBuf {
    let packaged = PathBuf::from("models").join(name);
    if packaged.exists() {
        packaged
    } else {
        PathBuf::from("artifacts/onnx/n0_q").join(name)
    }
}

/// Nạp `.vfa`/`.vfts` theo đuôi; lỗi rõ để UI hiển thị.
fn load_bundle(path: &std::path::Path, vocoder: &std::path::Path) -> Result<NativeEngine, String> {
    let extension = path
        .extension()
        .and_then(|value| value.to_str())
        .unwrap_or_default();
    match extension {
        "vfa" => load_vfa(path, vocoder),
        "vfts" => load_vfts(path),
        _ => Err("model browser chỉ tải .vfa/.vfts".to_string()),
    }
}

impl Default for TuiArgs {
    fn default() -> Self {
        Self {
            text: default_text("tui"),
            output: PathBuf::from("out-tui.wav"),
            acoustic: default_model("acoustic.onnx"),
            vocoder: default_model("vocoder.onnx"),
            server: None,
            token: None,
            speed: 1.0,
            alpha: 1.5,
            max_chars: 300,
            fixed_pauses: false,
            peak_normalize: false,
            dialect: "north".to_string(),
            resolve_oov: true,
            dictionary: None,
            vfts: None,
            vfa: None,
            srt: None,
            vtt: None,
            model_dir: PathBuf::from("models"),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Mode {
    Local,
    Remote,
}

enum TuiEvent {
    Status(String),
    Ready(String),
    Done {
        wav: Vec<u8>,
        elapsed_ms: u64,
        mode: Mode,
        karaoke: Option<KaraokeDocument>,
    },
    Error(String),
    ModelResults(Vec<HfModel>),
    ModelFiles(Vec<HfFile>),
    ModelDownloaded(PathBuf),
    ModelError(String),
}

#[allow(clippy::large_enum_variant)]
enum LocalCommand {
    Synthesize {
        text: String,
        options: SynthesisOptions,
    },
    Reload(PathBuf),
}

#[derive(Default)]
struct ModelPane {
    open: bool,
    query: String,
    results: Vec<HfModel>,
    files: Vec<HfFile>,
    repo: Option<String>,
    selected: usize,
    loading: bool,
    status: String,
}

impl ModelPane {
    fn new() -> Self {
        Self {
            query: "vifasttts".to_string(),
            status: "Enter: tìm · chọn repo: Enter · chọn file: Enter".to_string(),
            ..Self::default()
        }
    }
}

struct App {
    input: String,
    output: PathBuf,
    mode: Mode,
    server: Option<String>,
    token: Option<String>,
    speed: f32,
    alpha: f32,
    max_chars: usize,
    fixed_pauses: bool,
    peak_normalize: bool,
    dialect: String,
    resolve_oov: bool,
    srt: Option<PathBuf>,
    vtt: Option<PathBuf>,
    show_settings: bool,
    busy: bool,
    quit: bool,
    status: String,
    logs: Vec<String>,
    events: Receiver<TuiEvent>,
    local_tx: Option<Sender<LocalCommand>>,
    forward_tx: Sender<TuiEvent>,
    dictionary: HashMap<String, String>,
    last_error: Option<String>,
    model: ModelPane,
    model_dir: PathBuf,
}

impl App {
    fn new(
        args: TuiArgs,
        events: Receiver<TuiEvent>,
        local_tx: Option<Sender<LocalCommand>>,
        forward_tx: Sender<TuiEvent>,
    ) -> Self {
        let dictionary = args
            .dictionary
            .as_ref()
            .and_then(|path| fs::read_to_string(path).ok())
            .map(|text: String| parse_dictionary(&text).overrides().into_iter().collect())
            .unwrap_or_default();
        Self {
            input: args.text,
            output: args.output,
            mode: if args.server.is_some() {
                Mode::Remote
            } else {
                Mode::Local
            },
            server: args.server,
            token: args.token,
            speed: args.speed,
            alpha: args.alpha,
            max_chars: args.max_chars,
            fixed_pauses: args.fixed_pauses,
            peak_normalize: args.peak_normalize,
            dialect: args.dialect,
            resolve_oov: args.resolve_oov,
            srt: args.srt,
            vtt: args.vtt,
            show_settings: false,
            busy: false,
            quit: false,
            status: "Sẵn sàng".to_string(),
            logs: Vec::new(),
            events,
            local_tx,
            forward_tx,
            dictionary,
            last_error: None,
            model: ModelPane::new(),
            model_dir: args.model_dir,
        }
    }

    fn log(&mut self, message: impl Into<String>) {
        self.logs.push(message.into());
        if self.logs.len() > 80 {
            self.logs.remove(0);
        }
    }

    fn make_options(&self) -> SynthesisOptions {
        let dialect = Dialect::from_name(&self.dialect).unwrap_or(Dialect::North);
        let mut parse = live_parse_options(dialect, Some(&self.dictionary), None);
        parse.resolve_oov = self.resolve_oov;
        let mut options = SynthesisOptions {
            speed: self.speed,
            alpha: self.alpha,
            max_chars: self.max_chars.clamp(50, 5000),
            fixed_pauses: self.fixed_pauses,
            peak_normalize: self.peak_normalize,
            parse,
            ..SynthesisOptions::default()
        };
        if options.fixed_pauses {
            options.gate_threshold = 1.01;
        }
        options
    }

    fn synthesize(&mut self) {
        if self.busy {
            return;
        }
        let text = self.input.trim().to_string();
        if text.is_empty() {
            self.last_error = Some("Chưa có text".to_string());
            return;
        }
        self.busy = true;
        self.last_error = None;
        self.status = "Đang tổng hợp…".to_string();
        match self.mode {
            Mode::Local => {
                let Some(tx) = &self.local_tx else {
                    self.busy = false;
                    self.last_error = Some("Local worker chưa sẵn sàng".to_string());
                    return;
                };
                if tx
                    .send(LocalCommand::Synthesize {
                        text,
                        options: self.make_options(),
                    })
                    .is_err()
                {
                    self.busy = false;
                    self.last_error = Some("Local worker đã dừng".to_string());
                }
            }
            Mode::Remote => {
                let Some(server) = self.server.clone() else {
                    self.busy = false;
                    self.last_error = Some("Chưa có --server".to_string());
                    return;
                };
                let token = self.token.clone();
                let event_tx = self.event_sender();
                let speed = self.speed;
                let alpha = self.alpha;
                let max_chars = self.max_chars;
                let fixed = self.fixed_pauses;
                let peak = self.peak_normalize;
                let dialect = self.dialect.clone();
                let resolve_oov = self.resolve_oov;
                let overrides = (!self.dictionary.is_empty()).then(|| self.dictionary.clone());
                thread::spawn(move || {
                    let started = Instant::now();
                    let client = HttpTtsClient::new(server, token.filter(|v| !v.trim().is_empty()));
                    let request = HttpTtsRequest {
                        text,
                        speed,
                        alpha,
                        max_chars,
                        fixed_pauses: fixed,
                        peak_normalize: peak,
                        dialect,
                        resolve_oov,
                        overrides,
                        ..HttpTtsRequest::default()
                    };
                    match client.synthesize_karaoke(&request) {
                        Ok(response) => match response.audio_bytes() {
                            Ok(wav) => {
                                let _ = event_tx.send(TuiEvent::Done {
                                    wav,
                                    elapsed_ms: started.elapsed().as_millis() as u64,
                                    mode: Mode::Remote,
                                    karaoke: Some(response.karaoke),
                                });
                            }
                            Err(error) => {
                                let _ = event_tx.send(TuiEvent::Error(error));
                            }
                        },
                        Err(error) => {
                            let _ = event_tx.send(TuiEvent::Error(error));
                        }
                    }
                });
            }
        }
    }

    fn event_sender(&self) -> Sender<TuiEvent> {
        // TUI chỉ có một receiver; giữ sender qua worker local. Với remote,
        // tạo một cặp channel riêng và chuyển tiếp vào receiver chính.
        // Được thay bằng sender truyền vào App nếu cần mở rộng.
        let (tx, rx) = mpsc::channel();
        let main_tx = self.forward_tx.clone();
        thread::spawn(move || {
            while let Ok(event) = rx.recv() {
                if main_tx.send(event).is_err() {
                    break;
                }
            }
        });
        tx
    }

    fn model_search(&mut self) {
        let query = self.model.query.trim().to_string();
        let query = if query.is_empty() {
            "vifasttts".to_string()
        } else {
            query
        };
        self.model.loading = true;
        self.model.files.clear();
        self.model.repo = None;
        self.model.status = format!("Đang tìm {query}…");
        let manager = ModelManager::new(self.model_dir.clone());
        let tx = self.forward_tx.clone();
        thread::spawn(move || match manager.search(&query, 20) {
            Ok(models) => {
                let _ = tx.send(TuiEvent::ModelResults(models));
            }
            Err(error) => {
                let _ = tx.send(TuiEvent::ModelError(error));
            }
        });
    }

    fn model_load_files(&mut self) {
        let Some(model) = self.model.results.get(self.model.selected) else {
            return;
        };
        let repo = model.id.clone();
        self.model.loading = true;
        self.model.repo = Some(repo.clone());
        self.model.files.clear();
        self.model.status = format!("Đang xem {repo}…");
        let manager = ModelManager::new(self.model_dir.clone());
        let tx = self.forward_tx.clone();
        thread::spawn(move || match manager.files(&repo) {
            Ok(files) => {
                let _ = tx.send(TuiEvent::ModelFiles(files));
            }
            Err(error) => {
                let _ = tx.send(TuiEvent::ModelError(error));
            }
        });
    }

    fn model_download(&mut self) {
        let Some(repo) = self.model.repo.clone() else {
            return;
        };
        let Some(file) = self.model.files.get(self.model.selected) else {
            return;
        };
        let path = file.path.clone();
        self.model.loading = true;
        self.model.status = format!("Đang tải {path}…");
        let manager = ModelManager::new(self.model_dir.clone());
        let tx = self.forward_tx.clone();
        thread::spawn(move || match manager.install(&repo, &path) {
            Ok(model) => {
                let _ = tx.send(TuiEvent::ModelDownloaded(model.path));
            }
            Err(error) => {
                let _ = tx.send(TuiEvent::ModelError(error));
            }
        });
    }

    fn poll(&mut self) {
        while let Ok(event) = self.events.try_recv() {
            match event {
                TuiEvent::Status(message) => self.status = message,
                TuiEvent::Ready(message) => {
                    self.status = message.clone();
                    self.log(message);
                }
                TuiEvent::Done {
                    wav,
                    elapsed_ms,
                    mode,
                    karaoke,
                } => {
                    self.busy = false;
                    self.status = format!("Xong · {elapsed_ms} ms · {}", self.output.display());
                    match fs::write(&self.output, &wav) {
                        Ok(()) => self.log(format!(
                            "{}: đã ghi {} ({} B)",
                            if mode == Mode::Local {
                                "local"
                            } else {
                                "remote"
                            },
                            self.output.display(),
                            wav.len()
                        )),
                        Err(error) => self.last_error = Some(format!("ghi WAV: {error}")),
                    }
                    if let Some(path) = &self.srt {
                        if let Some(document) = &karaoke {
                            if let Err(error) = fs::write(path, document.to_srt()) {
                                self.last_error = Some(format!("ghi SRT: {error}"));
                            } else {
                                self.log(format!("đã ghi {}", path.display()));
                            }
                        } else {
                            self.last_error = Some("Model không có timing để ghi SRT".to_string());
                        }
                    }
                    if let Some(path) = &self.vtt {
                        if let Some(document) = &karaoke {
                            if let Err(error) = fs::write(path, document.to_vtt_karaoke()) {
                                self.last_error = Some(format!("ghi VTT: {error}"));
                            } else {
                                self.log(format!("đã ghi {}", path.display()));
                            }
                        } else {
                            self.last_error = Some("Model không có timing để ghi VTT".to_string());
                        }
                    }
                }
                TuiEvent::Error(error) => {
                    self.busy = false;
                    self.status = "Lỗi".to_string();
                    self.last_error = Some(error.clone());
                    self.log(format!("Lỗi: {error}"));
                }
                TuiEvent::ModelResults(models) => {
                    self.model.loading = false;
                    self.model.results = models;
                    self.model.selected = 0;
                    self.model.status = format!("Thấy {} repo", self.model.results.len());
                }
                TuiEvent::ModelFiles(files) => {
                    self.model.loading = false;
                    self.model.files = files;
                    self.model.selected = 0;
                    self.model.status = format!("Thấy {} bundle", self.model.files.len());
                }
                TuiEvent::ModelDownloaded(path) => {
                    self.model.loading = false;
                    self.model.status = format!("Đã tải {}", path.display());
                    self.log(format!("model: đã tải {}", path.display()));
                    if self.mode == Mode::Local
                        && let Some(tx) = &self.local_tx
                    {
                        let _ = tx.send(LocalCommand::Reload(path));
                    }
                }
                TuiEvent::ModelError(error) => {
                    self.model.loading = false;
                    self.model.status = format!("Lỗi: {error}");
                    self.last_error = Some(error);
                }
            }
        }
    }
}

fn spawn_local(
    acoustic: PathBuf,
    vocoder: PathBuf,
    vfts: Option<PathBuf>,
    vfa: Option<PathBuf>,
    event_tx: Sender<TuiEvent>,
) -> Sender<LocalCommand> {
    let (command_tx, command_rx) = mpsc::channel();
    thread::spawn(move || {
        let _ = event_tx.send(TuiEvent::Status("Đang nạp model local…".to_string()));
        let loaded = if let Some(path) = vfa {
            load_vfa(path, &vocoder)
        } else if let Some(path) = vfts {
            load_vfts(path)
        } else {
            load(&acoustic, &vocoder)
        };
        let mut engine: Option<NativeEngine> = match loaded {
            Ok(engine) => {
                let info = engine.info();
                let _ = event_tx.send(TuiEvent::Ready(format!(
                    "Local sẵn sàng · {} Hz · {} · {}",
                    info.sample_rate, info.arch, info.vocab_version
                )));
                Some(engine)
            }
            Err(error) => {
                let _ = event_tx.send(TuiEvent::Error(format!("nạp model: {error}")));
                None
            }
        };
        while let Ok(command) = command_rx.recv() {
            match command {
                LocalCommand::Synthesize { text, options } => {
                    let Some(engine) = engine.as_mut() else {
                        let _ =
                            event_tx.send(TuiEvent::Error("Model local chưa sẵn sàng".to_string()));
                        continue;
                    };
                    let started = Instant::now();
                    match engine.synthesize(&text, &options) {
                        Ok(result) => {
                            let _ = event_tx.send(TuiEvent::Done {
                                wav: result.wav,
                                elapsed_ms: started.elapsed().as_millis() as u64,
                                mode: Mode::Local,
                                karaoke: result.karaoke,
                            });
                        }
                        Err(error) => {
                            let _ = event_tx.send(TuiEvent::Error(error));
                        }
                    }
                }
                LocalCommand::Reload(path) => match load_bundle(&path, &vocoder) {
                    Ok(new_engine) => {
                        let info = new_engine.info();
                        let message = format!(
                            "Đã đổi model · {} Hz · {} · {}",
                            info.sample_rate, info.arch, info.vocab_version
                        );
                        engine = Some(new_engine);
                        let _ = event_tx.send(TuiEvent::Ready(message));
                    }
                    Err(error) => {
                        let _ = event_tx.send(TuiEvent::Error(format!("đổi model: {error}")));
                    }
                },
            }
        }
    });
    command_tx
}

pub fn run(args: TuiArgs) -> Result<()> {
    let (event_tx, events) = mpsc::channel();
    let local_tx = if args.server.is_none() {
        Some(spawn_local(
            args.acoustic.clone(),
            args.vocoder.clone(),
            args.vfts.clone(),
            args.vfa.clone(),
            event_tx.clone(),
        ))
    } else {
        None
    };
    let mut app = App::new(args, events, local_tx, event_tx);

    enable_raw_mode().context("enable raw mode")?;
    let mut stdout = std::io::stdout();
    execute!(stdout, EnterAlternateScreen).context("enter alternate screen")?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend).context("terminal")?;
    let result = run_loop(&mut terminal, &mut app);
    disable_raw_mode().ok();
    execute!(terminal.backend_mut(), LeaveAlternateScreen).ok();
    terminal.show_cursor().ok();
    result
}

fn run_loop(
    terminal: &mut Terminal<CrosstermBackend<std::io::Stdout>>,
    app: &mut App,
) -> Result<()> {
    loop {
        app.poll();
        terminal.draw(|frame| draw(frame, app))?;
        if event::poll(Duration::from_millis(100))? {
            match event::read()? {
                CrosstermEvent::Key(key) if key.kind == KeyEventKind::Press => handle_key(app, key),
                _ => {}
            }
        }
        if app.quit {
            return Ok(());
        }
    }
}

fn handle_key(app: &mut App, key: KeyEvent) {
    let ctrl = key.modifiers.contains(KeyModifiers::CONTROL);
    if app.model.open {
        handle_model_key(app, key, ctrl);
        return;
    }
    if app.show_settings {
        handle_settings_key(app, key, ctrl);
        return;
    }
    match key.code {
        KeyCode::Char('q') if ctrl => app.quit = true,
        KeyCode::Char('s') if ctrl => app.synthesize(),
        KeyCode::Char('g') if ctrl => app.synthesize(),
        KeyCode::Char('r') if ctrl => app.synthesize(),
        KeyCode::F(5) => app.synthesize(),
        KeyCode::Char('l') if ctrl => app.logs.clear(),
        KeyCode::Char('o') if ctrl => {
            app.model.open = true;
            app.model_search();
        }
        KeyCode::Char('p') if ctrl => {
            app.show_settings = true;
        }
        KeyCode::Char('r') if ctrl => {
            app.last_error = None;
            app.status = "Sẵn sàng".to_string();
        }
        KeyCode::Esc => app.quit = true,
        KeyCode::Backspace => {
            app.input.pop();
        }
        KeyCode::Delete => {
            app.input.clear();
        }
        KeyCode::Enter if ctrl => app.synthesize(),
        KeyCode::Enter => app.input.push('\n'),
        KeyCode::Tab => {
            app.mode = if app.mode == Mode::Local {
                Mode::Remote
            } else {
                Mode::Local
            };
            app.status = format!("Chế độ: {:?}", app.mode);
        }
        KeyCode::Up => {
            app.speed = (app.speed + 0.05).min(2.0);
        }
        KeyCode::Down => {
            app.speed = (app.speed - 0.05).max(0.5);
        }
        KeyCode::Char(c) if !ctrl => app.input.push(c),
        _ => {}
    }
}

fn handle_settings_key(app: &mut App, key: KeyEvent, ctrl: bool) {
    if key.code == KeyCode::Esc || (ctrl && key.code == KeyCode::Char('p')) {
        app.show_settings = false;
        return;
    }
    if ctrl && key.code == KeyCode::Char('s') {
        app.show_settings = false;
        app.synthesize();
        return;
    }
    match key.code {
        KeyCode::Up => app.speed = (app.speed + 0.05).min(2.0),
        KeyCode::Down => app.speed = (app.speed - 0.05).max(0.5),
        KeyCode::Char('a') => app.alpha = (app.alpha + 0.05).min(3.0),
        KeyCode::Char('A') => app.alpha = (app.alpha - 0.05).max(0.5),
        KeyCode::Char('m') => app.max_chars = (app.max_chars + 50).min(5000),
        KeyCode::Char('M') => app.max_chars = app.max_chars.saturating_sub(50).max(50),
        KeyCode::Char('f') => app.fixed_pauses = !app.fixed_pauses,
        KeyCode::Char('p') => app.peak_normalize = !app.peak_normalize,
        KeyCode::Char('o') => app.resolve_oov = !app.resolve_oov,
        KeyCode::Char('d') => {
            app.dialect = match app.dialect.as_str() {
                "north" => "central".to_string(),
                "central" => "south".to_string(),
                _ => "north".to_string(),
            };
        }
        _ => {}
    }
}

fn handle_model_key(app: &mut App, key: KeyEvent, ctrl: bool) {
    if key.code == KeyCode::Esc || (ctrl && key.code == KeyCode::Char('o')) {
        app.model.open = false;
        return;
    }
    if app.model.loading {
        return;
    }
    let file_mode = !app.model.files.is_empty();
    let list_len = if file_mode {
        app.model.files.len()
    } else {
        app.model.results.len()
    };
    match key.code {
        KeyCode::Enter => {
            if app.model.results.is_empty() {
                app.model_search();
            } else if file_mode {
                app.model_download();
            } else {
                app.model_load_files();
            }
        }
        KeyCode::Up => {
            if list_len > 0 {
                app.model.selected = app.model.selected.saturating_sub(1);
            }
        }
        KeyCode::Down => {
            if list_len > 0 {
                app.model.selected = (app.model.selected + 1).min(list_len - 1);
            }
        }
        KeyCode::Backspace => {
            app.model.query.pop();
            app.model.results.clear();
            app.model.files.clear();
            app.model.repo = None;
            app.model.selected = 0;
        }
        KeyCode::Char(character) if !ctrl => {
            app.model.query.push(character);
            app.model.results.clear();
            app.model.files.clear();
            app.model.repo = None;
            app.model.selected = 0;
            app.model.status = "Enter: tìm".to_string();
        }
        _ => {}
    }
}

fn draw_model(frame: &mut Frame, app: &App) {
    let area = frame.area();
    let width = area.width.saturating_sub(8).max(40).min(area.width);
    let height = area.height.saturating_sub(6).max(12).min(area.height);
    let popup = ratatui::layout::Rect::new(
        area.x + (area.width.saturating_sub(width)) / 2,
        area.y + (area.height.saturating_sub(height)) / 2,
        width,
        height,
    );
    frame.render_widget(Clear, popup);
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3),
            Constraint::Percentage(48),
            Constraint::Percentage(38),
            Constraint::Length(2),
        ])
        .split(popup);
    let title = if app.model.loading {
        "Model browser · đang chạy…"
    } else {
        "Model browser · Ctrl+O/Esc đóng"
    };
    let query = Paragraph::new(format!("Tìm: {}", app.model.query))
        .block(Block::default().borders(Borders::ALL).title(title));
    frame.render_widget(query, chunks[0]);

    let bundle_count = |model: &HfModel| {
        model
            .siblings
            .iter()
            .filter(|file| file.rfilename.ends_with(".vfa") || file.rfilename.ends_with(".vfts"))
            .count()
    };
    let result_lines: Vec<Line> = app
        .model
        .results
        .iter()
        .enumerate()
        .map(|(index, model)| {
            let marker = if index == app.model.selected {
                ">"
            } else {
                " "
            };
            Line::from(format!(
                "{marker} {}  ({} bundle)",
                model.id,
                bundle_count(model)
            ))
        })
        .collect();
    let results = Paragraph::new(result_lines)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title("Repo · Enter để xem file"),
        )
        .wrap(Wrap { trim: true });
    frame.render_widget(results, chunks[1]);

    let file_lines: Vec<Line> = app
        .model
        .files
        .iter()
        .enumerate()
        .map(|(index, file)| {
            let marker = if index == app.model.selected {
                ">"
            } else {
                " "
            };
            Line::from(format!(
                "{marker} {}  ({:.1} MB)",
                file.path,
                file.size as f64 / 1e6
            ))
        })
        .collect();
    let title = app
        .model
        .repo
        .as_ref()
        .map(|repo| format!("Bundle · {repo}"))
        .unwrap_or_else(|| "Bundle · chọn repo trước".to_string());
    let files = Paragraph::new(file_lines)
        .block(Block::default().borders(Borders::ALL).title(title))
        .wrap(Wrap { trim: true });
    frame.render_widget(files, chunks[2]);

    let status =
        Paragraph::new(app.model.status.clone()).style(Style::default().fg(Color::LightBlue));
    frame.render_widget(status, chunks[3]);
}

fn draw(frame: &mut Frame, app: &App) {
    let area = frame.area();
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3),
            Constraint::Min(6),
            Constraint::Length(3),
            Constraint::Length(8),
            Constraint::Length(2),
        ])
        .split(area);

    let header = Paragraph::new(Line::from(vec![
        Span::styled(
            " ViFastTts TUI ",
            Style::default()
                .fg(Color::Cyan)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(format!(
            " {:?} · {:.2}× · α{:.2} · {} · {} · {} ký tự",
            app.mode,
            app.speed,
            app.alpha,
            if app.fixed_pauses {
                "fixed"
            } else {
                "model pause"
            },
            app.dialect,
            app.input.chars().count()
        )),
    ]))
    .block(Block::default().borders(Borders::ALL).title("Trạng thái"));
    frame.render_widget(header, chunks[0]);

    let input = Paragraph::new(Text::from(app.input.clone()))
        .block(Block::default().borders(Borders::ALL).title("Văn bản"))
        .wrap(Wrap { trim: false });
    frame.render_widget(input, chunks[1]);

    let status = Paragraph::new(Line::from(format!(
        "{}  ·  output: {}",
        if app.busy {
            "đang chạy…"
        } else {
            &app.status
        },
        app.output.display()
    )))
    .block(Block::default().borders(Borders::ALL).title("Tiến trình"))
    .style(if app.last_error.is_some() {
        Style::default().fg(Color::LightRed)
    } else {
        Style::default().fg(Color::LightBlue)
    });
    frame.render_widget(status, chunks[2]);

    let mut log_lines: Vec<Line> = app
        .logs
        .iter()
        .rev()
        .take(6)
        .map(|line| Line::from(line.as_str()))
        .collect();
    if let Some(error) = &app.last_error {
        log_lines.insert(
            0,
            Line::from(format!("Lỗi: {error}")).style(Style::default().fg(Color::LightRed)),
        );
    }
    let log = Paragraph::new(log_lines)
        .block(Block::default().borders(Borders::ALL).title("Log"))
        .wrap(Wrap { trim: false });
    frame.render_widget(log, chunks[3]);

    let footer = Paragraph::new("Ctrl+Enter/G/R/S hoặc F5 đọc · Ctrl+O model · Ctrl+P cài đặt · Tab local/remote · ↑/↓ speed · Ctrl+L xoá log · Ctrl+Q/Esc thoát")
        .style(Style::default().fg(Color::DarkGray));
    frame.render_widget(footer, chunks[4]);

    if app.show_settings {
        draw_settings(frame, app);
    }
    if app.model.open {
        draw_model(frame, app);
    }
}

fn draw_settings(frame: &mut Frame, app: &App) {
    let area = frame.area();
    let width = area.width.saturating_sub(8).max(44).min(area.width);
    let height = 18.min(area.height);
    let popup = ratatui::layout::Rect::new(
        area.x + (area.width.saturating_sub(width)) / 2,
        area.y + (area.height.saturating_sub(height)) / 2,
        width,
        height,
    );
    frame.render_widget(Clear, popup);
    let lines = vec![
        Line::from(format!("Tốc độ          {:.2}×   ↑/↓", app.speed)),
        Line::from(format!("Alpha mel       {:.2}   a/A", app.alpha)),
        Line::from(format!("Max ký tự/chunk {}      m/M", app.max_chars)),
        Line::from(format!(
            "Pause cố định   {}      f",
            if app.fixed_pauses { "bật" } else { "tắt" }
        )),
        Line::from(format!(
            "Peak normalize  {}      p",
            if app.peak_normalize { "bật" } else { "tắt" }
        )),
        Line::from(format!(
            "Resolve OOV     {}      o",
            if app.resolve_oov { "bật" } else { "tắt" }
        )),
        Line::from(format!("Phương ngữ      {}      d", app.dialect)),
        Line::from(format!(
            "Từ điển         {} quy tắc (--dictionary)",
            app.dictionary.len()
        )),
        Line::from(""),
        Line::from("Esc/Ctrl+P đóng · Ctrl+S đọc với cấu hình này"),
    ];
    let block = Paragraph::new(lines)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title("Cài đặt âm thanh · Ctrl+P"),
        )
        .wrap(Wrap { trim: true });
    frame.render_widget(block, popup);
}
