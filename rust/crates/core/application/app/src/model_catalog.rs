//! Hợp đồng catalog model dùng chung cho UI native.
//!
//! Không chứa HTTP client: Android/iOS vẫn dùng URLSession/HttpURLConnection vì
//! TLS/redirect/network stack khác nhau. Phần dễ lệch — ghép URL, lọc bundle,
//! dedupe và chuẩn hoá response — nằm ở đây để mọi client dùng cùng một luật.

use serde::{Deserialize, Serialize};

const HF_API: &str = "https://huggingface.co";
const DEFAULT_LIMIT: u32 = 20;
const DEFAULT_SERVER: &str = "http://127.0.0.1:8000";

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ModelUrls {
    pub search: String,
    pub files: String,
    pub download: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ModelSummary {
    pub id: String,
    pub bundle_count: usize,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct CatalogFile {
    pub path: String,
    pub size: u64,
}

fn encode_query(value: &str) -> String {
    urlencoding::encode(value).into_owned()
}

fn encode_path(value: &str) -> String {
    value
        .split('/')
        .map(|part| urlencoding::encode(part).into_owned())
        .collect::<Vec<_>>()
        .join("/")
}

fn encode_repo(repo: &str) -> String {
    encode_path(repo.trim_matches('/'))
}

fn normalized_base(base: &str) -> String {
    let base = base.trim().trim_end_matches('/');
    if base.is_empty() {
        DEFAULT_SERVER.to_string()
    } else {
        base.to_string()
    }
}

/// URL cho cả 3 thao tác catalog. `direct=true` = gọi HuggingFace trực tiếp;
/// `false` = gọi server `/api/models/*` (giữ token/rate-limit ở server).
pub fn model_urls(
    base: &str,
    query: &str,
    repo: &str,
    path: &str,
    limit: u32,
    direct: bool,
) -> ModelUrls {
    let query = if query.trim().is_empty() {
        "vifasttts"
    } else {
        query.trim()
    };
    let limit = if limit == 0 {
        DEFAULT_LIMIT
    } else {
        limit.clamp(1, 50)
    };
    let repo = repo.trim_matches('/');
    let path = path.trim_start_matches('/');
    if direct {
        ModelUrls {
            search: format!(
                "{HF_API}/api/models?search={}&limit={limit}&full=true",
                encode_query(query)
            ),
            files: if repo.is_empty() {
                String::new()
            } else {
                format!(
                    "{HF_API}/api/models/{}/tree/main?recursive=true",
                    encode_repo(repo)
                )
            },
            download: if repo.is_empty() || path.is_empty() {
                String::new()
            } else {
                format!(
                    "{HF_API}/{}/resolve/main/{}",
                    encode_repo(repo),
                    encode_path(path)
                )
            },
        }
    } else {
        let base = normalized_base(base);
        ModelUrls {
            search: format!(
                "{base}/api/models/search?q={}&limit={limit}",
                encode_query(query)
            ),
            files: if repo.is_empty() {
                String::new()
            } else {
                format!("{base}/api/models/files?repo={}", encode_repo(repo))
            },
            download: if repo.is_empty() || path.is_empty() {
                String::new()
            } else {
                format!(
                    "{base}/api/models/download?repo={}&path={}",
                    encode_repo(repo),
                    encode_path(path)
                )
            },
        }
    }
}

pub fn model_urls_json(
    base: &str,
    query: &str,
    repo: &str,
    path: &str,
    limit: u32,
    direct: bool,
) -> Result<String, String> {
    let urls = model_urls(base, query, repo, path, limit, direct);
    serde_json::to_string(&urls).map_err(|error| format!("model URLs JSON: {error}"))
}

#[derive(Debug, Deserialize)]
struct RawModel {
    id: String,
    #[serde(default)]
    siblings: Vec<RawSibling>,
}

#[derive(Debug, Deserialize)]
struct RawSibling {
    #[serde(default, alias = "path")]
    rfilename: String,
}

fn is_bundle(path: &str) -> bool {
    path.ends_with(".vfa") || path.ends_with(".vfts")
}

fn bundle_name(path: &str) -> &str {
    path.rsplit('/').next().unwrap_or(path)
}

fn bundle_count(model: &RawModel) -> usize {
    let mut seen = std::collections::HashSet::new();
    model
        .siblings
        .iter()
        .map(|file| file.rfilename.as_str())
        .filter(|path| is_bundle(path))
        .filter(|path| seen.insert(bundle_name(path).to_string()))
        .count()
}

/// Chuẩn hoá response search (HF hoặc server) thành `[{id,bundle_count}]`.
///
/// UI không cần biết server trả `siblings` hay `path`; chỉ hiển thị số bundle.
pub fn normalize_search_json(raw: &str) -> Result<String, String> {
    let models: Vec<RawModel> =
        serde_json::from_str(raw).map_err(|error| format!("model search JSON: {error}"))?;
    let summaries: Vec<ModelSummary> = models
        .into_iter()
        .map(|model| {
            let count = bundle_count(&model);
            ModelSummary {
                id: model.id,
                bundle_count: count,
            }
        })
        .collect();
    serde_json::to_string(&summaries).map_err(|error| format!("model search summary: {error}"))
}

#[derive(Debug, Deserialize)]
struct RawFile {
    #[serde(default)]
    path: String,
    #[serde(default)]
    size: u64,
    #[serde(default, rename = "type")]
    kind: Option<String>,
}

/// Chuẩn hoá tree/server files thành `[{path,size}]`, chỉ bundle và dedupe.
///
/// Repo HF có thể mirror cùng bundle ở `bundles/` và `resources/`; dedupe theo
/// `(tên file, size)` giống `vifasttts-huggingface::bundle_files`.
pub fn normalize_files_json(raw: &str, _direct: bool) -> Result<String, String> {
    let entries: Vec<RawFile> =
        serde_json::from_str(raw).map_err(|error| format!("model files JSON: {error}"))?;
    let mut seen = std::collections::HashSet::new();
    let files: Vec<CatalogFile> = entries
        .into_iter()
        .filter(|file| matches!(file.kind.as_deref(), None | Some("file")))
        .filter(|file| is_bundle(&file.path))
        .filter(|file| seen.insert((bundle_name(&file.path).to_string(), file.size)))
        .map(|file| CatalogFile {
            path: file.path,
            size: file.size,
        })
        .collect();
    serde_json::to_string(&files).map_err(|error| format!("model files summary: {error}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn direct_urls_encode_repo_and_path() {
        let urls = model_urls(
            "",
            "ngọc huyền",
            "dvchd/model",
            "bundles/a b.vfts",
            20,
            true,
        );
        assert!(urls.search.contains("search=ng%E1%BB%8Dc%20huy%E1%BB%81n"));
        assert!(urls.files.contains("dvchd/model/tree/main"));
        assert!(urls.download.contains("a%20b.vfts"));
    }

    #[test]
    fn server_urls_fallback_and_repo_encoding() {
        let urls = model_urls(
            "http://127.0.0.1:8000/",
            "vifasttts",
            "dvchd/a b",
            "x.vfa",
            5,
            false,
        );
        assert!(
            urls.search
                .starts_with("http://127.0.0.1:8000/api/models/search?")
        );
        assert!(urls.files.contains("repo=dvchd/a%20b"));
        assert!(urls.download.contains("path=x.vfa"));
        assert!(
            model_urls("", "q", "r", "p", 20, false)
                .files
                .starts_with(DEFAULT_SERVER)
        );
    }

    #[test]
    fn search_summary_counts_unique_bundle_names() {
        let raw = r#"[
          {"id":"a","siblings":[{"rfilename":"bundles/x.vfts"},{"rfilename":"resources/x.vfts"},{"rfilename":"onnx/a.onnx"}]},
          {"id":"b","siblings":[]}
        ]"#;
        let value: serde_json::Value =
            serde_json::from_str(&normalize_search_json(raw).unwrap()).unwrap();
        assert_eq!(value[0]["bundle_count"], 1);
        assert_eq!(value[1]["bundle_count"], 0);
    }

    #[test]
    fn file_summary_filters_kind_and_dedupes_by_name_size() {
        let raw = r#"[
          {"path":"bundles/x.vfts","size":10,"type":"file"},
          {"path":"resources/x.vfts","size":10,"type":"file"},
          {"path":"bundles/y.vfa","size":20},
          {"path":"onnx/a.onnx","size":30,"type":"file"},
          {"path":"bundles/z.vfts","size":40,"type":"directory"}
        ]"#;
        let files: Vec<CatalogFile> =
            serde_json::from_str(&normalize_files_json(raw, true).unwrap()).unwrap();
        assert_eq!(files.len(), 2);
        assert_eq!(files[0].path, "bundles/x.vfts");
        assert_eq!(files[1].size, 20);
    }
}
