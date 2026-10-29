//! Model browser desktop: tìm repo trên HuggingFace, lọc `.vfa`/`.vfts`, tải.
//!
//! Networking chạy background thread; UI không block. Download chỉ tải bundle,
//! không tải raw ONNX. State chuyển/search/files tách sang
//! `vifasttts_model_manager::ModelBrowserState` để TUI/CLI dùng lại.

use std::path::PathBuf;
use std::sync::mpsc::{self, Receiver, Sender};
use std::thread;

use eframe::egui;
use vifasttts_huggingface::{HfFile, HfModel};
use vifasttts_model_manager::{ModelBrowserState, ModelManager};

enum Event {
    Models(Vec<HfModel>),
    Files(String, Vec<HfFile>),
    Downloaded(PathBuf),
    Error(String),
}

pub struct ModelBrowser {
    state: ModelBrowserState,
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
            state: ModelBrowserState::new(),
            tx,
            rx,
            download_dir,
            manager,
        }
    }

    fn search(&mut self) {
        if !self.state.start_search(&self.state.query.clone()) {
            return;
        }
        let query = self.state.query.clone();
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
        if !self.state.start_files(&repo) {
            return;
        }
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
        let Some(repo) = self.state.selected.clone() else {
            return;
        };
        if !self.state.start_download(&path) {
            return;
        }
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
                Event::Models(models) => self.state.finish_search(models),
                Event::Files(repo, files) => self.state.finish_files(&repo, files),
                Event::Downloaded(path) => {
                    self.state.finish_download(&path);
                    downloaded = Some(path);
                }
                Event::Error(error) => self.state.fail(error),
            }
        }
        downloaded
    }

    pub fn ui(&mut self, ui: &mut egui::Ui) {
        ui.horizontal(|ui| {
            ui.label("Tìm trên HuggingFace");
            ui.add(egui::TextEdit::singleline(&mut self.state.query).desired_width(260.0));
            if ui
                .add_enabled(!self.state.busy, egui::Button::new("Tìm"))
                .clicked()
            {
                self.search();
            }
            if self.state.busy {
                ui.spinner();
            }
        });
        ui.small("Chỉ hiển thị file `.vfa`/`.vfts`; raw `acoustic.onnx` bị bỏ qua.");
        ui.label(&self.state.status);
        if let Some(error) = &self.state.error {
            ui.colored_label(egui::Color32::from_rgb(0xB9, 0x1C, 0x1C), error);
        }
        ui.separator();

        egui::ScrollArea::vertical()
            .id_salt("hf_models")
            .max_height(170.0)
            .show(ui, |ui| {
                let mut choose = None;
                for model in &self.state.models {
                    let selected = self.state.selected.as_deref() == Some(model.id.as_str());
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

        if let Some(repo) = &self.state.selected {
            ui.label(format!("Bundle trong {repo}"));
            egui::ScrollArea::vertical()
                .id_salt("hf_files")
                .max_height(140.0)
                .show(ui, |ui| {
                    let mut choose = None;
                    for file in &self.state.files {
                        let text = format!("{}  · {:.1} MB", file.path, file.size as f64 / 1e6);
                        if ui
                            .add_enabled(!self.state.busy, egui::Button::new(text))
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
