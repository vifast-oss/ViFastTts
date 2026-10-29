//! Shared native model catalog/download manager.
//!
//! Dùng chung cho CLI/desktop/server/TUI; web/extension/mobile dùng HTTP
//! `/api/models/*` của server để không lặp logic.

use std::path::{Path, PathBuf};

use vifasttts_huggingface::{HfFile, HfModel, bundle_files, download, download_bytes, search};
use vifasttts_vfts::{VfaBundle, VftsBundle};

#[derive(Clone, Debug, serde::Serialize, serde::Deserialize)]
pub struct InstalledModel {
    pub name: String,
    pub path: PathBuf,
    pub kind: String,
    pub size: u64,
}

/// State machine dùng chung cho model browser (desktop/TUI/CLI).
///
/// Không chứa networking/UI; adapter chỉ gọi `start_*` rồi `finish_*`/`fail`.
#[derive(Clone, Debug)]
pub struct ModelBrowserState {
    pub query: String,
    pub models: Vec<HfModel>,
    pub files: Vec<HfFile>,
    pub selected: Option<String>,
    pub status: String,
    pub busy: bool,
    pub error: Option<String>,
}

impl Default for ModelBrowserState {
    fn default() -> Self {
        Self {
            query: "vifasttts".to_string(),
            models: Vec::new(),
            files: Vec::new(),
            selected: None,
            status: "Tìm model public trên HuggingFace (chỉ tải .vfa/.vfts).".to_string(),
            busy: false,
            error: None,
        }
    }
}

impl ModelBrowserState {
    pub fn new() -> Self {
        Self::default()
    }

    /// Trả false nếu đang bận; UI không được phát request thứ hai.
    pub fn start_search(&mut self, query: &str) -> bool {
        if self.busy {
            return false;
        }
        let query = query.trim();
        if query.is_empty() {
            self.status = "Nhập từ khóa".to_string();
            self.error = Some(self.status.clone());
            return false;
        }
        self.busy = true;
        self.error = None;
        self.files.clear();
        self.selected = None;
        self.query = query.to_string();
        self.status = format!("Đang tìm `{query}`…");
        true
    }

    pub fn finish_search(&mut self, models: Vec<HfModel>) {
        self.busy = false;
        self.models = models;
        self.status = format!("{} repo; chọn repo để xem bundle.", self.models.len());
    }

    pub fn start_files(&mut self, repo: &str) -> bool {
        if self.busy {
            return false;
        }
        self.busy = true;
        self.error = None;
        self.selected = Some(repo.to_string());
        self.files.clear();
        self.status = format!("Đang xem file của {repo}…");
        true
    }

    pub fn finish_files(&mut self, repo: &str, files: Vec<HfFile>) {
        self.busy = false;
        self.selected = Some(repo.to_string());
        self.files = files;
        self.status = if self.files.is_empty() {
            "Repo này chưa có .vfa/.vfts (raw ONNX không dùng để tải).".to_string()
        } else {
            format!("{} bundle.", self.files.len())
        };
    }

    pub fn start_download(&mut self, path: &str) -> bool {
        if self.busy || self.selected.is_none() {
            return false;
        }
        self.busy = true;
        self.error = None;
        self.status = format!("Đang tải {path}…");
        true
    }

    pub fn finish_download(&mut self, path: &std::path::Path) {
        self.busy = false;
        self.status = format!("Đã tải {}", path.display());
    }

    pub fn fail(&mut self, error: impl Into<String>) {
        let error = error.into();
        self.busy = false;
        self.status = format!("Lỗi: {error}");
        self.error = Some(error);
    }
}

#[derive(Clone, Debug)]
pub struct ModelManager {
    directory: PathBuf,
}

impl ModelManager {
    pub fn new(directory: impl Into<PathBuf>) -> Self {
        Self {
            directory: directory.into(),
        }
    }

    pub fn directory(&self) -> &Path {
        &self.directory
    }

    pub fn search(&self, query: &str, limit: usize) -> Result<Vec<HfModel>, String> {
        search(query, limit)
    }

    pub fn files(&self, repo: &str) -> Result<Vec<HfFile>, String> {
        bundle_files(repo)
    }

