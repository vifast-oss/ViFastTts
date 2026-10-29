//! Tìm/tải bundle model `.vfa`/`.vfts` từ HuggingFace.
//!
//! Public API không cần token; set `HF_TOKEN` cho repo private. Loader vẫn là
//! `vifasttts-vfts`/`vifasttts-native` ở phía sau.

use std::collections::HashSet;
use std::fs;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

const API: &str = "https://huggingface.co";
const MAX_DOWNLOAD: u64 = 512 * 1024 * 1024;

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct HfModel {
    pub id: String,
    #[serde(default)]
    pub downloads: u64,
    #[serde(default)]
    pub likes: u64,
    #[serde(default)]
    pub tags: Vec<String>,
    #[serde(default)]
    pub siblings: Vec<HfSibling>,
    #[serde(default)]
    pub pipeline_tag: Option<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct HfSibling {
    pub rfilename: String,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct HfFile {
    pub path: String,
    #[serde(default)]
    pub size: u64,
    #[serde(rename = "type", default)]
    pub kind: Option<String>,
}

impl HfFile {
    pub fn is_bundle(&self) -> bool {
        matches!(self.kind.as_deref(), None | Some("file"))
            && (self.path.ends_with(".vfa") || self.path.ends_with(".vfts"))
    }
}

fn agent() -> ureq::Agent {
    ureq::Agent::new_with_defaults()
}

fn auth<T>(request: ureq::RequestBuilder<T>, token: Option<&str>) -> ureq::RequestBuilder<T> {
    match token.filter(|value| !value.trim().is_empty()) {
        Some(token) => request.header("Authorization", &format!("Bearer {token}")),
        None => request,
    }
}

fn token_from_env() -> Option<String> {
    std::env::var("HF_TOKEN").ok()
}

/// Tìm model theo query; không lọc bundle (UI tự kiểm tra `siblings`).
pub fn search(query: &str, limit: usize) -> Result<Vec<HfModel>, String> {
    let query = urlencoding::encode(query);
    let url = format!(
        "{API}/api/models?search={query}&limit={}&full=true",
        limit.clamp(1, 50)
    );
    let mut response = agent()
        .get(&url)
        .call()
        .map_err(|error| format!("GET HuggingFace search: {error}"))?;
    response
        .body_mut()
        .read_json::<Vec<HfModel>>()
        .map_err(|error| format!("parse HuggingFace search: {error}"))
}

/// Liệt kê file bundle trong repo; dùng tree API để có size.
pub fn bundle_files(repo: &str) -> Result<Vec<HfFile>, String> {
    let repo = repo.trim_matches('/');
    let url = format!("{API}/api/models/{repo}/tree/main?recursive=true");
    let token = token_from_env();
    let mut response = auth(agent().get(&url), token.as_deref())
        .call()
        .map_err(|error| format!("GET HuggingFace tree {repo}: {error}"))?;
    let entries: Vec<HfFile> = response
        .body_mut()
        .read_json()
        .map_err(|error| format!("parse HuggingFace tree: {error}"))?;
    // Repo có thể mirror cùng bundle ở `bundles/` và `resources/`; chỉ trả một
    // đại diện (tên file + size) để model browser không hiện trùng.
    let mut seen = HashSet::new();
    Ok(entries
        .into_iter()
        .filter(HfFile::is_bundle)
        .filter(|file| {
            let name = Path::new(&file.path)
                .file_name()
                .and_then(|value| value.to_str())
                .unwrap_or(&file.path);
            seen.insert((name.to_string(), file.size))
        })
        .collect())
}

/// File bundle từ `siblings` của search (không cần gọi tree).
pub fn bundles_from_siblings(model: &HfModel) -> Vec<String> {
    let mut seen = HashSet::new();
    model
        .siblings
        .iter()
        .map(|file| file.rfilename.clone())
        .filter(|path| path.ends_with(".vfa") || path.ends_with(".vfts"))
        .filter(|path| {
            let name = Path::new(path)
                .file_name()
                .and_then(|value| value.to_str())
                .unwrap_or(path);
            seen.insert(name.to_string())
        })
        .collect()
}

fn encode_path(path: &str) -> String {
    path.split('/')
        .map(|part| urlencoding::encode(part).into_owned())
        .collect::<Vec<_>>()
        .join("/")
}

/// Tải bundle vào bộ nhớ (dùng cho server proxy/UI remote).
pub fn download_bytes(repo: &str, path: &str) -> Result<Vec<u8>, String> {
    if !(path.ends_with(".vfa") || path.ends_with(".vfts")) {
        return Err("chỉ tải .vfa/.vfts".to_string());
    }
    let url = format!(
        "{API}/{}/resolve/main/{}",
        repo.trim_matches('/'),
        encode_path(path)
    );
    let token = token_from_env();
    let mut response = auth(agent().get(&url), token.as_deref())
        .call()
        .map_err(|error| format!("GET {url}: {error}"))?;
    if let Some(length) = response
        .headers()
        .get("content-length")
        .and_then(|value| value.to_str().ok())
        .and_then(|value| value.parse::<u64>().ok())
        && length > MAX_DOWNLOAD
    {
        return Err(format!("model quá lớn: {length} B"));
    }
    let bytes = response
        .body_mut()
        .with_config()
        .limit(MAX_DOWNLOAD)
        .read_to_vec()
        .map_err(|error| format!("tải {url}: {error}"))?;
    if bytes.len() as u64 > MAX_DOWNLOAD {
        return Err("model vượt giới hạn tải".to_string());
    }
    Ok(bytes)
}

/// Tải một bundle vào thư mục đích; trả đường dẫn file.
pub fn download(repo: &str, path: &str, directory: impl AsRef<Path>) -> Result<PathBuf, String> {
    let bytes = download_bytes(repo, path)?;
    let directory = directory.as_ref();
    fs::create_dir_all(directory)
        .map_err(|error| format!("tạo {}: {error}", directory.display()))?;
    let name = Path::new(path)
        .file_name()
        .and_then(|value| value.to_str())
        .ok_or_else(|| "tên file không hợp lệ".to_string())?;
    let destination = directory.join(name);
    fs::write(&destination, &bytes)
        .map_err(|error| format!("ghi {}: {error}", destination.display()))?;
    Ok(destination)
}
