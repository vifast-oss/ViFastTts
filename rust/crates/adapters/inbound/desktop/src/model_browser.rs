//! Model browser desktop: tìm repo trên HuggingFace, lọc `.vfa`/`.vfts`, tải.
//!
//! Networking chạy background thread; UI không block. Download chỉ tải bundle,
//! không tải raw ONNX.

use std::path::PathBuf;
use std::sync::mpsc::{self, Receiver, Sender};
use std::thread;

use eframe::egui;
use vifasttts_huggingface::{HfFile, HfModel};
use vifasttts_model_manager::ModelManager;

enum Event {
    Models(Vec<HfModel>),
    Files(String, Vec<HfFile>),
    Downloaded(PathBuf),
    Error(String),
}

pub struct ModelBrowser {
    query: String,
    results: Vec<HfModel>,
    files: Vec<HfFile>,
    selected: Option<String>,
    status: String,
    busy: bool,
    tx: Sender<Event>,
    rx: Receiver<Event>,
    download_dir: PathBuf,
    manager: ModelManager,
}

impl ModelBrowser {
    pub fn new(download_dir: PathBuf) -> Self {
        let (tx, rx) = mpsc::channel();
        let manager = ModelManager::new(download_dir.clone());
        Self {
            query: "vifasttts".to_string(),
            results: Vec::new(),
            files: Vec::new(),
            selected: None,
            status: "Tìm model public trên HuggingFace (chỉ tải .vfa/.vfts).".to_string(),
            busy: false,
            tx,
            rx,
            download_dir,
            manager,
        }
    }

    fn search(&mut self) {
        if self.busy {
            return;
        }
        let query = self.query.trim().to_string();
        if query.is_empty() {
            self.status = "Nhập từ khóa".to_string();
            return;
        }
        self.busy = true;
        self.files.clear();
        self.selected = None;
        self.status = format!("Đang tìm `{query}`…");
        let tx = self.tx.clone();
        let manager = self.manager.clone();
        thread::spawn(move || match manager.search(&query, 20) {
            Ok(models) => {
                let _ = tx.send(Event::Models(models));
            }
            Err(error) => {
                let _ = tx.send(Event::Error(error));
            }
        });
    }

    fn select(&mut self, repo: String) {
        if self.busy {
            return;
        }
        self.selected = Some(repo.clone());
        self.files.clear();
        self.busy = true;
        self.status = format!("Đang xem file của {repo}…");
        let tx = self.tx.clone();
        let manager = self.manager.clone();
        thread::spawn(move || match manager.files(&repo) {
            Ok(files) => {
                let _ = tx.send(Event::Files(repo, files));
            }
            Err(error) => {
                let _ = tx.send(Event::Error(error));
            }
        });
    }

    fn download(&mut self, path: String) {
        let Some(repo) = self.selected.clone() else {
            return;
        };
        if self.busy {
            return;
        }
        self.busy = true;
        self.status = format!("Đang tải {path}…");
        let tx = self.tx.clone();
        let manager = self.manager.clone();
        thread::spawn(move || match manager.install(&repo, &path) {
            Ok(model) => {
                let _ = tx.send(Event::Downloaded(model.path));
            }
            Err(error) => {
                let _ = tx.send(Event::Error(error));
            }
        });
    }

    /// Trả path khi tải xong để DesktopApp nạp model.
    pub fn poll(&mut self) -> Option<PathBuf> {
        let mut downloaded = None;
        while let Ok(event) = self.rx.try_recv() {
            match event {
                Event::Models(models) => {
                    self.busy = false;
                    self.results = models;
                    self.status = format!("{} repo; chọn repo để xem bundle.", self.results.len());
                }
                Event::Files(repo, files) => {
                    self.busy = false;
                    self.selected = Some(repo);
                    self.files = files;
                    self.status = if self.files.is_empty() {
                        "Repo này chưa có .vfa/.vfts (raw ONNX không dùng để tải).".to_string()
                    } else {
                        format!("{} bundle.", self.files.len())
                    };
                }
                Event::Downloaded(path) => {
                    self.busy = false;
                    self.status = format!("Đã tải {}", path.display());
                    downloaded = Some(path);
                }
                Event::Error(error) => {
                    self.busy = false;
                    self.status = format!("Lỗi: {error}");
                }
            }
        }
        downloaded
    }

    pub fn ui(&mut self, ui: &mut egui::Ui) {
        ui.horizontal(|ui| {
            ui.label("Tìm trên HuggingFace");
            ui.add(egui::TextEdit::singleline(&mut self.query).desired_width(260.0));
            if ui
                .add_enabled(!self.busy, egui::Button::new("Tìm"))
                .clicked()
            {
                self.search();
            }
            if self.busy {
                ui.spinner();
            }
        });
        ui.small("Chỉ hiển thị file `.vfa`/`.vfts`; raw `acoustic.onnx` bị bỏ qua.");
        ui.label(&self.status);
        ui.separator();

        egui::ScrollArea::vertical()
            .id_salt("hf_models")
            .max_height(170.0)
            .show(ui, |ui| {
                let mut choose = None;
                for model in &self.results {
                    let selected = self.selected.as_deref() == Some(model.id.as_str());
                    let text = format!(
                        "{}  · {} downloads · {} likes",
                        model.id, model.downloads, model.likes
                    );
                    if ui.selectable_label(selected, text).clicked() {
                        choose = Some(model.id.clone());
                    }
                }
                if let Some(repo) = choose {
                    self.select(repo);
                }
            });

        if let Some(repo) = &self.selected {
            ui.label(format!("Bundle trong {repo}"));
            egui::ScrollArea::vertical()
                .id_salt("hf_files")
                .max_height(140.0)
                .show(ui, |ui| {
                    let mut choose = None;
                    for file in &self.files {
                        let text = format!("{}  · {:.1} MB", file.path, file.size as f64 / 1e6);
                        if ui
                            .add_enabled(!self.busy, egui::Button::new(text))
                            .clicked()
                        {
                            choose = Some(file.path.clone());
                        }
                    }
                    if let Some(path) = choose {
                        self.download(path);
                    }
                });
        }
        ui.small(format!("Lưu tại: {}", self.download_dir.display()));
        ui.small("Model tải về sẽ được kiểm manifest/hash khi nạp; license CC-BY-NC.");
    }
}
