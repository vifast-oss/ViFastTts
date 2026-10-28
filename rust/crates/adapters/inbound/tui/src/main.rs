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
use ratatui::widgets::{Block, Borders, Paragraph, Wrap};
use ratatui::{Frame, Terminal};

use vifasttts_app::parse_dictionary;
use vifasttts_http_client::{HttpTtsClient, HttpTtsRequest};
use vifasttts_native::{NativeEngine, SynthesisOptions, load, load_vfts};
use vifasttts_text::dialect::Dialect;
use vifasttts_text::pipeline::live_parse_options;

#[derive(Parser, Debug)]
#[command(name = "vifasttts-tui", version, about = "Terminal UI cho ViFastTts")]
struct Args {
    #[arg(long, default_value = "Xin chào, đây là bản TUI của ViFastTts.")]
    text: String,
    #[arg(long, default_value = "out-tui.wav")]
    output: PathBuf,
    #[arg(long, default_value = "artifacts/onnx/n0_q/acoustic.onnx")]
    acoustic: PathBuf,
    #[arg(long, default_value = "artifacts/onnx/n0_q/vocoder.onnx")]
    vocoder: PathBuf,
    /// Dùng server HTTP thay vì nạp model local.
    #[arg(long)]
    server: Option<String>,
    #[arg(long)]
    token: Option<String>,
    #[arg(long, default_value_t = 1.0)]
    speed: f32,
    #[arg(long)]
    fixed_pauses: bool,
    /// File từ điển `key = cách đọc` (tuỳ chọn).
    #[arg(long)]
    dictionary: Option<PathBuf>,
    /// Nạp model từ bundle `.vfts`.
    #[arg(long)]
    vfts: Option<PathBuf>,
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
    },
    Error(String),
}

enum LocalCommand {
    Synthesize {
        text: String,
        options: SynthesisOptions,
    },
}

struct App {
    input: String,
    output: PathBuf,
    mode: Mode,
    server: Option<String>,
    token: Option<String>,
    speed: f32,
    fixed_pauses: bool,
    busy: bool,
    quit: bool,
    status: String,
    logs: Vec<String>,
    events: Receiver<TuiEvent>,
    local_tx: Option<Sender<LocalCommand>>,
    forward_tx: Sender<TuiEvent>,
    dictionary: HashMap<String, String>,
    last_error: Option<String>,
}

impl App {
    fn new(
        args: Args,
        events: Receiver<TuiEvent>,
        local_tx: Option<Sender<LocalCommand>>,
        forward_tx: Sender<TuiEvent>,
    ) -> Self {
        let dictionary = args
            .dictionary
            .as_ref()
            .and_then(|path| fs::read_to_string(path).ok())
            .map(|text| parse_dictionary(&text).overrides().into_iter().collect())
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
            fixed_pauses: args.fixed_pauses,
            busy: false,
            quit: false,
            status: "Sẵn sàng".to_string(),
            logs: Vec::new(),
            events,
            local_tx,
            forward_tx,
            dictionary,
            last_error: None,
        }
    }

    fn log(&mut self, message: impl Into<String>) {
        self.logs.push(message.into());
        if self.logs.len() > 80 {
            self.logs.remove(0);
        }
    }

    fn make_options(&self) -> SynthesisOptions {
        let mut parse = live_parse_options(Dialect::North, Some(&self.dictionary), None);
        parse.resolve_oov = true;
        let mut options = SynthesisOptions {
            speed: self.speed,
            fixed_pauses: self.fixed_pauses,
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
                let fixed = self.fixed_pauses;
                thread::spawn(move || {
                    let started = Instant::now();
                    let client = HttpTtsClient::new(server, token.filter(|v| !v.trim().is_empty()));
                    let request = HttpTtsRequest {
                        text,
                        speed,
                        fixed_pauses: fixed,
                    };
                    match client.synthesize_wav(&request) {
                        Ok(wav) => {
                            let _ = event_tx.send(TuiEvent::Done {
                                wav,
                                elapsed_ms: started.elapsed().as_millis() as u64,
                                mode: Mode::Remote,
                            });
                        }
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
                }
                TuiEvent::Error(error) => {
                    self.busy = false;
                    self.status = "Lỗi".to_string();
                    self.last_error = Some(error.clone());
                    self.log(format!("Lỗi: {error}"));
                }
            }
        }
    }
}

fn spawn_local(
    acoustic: PathBuf,
    vocoder: PathBuf,
    vfts: Option<PathBuf>,
    event_tx: Sender<TuiEvent>,
) -> Sender<LocalCommand> {
    let (command_tx, command_rx) = mpsc::channel();
    thread::spawn(move || {
        let _ = event_tx.send(TuiEvent::Status("Đang nạp model local…".to_string()));
        let loaded = if let Some(path) = vfts {
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
            let LocalCommand::Synthesize { text, options } = command;
            {
                let Some(engine) = engine.as_mut() else {
                    let _ = event_tx.send(TuiEvent::Error("Model local chưa sẵn sàng".to_string()));
                    continue;
                };
                let started = Instant::now();
                match engine.synthesize(&text, &options) {
                    Ok(result) => {
                        let _ = event_tx.send(TuiEvent::Done {
                            wav: result.wav,
                            elapsed_ms: started.elapsed().as_millis() as u64,
                            mode: Mode::Local,
                        });
                    }
                    Err(error) => {
                        let _ = event_tx.send(TuiEvent::Error(error));
                    }
                }
            }
        }
    });
    command_tx
}

fn main() -> Result<()> {
    let args = Args::parse();
    let (event_tx, events) = mpsc::channel();
    let local_tx = if args.server.is_none() {
        Some(spawn_local(
            args.acoustic.clone(),
            args.vocoder.clone(),
            args.vfts.clone(),
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
    match key.code {
        KeyCode::Char('q') if ctrl => app.quit = true,
        KeyCode::Char('s') if ctrl => app.synthesize(),
        KeyCode::Char('l') if ctrl => app.logs.clear(),
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
            " {:?} · {:.2}× · {} · {} ký tự",
            app.mode,
            app.speed,
            if app.fixed_pauses {
                "fixed"
            } else {
                "model pause"
            },
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

    let footer = Paragraph::new("Ctrl+Enter đọc · Ctrl+S đọc · Tab đổi local/remote · ↑/↓ speed · Ctrl+L xoá log · Ctrl+Q/Esc thoát")
        .style(Style::default().fg(Color::DarkGray));
    frame.render_widget(footer, chunks[4]);
}