    /// Tải, kiểm manifest/hash của bundle, lưu local; trả metadata.
    pub fn install(&self, repo: &str, path: &str) -> Result<InstalledModel, String> {
        let destination = download(repo, path, &self.directory)?;
        let extension = destination
            .extension()
            .and_then(|value| value.to_str())
            .unwrap_or_default();
        let valid = match extension {
            "vfa" => VfaBundle::read_path(&destination).map(|_| ()),
            "vfts" => VftsBundle::read_path(&destination).map(|_| ()),
            _ => Err("không phải .vfa/.vfts".to_string()),
        };
        if let Err(error) = valid {
            let _ = std::fs::remove_file(&destination);
            return Err(error);
        }
        self.describe(&destination)
            .ok_or_else(|| "không mô tả được model".to_string())
    }

    /// Tải + lưu cache server rồi trả bytes cho UI remote.
    pub fn install_and_read(&self, repo: &str, path: &str) -> Result<Vec<u8>, String> {
        let model = self.install(repo, path)?;
        std::fs::read(&model.path).map_err(|error| format!("đọc {}: {error}", model.path.display()))
    }

    /// Proxy bytes cho web/extension/mobile, vẫn kiểm bundle trước khi trả.
    pub fn install_bytes(&self, repo: &str, path: &str) -> Result<Vec<u8>, String> {
        let bytes = download_bytes(repo, path)?;
        match path.rsplit('.').next().unwrap_or_default() {
            "vfa" => VfaBundle::read_bytes(&bytes).map(|_| ())?,
            "vfts" => VftsBundle::read_bytes(&bytes).map(|_| ())?,
            _ => return Err("chỉ trả .vfa/.vfts".to_string()),
        }
        Ok(bytes)
    }

    pub fn installed(&self) -> Vec<InstalledModel> {
        let Ok(read_dir) = std::fs::read_dir(&self.directory) else {
            return Vec::new();
        };
        read_dir
            .filter_map(Result::ok)
            .filter_map(|entry| self.describe(&entry.path()))
            .collect()
    }

    fn describe(&self, path: &Path) -> Option<InstalledModel> {
        let extension = path.extension()?.to_str()?.to_ascii_lowercase();
        if extension != "vfa" && extension != "vfts" {
            return None;
        }
        let size = std::fs::metadata(path).ok()?.len();
        Some(InstalledModel {
            name: path.file_name()?.to_string_lossy().to_string(),
            path: path.to_path_buf(),
            kind: extension,
            size,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn browser_state_transitions_va_chan_request_khi_busy() {
        let mut state = ModelBrowserState::new();
        assert!(state.start_search("vifasttts"));
        assert!(!state.start_search("khac"));
        state.finish_search(vec![HfModel {
            id: "dvchd/demo".to_string(),
            downloads: 1,
            likes: 2,
            tags: vec![],
            siblings: vec![],
            pipeline_tag: None,
        }]);
        assert!(!state.busy);
        assert_eq!(state.models.len(), 1);
        assert!(state.start_files("dvchd/demo"));
        state.finish_files(
            "dvchd/demo",
            vec![HfFile {
                path: "bundles/a.vfts".to_string(),
                size: 10,
                kind: Some("file".to_string()),
            }],
        );
        assert_eq!(state.files.len(), 1);
        assert!(state.start_download("bundles/a.vfts"));
        state.finish_download(std::path::Path::new("/tmp/a.vfts"));
        assert!(state.status.contains("Đã tải"));
        state.fail("mất mạng");
        assert_eq!(state.error.as_deref(), Some("mất mạng"));
    }

    #[test]
    fn installed_chi_lay_bundle() {
        let directory = std::env::temp_dir().join(format!(
            "vifasttts-model-manager-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        ));
        std::fs::create_dir_all(&directory).unwrap();
        std::fs::write(directory.join("a.vfa"), b"x").unwrap();
        std::fs::write(directory.join("b.vfts"), b"xy").unwrap();
        std::fs::write(directory.join("note.txt"), b"x").unwrap();
        let manager = ModelManager::new(&directory);
        let found = manager.installed();
        assert_eq!(found.len(), 2);
        assert!(found.iter().any(|model| model.kind == "vfa"));
        assert!(found.iter().any(|model| model.kind == "vfts"));
        std::fs::remove_dir_all(directory).unwrap();
    }
}
