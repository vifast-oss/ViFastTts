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
