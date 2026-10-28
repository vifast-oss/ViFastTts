//! `.vfts` — bundle model optional: manifest + acoustic/vocoder ONNX + frontend resources.
//!
//! Đây **không phải** định dạng model mới thay ONNX. Loader hiện tại vẫn dùng
//! `from_bytes`; `.vfts` chỉ đóng gói/kiểm provenance và resource để phân phối.
//! Frontend resources là snapshot để audit/reproducibility; runtime hiện vẫn
//! dùng resource nhúng trong `vifasttts-text` (xem `verify_runtime_vocab`).

use std::collections::BTreeMap;
use std::io::{Cursor, Read, Write};
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use zip::write::SimpleFileOptions;
use zip::{CompressionMethod, ZipArchive, ZipWriter};

use vifasttts_model_source::{ModelBytes, ModelSource};

pub const FORMAT: &str = "vifasttts-model-v1";
pub const MANIFEST_NAME: &str = "manifest.json";
pub const ACOUSTIC_NAME: &str = "acoustic.onnx";
pub const VOCODER_NAME: &str = "vocoder.onnx";
pub const MAX_UNCOMPRESSED: u64 = 512 * 1024 * 1024;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct BundleFile {
    pub file: String,
    pub sha256: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct OrtRef {
    pub tested: String,
    pub mode: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct VftsManifest {
    pub format: String,
    pub arch: String,
    pub sample_rate: u32,
    pub n_mels: usize,
    pub n_fft: usize,
    pub hop_length: usize,
    pub vocab_version: String,
    pub vocab_hash: String,
    pub acoustic: BundleFile,
    pub vocoder: BundleFile,
    pub ort: OrtRef,
    pub license: String,
    /// Snapshot frontend: tên logic (ví dụ `vocab.json`) → entry trong bundle.
    #[serde(default)]
    pub frontend: BTreeMap<String, BundleFile>,
}

#[derive(Clone, Debug)]
pub struct VftsBundle {
    pub manifest: VftsManifest,
    pub acoustic: Vec<u8>,
    pub vocoder: Vec<u8>,
    /// `vocab.json`, `overrides_vi.json`, ... (bytes).
    pub frontend: BTreeMap<String, Vec<u8>>,
}

#[derive(Clone, Debug)]
pub struct PackOptions {
    pub arch: String,
    pub sample_rate: u32,
    pub n_mels: usize,
    pub n_fft: usize,
    pub hop_length: usize,
    pub vocab_version: String,
    pub vocab_hash: String,
    pub ort_tested: String,
    pub license: String,
}

impl Default for PackOptions {
    fn default() -> Self {
        Self {
            arch: "v2_slot5".to_string(),
            sample_rate: 24_000,
            n_mels: 100,
            n_fft: 1024,
            hop_length: 256,
            vocab_version: vifasttts_text::vocab::vocab_version(),
            vocab_hash: vifasttts_text::vocab::vocab_hash(),
            ort_tested: "1.31.1".to_string(),
            license: "research/non-commercial; dataset CC-BY-NC-4.0".to_string(),
        }
    }
}

fn sha256_bytes(bytes: &[u8]) -> String {
    hex::encode(Sha256::digest(bytes))
}

fn read_file(path: &Path) -> Result<Vec<u8>, String> {
    std::fs::read(path).map_err(|error| format!("đọc {}: {error}", path.display()))
}

fn safe_entry_name(name: &str) -> bool {
    if name.is_empty() || name.starts_with('/') || name.contains('\\') {
        return false;
    }
    !name.split('/').any(|part| part == ".." || part.is_empty())
}

fn add_entry(zip: &mut ZipWriter<Cursor<Vec<u8>>>, name: &str, bytes: &[u8]) -> Result<(), String> {
    let options = SimpleFileOptions::default().compression_method(CompressionMethod::Deflated);
    zip.start_file(name, options)
        .map_err(|error| format!("tạo entry {name}: {error}"))?;
    zip.write_all(bytes)
        .map_err(|error| format!("ghi entry {name}: {error}"))
}

impl VftsBundle {
    /// Đóng gói ONNX + snapshot resources. `frontend_dir` có thể `None`.
    pub fn from_paths(
        acoustic: impl AsRef<Path>,
        vocoder: impl AsRef<Path>,
        frontend_dir: Option<&Path>,
        options: PackOptions,
    ) -> Result<Self, String> {
        let acoustic = read_file(acoustic.as_ref())?;
        let vocoder = read_file(vocoder.as_ref())?;
        let mut frontend = BTreeMap::new();
        if let Some(dir) = frontend_dir {
            if !dir.is_dir() {
                return Err(format!("frontend dir không tồn tại: {}", dir.display()));
            }
            let mut paths: Vec<PathBuf> = std::fs::read_dir(dir)
                .map_err(|error| format!("đọc {}: {error}", dir.display()))?
                .filter_map(Result::ok)
                .map(|entry| entry.path())
                .filter(|path| path.extension().is_some_and(|ext| ext == "json"))
                .collect();
            paths.sort();
            for path in paths {
                let name = path
                    .file_name()
                    .and_then(|name| name.to_str())
                    .ok_or_else(|| format!("tên frontend không UTF-8: {}", path.display()))?;
                frontend.insert(name.to_string(), read_file(&path)?);
            }
        }
        let mut manifest = VftsManifest {
            format: FORMAT.to_string(),
            arch: options.arch,
            sample_rate: options.sample_rate,
            n_mels: options.n_mels,
            n_fft: options.n_fft,
            hop_length: options.hop_length,
            vocab_version: options.vocab_version,
            vocab_hash: options.vocab_hash,
            acoustic: BundleFile {
                file: ACOUSTIC_NAME.to_string(),
                sha256: sha256_bytes(&acoustic),
            },
            vocoder: BundleFile {
                file: VOCODER_NAME.to_string(),
                sha256: sha256_bytes(&vocoder),
            },
            ort: OrtRef {
                tested: options.ort_tested,
                mode: "load-dynamic".to_string(),
            },
            license: options.license,
            frontend: BTreeMap::new(),
        };
        for (name, bytes) in &frontend {
            manifest.frontend.insert(
                name.clone(),
                BundleFile {
                    file: format!("frontend/{name}"),
                    sha256: sha256_bytes(bytes),
                },
            );
        }
        Ok(Self {
            manifest,
            acoustic,
            vocoder,
            frontend,
        })
    }

    pub fn to_bytes(&self) -> Result<Vec<u8>, String> {
        self.validate()?;
        let cursor = Cursor::new(Vec::new());
        let mut zip = ZipWriter::new(cursor);
        let manifest = serde_json::to_vec_pretty(&self.manifest)
            .map_err(|error| format!("serialize manifest: {error}"))?;
        add_entry(&mut zip, MANIFEST_NAME, &manifest)?;
        add_entry(&mut zip, ACOUSTIC_NAME, &self.acoustic)?;
        add_entry(&mut zip, VOCODER_NAME, &self.vocoder)?;
        for (name, bytes) in &self.frontend {
            let entry = &self.manifest.frontend[name];
            add_entry(&mut zip, &entry.file, bytes)?;
        }
        let cursor = zip
            .finish()
            .map_err(|error| format!("finish zip: {error}"))?;
        Ok(cursor.into_inner())
    }

    pub fn write_path(&self, path: impl AsRef<Path>) -> Result<(), String> {
        let bytes = self.to_bytes()?;
        std::fs::write(path.as_ref(), bytes)
            .map_err(|error| format!("ghi {}: {error}", path.as_ref().display()))
    }

    pub fn read_path(path: impl AsRef<Path>) -> Result<Self, String> {
        let bytes = read_file(path.as_ref())?;
        Self::read_bytes(&bytes)
    }

    pub fn read_bytes(bytes: &[u8]) -> Result<Self, String> {
        let cursor = Cursor::new(bytes);
        let mut archive = ZipArchive::new(cursor)
            .map_err(|error| format!("không phải ZIP/.vfts hợp lệ: {error}"))?;
        let mut total = 0u64;
        let mut entries = BTreeMap::<String, Vec<u8>>::new();
        for index in 0..archive.len() {
            let mut file = archive
                .by_index(index)
                .map_err(|error| format!("đọc ZIP entry {index}: {error}"))?;
            let name = file
                .name()
                .map_err(|error| format!("tên ZIP entry {index}: {error}"))?
                .to_string();
            if !safe_entry_name(&name) {
                return Err(format!("entry .vfts không an toàn: {name}"));
            }
            if file.is_dir() {
                continue;
            }
            total = total.saturating_add(file.size());
            if total > MAX_UNCOMPRESSED {
                return Err(format!(
                    ".vfts giải nén vượt giới hạn {} MB",
                    MAX_UNCOMPRESSED / 1024 / 1024
                ));
            }
            let mut data = Vec::with_capacity(file.size() as usize);
            file.read_to_end(&mut data)
                .map_err(|error| format!("đọc {name}: {error}"))?;
            entries.insert(name, data);
        }
        let manifest_bytes = entries
            .remove(MANIFEST_NAME)
            .ok_or_else(|| "thiếu manifest.json".to_string())?;
        let manifest: VftsManifest = serde_json::from_slice(&manifest_bytes)
            .map_err(|error| format!("parse manifest.json: {error}"))?;
        if manifest.format != FORMAT {
            return Err(format!(
                "format {} không hỗ trợ (cần {FORMAT})",
                manifest.format
            ));
        }
        let acoustic = entries
            .remove(&manifest.acoustic.file)
            .or_else(|| entries.remove(ACOUSTIC_NAME))
            .ok_or_else(|| format!("thiếu acoustic: {}", manifest.acoustic.file))?;
        let vocoder = entries
            .remove(&manifest.vocoder.file)
            .or_else(|| entries.remove(VOCODER_NAME))
            .ok_or_else(|| format!("thiếu vocoder: {}", manifest.vocoder.file))?;
        check_hash("acoustic", &acoustic, &manifest.acoustic.sha256)?;
        check_hash("vocoder", &vocoder, &manifest.vocoder.sha256)?;
        let mut frontend = BTreeMap::new();
        for (name, file) in &manifest.frontend {
            let data = entries
                .remove(&file.file)
                .ok_or_else(|| format!("thiếu frontend {name}: {}", file.file))?;
            check_hash(name, &data, &file.sha256)?;
            frontend.insert(name.clone(), data);
        }
        let bundle = Self {
            manifest,
            acoustic,
            vocoder,
            frontend,
        };
        bundle.validate()?;
        Ok(bundle)
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.manifest.format != FORMAT {
            return Err(format!("format không hỗ trợ: {}", self.manifest.format));
        }
        check_hash("acoustic", &self.acoustic, &self.manifest.acoustic.sha256)?;
        check_hash("vocoder", &self.vocoder, &self.manifest.vocoder.sha256)?;
        for (name, bytes) in &self.frontend {
            let entry = self
                .manifest
                .frontend
                .get(name)
                .ok_or_else(|| format!("frontend {name} thiếu manifest entry"))?;
            check_hash(name, bytes, &entry.sha256)?;
        }
        Ok(())
    }

    /// Bundle frontend phải khớp vocab runtime; nếu bundle không có frontend thì bỏ qua.
    pub fn verify_runtime_vocab(&self) -> Result<(), String> {
        let Some(vocab) = self.frontend.get("vocab.json") else {
            return Ok(());
        };
        let value: serde_json::Value = serde_json::from_slice(vocab)
            .map_err(|error| format!("frontend/vocab.json: {error}"))?;
        let version = value.get("version").and_then(|v| v.as_str()).unwrap_or("");
        let hash = value.get("hash").and_then(|v| v.as_str()).unwrap_or("");
        if version != self.manifest.vocab_version || hash != self.manifest.vocab_hash {
            return Err("vocab frontend không khớp manifest".to_string());
        }
        let runtime_hash = vifasttts_text::vocab::vocab_hash();
        if hash != runtime_hash {
            return Err(format!(
                "vocab bundle {hash} != runtime {runtime_hash}; cần đúng frontend"
            ));
        }
        Ok(())
    }

    pub fn model_bytes(&self) -> ModelBytes {
        ModelBytes {
            acoustic: self.acoustic.clone(),
            vocoder: self.vocoder.clone(),
        }
    }

    /// Giải nén an toàn ra thư mục (không ghi đè path ngoài).
    pub fn unpack_to(&self, output: impl AsRef<Path>) -> Result<(), String> {
        let output = output.as_ref();
        std::fs::create_dir_all(output)
            .map_err(|error| format!("tạo {}: {error}", output.display()))?;
        std::fs::write(
            output.join(MANIFEST_NAME),
            serde_json::to_vec_pretty(&self.manifest)
                .map_err(|error| format!("serialize manifest: {error}"))?,
        )
        .map_err(|error| format!("ghi manifest: {error}"))?;
        std::fs::write(output.join(ACOUSTIC_NAME), &self.acoustic)
            .map_err(|error| format!("ghi acoustic: {error}"))?;
        std::fs::write(output.join(VOCODER_NAME), &self.vocoder)
            .map_err(|error| format!("ghi vocoder: {error}"))?;
        for (name, bytes) in &self.frontend {
            let dir = output.join("frontend");
            std::fs::create_dir_all(&dir).map_err(|error| format!("tạo frontend: {error}"))?;
            std::fs::write(dir.join(name), bytes)
                .map_err(|error| format!("ghi frontend {name}: {error}"))?;
        }
        Ok(())
    }
}

fn check_hash(name: &str, bytes: &[u8], expected: &str) -> Result<(), String> {
    let actual = sha256_bytes(bytes);
    if actual != expected {
        return Err(format!("{name}: sha256 {actual} != manifest {expected}"));
    }
    Ok(())
}

impl ModelSource for VftsBundle {
    fn load(&self) -> Result<ModelBytes, String> {
        Ok(self.model_bytes())
    }
}

// ---------------------------------------------------------------------------
// `.vfa` — acoustic-only voice pack, dùng chung vocoder theo SHA256
// ---------------------------------------------------------------------------

pub const VFA_FORMAT: &str = "vifasttts-acoustic-v1";

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct VocoderRef {
    pub id: String,
    pub sha256: String,
    pub sample_rate: u32,
    pub n_mels: usize,
    pub n_fft: usize,
    pub hop_length: usize,
    #[serde(default)]
    pub mel_hash: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct VfaManifest {
    pub format: String,
    pub arch: String,
    pub sample_rate: u32,
    pub n_mels: usize,
    pub n_fft: usize,
    pub hop_length: usize,
    pub vocab_version: String,
    pub vocab_hash: String,
    pub acoustic: BundleFile,
    pub vocoder: VocoderRef,
    pub license: String,
    #[serde(default)]
    pub frontend: BTreeMap<String, BundleFile>,
}

#[derive(Clone, Debug)]
pub struct VfaBundle {
    pub manifest: VfaManifest,
    pub acoustic: Vec<u8>,
    pub frontend: BTreeMap<String, Vec<u8>>,
}

#[derive(Clone, Debug)]
pub struct VfaOptions {
    pub arch: String,
    pub sample_rate: u32,
    pub n_mels: usize,
    pub n_fft: usize,
    pub hop_length: usize,
    pub vocab_version: String,
    pub vocab_hash: String,
    pub license: String,
    pub vocoder: VocoderRef,
}

impl Default for VfaOptions {
    fn default() -> Self {
        Self {
            arch: "v2_slot5".to_string(),
            sample_rate: 24_000,
            n_mels: 100,
            n_fft: 1024,
            hop_length: 256,
            vocab_version: vifasttts_text::vocab::vocab_version(),
            vocab_hash: vifasttts_text::vocab::vocab_hash(),
            license: "research/non-commercial; dataset CC-BY-NC-4.0".to_string(),
            vocoder: VocoderRef {
                id: "vocos-mel-24khz".to_string(),
                sha256: "b3eb09cf5c3baac334b1c0bbea070d02e33e55572e3755865b986cd05cf6b03f"
                    .to_string(),
                sample_rate: 24_000,
                n_mels: 100,
                n_fft: 1024,
                hop_length: 256,
                mel_hash: None,
            },
        }
    }
}

fn read_frontend(dir: Option<&Path>) -> Result<BTreeMap<String, Vec<u8>>, String> {
    let mut frontend = BTreeMap::new();
    let Some(dir) = dir else {
        return Ok(frontend);
    };
    if !dir.is_dir() {
        return Err(format!("frontend dir không tồn tại: {}", dir.display()));
    }
    let mut paths: Vec<PathBuf> = std::fs::read_dir(dir)
        .map_err(|error| format!("đọc {}: {error}", dir.display()))?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| path.extension().is_some_and(|ext| ext == "json"))
        .collect();
    paths.sort();
    for path in paths {
        let name = path
            .file_name()
            .and_then(|name| name.to_str())
            .ok_or_else(|| format!("tên frontend không UTF-8: {}", path.display()))?;
        frontend.insert(name.to_string(), read_file(&path)?);
    }
    Ok(frontend)
}

impl VfaBundle {
    pub fn from_paths(
        acoustic: impl AsRef<Path>,
        vocoder: impl AsRef<Path>,
        frontend_dir: Option<&Path>,
        mut options: VfaOptions,
    ) -> Result<Self, String> {
        let acoustic = read_file(acoustic.as_ref())?;
        let vocoder_bytes = read_file(vocoder.as_ref())?;
        options.vocoder.sha256 = sha256_bytes(&vocoder_bytes);
        let frontend = read_frontend(frontend_dir)?;
        let mut manifest = VfaManifest {
            format: VFA_FORMAT.to_string(),
            arch: options.arch,
            sample_rate: options.sample_rate,
            n_mels: options.n_mels,
            n_fft: options.n_fft,
            hop_length: options.hop_length,
            vocab_version: options.vocab_version,
            vocab_hash: options.vocab_hash,
            acoustic: BundleFile {
                file: ACOUSTIC_NAME.to_string(),
                sha256: sha256_bytes(&acoustic),
            },
            vocoder: options.vocoder,
            license: options.license,
            frontend: BTreeMap::new(),
        };
        for (name, bytes) in &frontend {
            manifest.frontend.insert(
                name.clone(),
                BundleFile {
                    file: format!("frontend/{name}"),
                    sha256: sha256_bytes(bytes),
                },
            );
        }
        Ok(Self {
            manifest,
            acoustic,
            frontend,
        })
    }

    pub fn to_bytes(&self) -> Result<Vec<u8>, String> {
        self.validate()?;
        let cursor = Cursor::new(Vec::new());
        let mut zip = ZipWriter::new(cursor);
        let manifest = serde_json::to_vec_pretty(&self.manifest)
            .map_err(|error| format!("serialize VFA manifest: {error}"))?;
        add_entry(&mut zip, MANIFEST_NAME, &manifest)?;
        add_entry(&mut zip, ACOUSTIC_NAME, &self.acoustic)?;
        for (name, bytes) in &self.frontend {
            let entry = &self.manifest.frontend[name];
            add_entry(&mut zip, &entry.file, bytes)?;
        }
        Ok(zip
            .finish()
            .map_err(|error| format!("finish VFA zip: {error}"))?
            .into_inner())
    }

    pub fn write_path(&self, path: impl AsRef<Path>) -> Result<(), String> {
        let bytes = self.to_bytes()?;
        std::fs::write(path.as_ref(), bytes)
            .map_err(|error| format!("ghi {}: {error}", path.as_ref().display()))
    }

    pub fn read_path(path: impl AsRef<Path>) -> Result<Self, String> {
        Self::read_bytes(&read_file(path.as_ref())?)
    }

    pub fn read_bytes(bytes: &[u8]) -> Result<Self, String> {
        let mut archive = ZipArchive::new(Cursor::new(bytes))
            .map_err(|error| format!("không phải ZIP/.vfa hợp lệ: {error}"))?;
        let mut entries = BTreeMap::<String, Vec<u8>>::new();
        let mut total = 0u64;
        for index in 0..archive.len() {
            let mut file = archive
                .by_index(index)
                .map_err(|error| format!("đọc ZIP entry {index}: {error}"))?;
            let name = file
                .name()
                .map_err(|error| format!("tên ZIP entry {index}: {error}"))?
                .to_string();
            if !safe_entry_name(&name) {
                return Err(format!("entry .vfa không an toàn: {name}"));
            }
            if file.is_dir() {
                continue;
            }
            total = total.saturating_add(file.size());
            if total > MAX_UNCOMPRESSED {
                return Err(".vfa vượt giới hạn giải nén".to_string());
            }
            let mut data = Vec::with_capacity(file.size() as usize);
            file.read_to_end(&mut data)
                .map_err(|error| format!("đọc {name}: {error}"))?;
            entries.insert(name, data);
        }
        let manifest: VfaManifest = serde_json::from_slice(
            entries
                .remove(MANIFEST_NAME)
                .ok_or_else(|| "thiếu manifest.json".to_string())?
                .as_slice(),
        )
        .map_err(|error| format!("parse VFA manifest: {error}"))?;
        if manifest.format != VFA_FORMAT {
            return Err(format!("format {} không phải .vfa", manifest.format));
        }
        let acoustic = entries
            .remove(&manifest.acoustic.file)
            .or_else(|| entries.remove(ACOUSTIC_NAME))
            .ok_or_else(|| "thiếu acoustic.onnx".to_string())?;
        check_hash("acoustic", &acoustic, &manifest.acoustic.sha256)?;
        let mut frontend = BTreeMap::new();
        for (name, file) in &manifest.frontend {
            let data = entries
                .remove(&file.file)
                .ok_or_else(|| format!("thiếu frontend {name}"))?;
            check_hash(name, &data, &file.sha256)?;
            frontend.insert(name.clone(), data);
        }
        let bundle = Self {
            manifest,
            acoustic,
            frontend,
        };
        bundle.validate()?;
        Ok(bundle)
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.manifest.format != VFA_FORMAT {
            return Err(format!("format không hỗ trợ: {}", self.manifest.format));
        }
        check_hash("acoustic", &self.acoustic, &self.manifest.acoustic.sha256)?;
        for (name, bytes) in &self.frontend {
            let entry = self
                .manifest
                .frontend
                .get(name)
                .ok_or_else(|| format!("frontend {name} thiếu manifest entry"))?;
            check_hash(name, bytes, &entry.sha256)?;
        }
        Ok(())
    }

    pub fn verify_vocoder(&self, vocoder: &[u8]) -> Result<(), String> {
        check_hash("vocoder", vocoder, &self.manifest.vocoder.sha256)?;
        Ok(())
    }

    pub fn verify_runtime_vocab(&self) -> Result<(), String> {
        let Some(vocab) = self.frontend.get("vocab.json") else {
            return Ok(());
        };
        let value: serde_json::Value = serde_json::from_slice(vocab)
            .map_err(|error| format!("frontend/vocab.json: {error}"))?;
        let version = value.get("version").and_then(|v| v.as_str()).unwrap_or("");
        let hash = value.get("hash").and_then(|v| v.as_str()).unwrap_or("");
        if version != self.manifest.vocab_version || hash != self.manifest.vocab_hash {
            return Err("vocab frontend không khớp manifest".to_string());
        }
        let runtime_hash = vifasttts_text::vocab::vocab_hash();
        if hash != runtime_hash {
            return Err(format!(
                "vocab bundle {hash} != runtime {runtime_hash}; cần đúng frontend"
            ));
        }
        Ok(())
    }

    pub fn unpack_to(&self, output: impl AsRef<Path>) -> Result<(), String> {
        let output = output.as_ref();
        std::fs::create_dir_all(output)
            .map_err(|error| format!("tạo {}: {error}", output.display()))?;
        std::fs::write(
            output.join(MANIFEST_NAME),
            serde_json::to_vec_pretty(&self.manifest)
                .map_err(|error| format!("serialize manifest: {error}"))?,
        )
        .map_err(|error| format!("ghi manifest: {error}"))?;
        std::fs::write(output.join(ACOUSTIC_NAME), &self.acoustic)
            .map_err(|error| format!("ghi acoustic: {error}"))?;
        for (name, bytes) in &self.frontend {
            let dir = output.join("frontend");
            std::fs::create_dir_all(&dir).map_err(|error| format!("tạo frontend: {error}"))?;
            std::fs::write(dir.join(name), bytes)
                .map_err(|error| format!("ghi frontend {name}: {error}"))?;
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn bundle() -> VftsBundle {
        let acoustic = b"fake-acoustic".to_vec();
        let vocoder = b"fake-vocoder".to_vec();
        let mut frontend = BTreeMap::new();
        frontend.insert(
            "vocab.json".to_string(),
            br#"{"version":"v-test","hash":"h-test"}"#.to_vec(),
        );
        let mut manifest = VftsManifest {
            format: FORMAT.to_string(),
            arch: "v2_slot5".to_string(),
            sample_rate: 24_000,
            n_mels: 100,
            n_fft: 1024,
            hop_length: 256,
            vocab_version: "v-test".to_string(),
            vocab_hash: "h-test".to_string(),
            acoustic: BundleFile {
                file: ACOUSTIC_NAME.to_string(),
                sha256: sha256_bytes(&acoustic),
            },
            vocoder: BundleFile {
                file: VOCODER_NAME.to_string(),
                sha256: sha256_bytes(&vocoder),
            },
            ort: OrtRef {
                tested: "1.31.1".to_string(),
                mode: "load-dynamic".to_string(),
            },
            license: "test".to_string(),
            frontend: BTreeMap::new(),
        };
        for (name, bytes) in &frontend {
            manifest.frontend.insert(
                name.clone(),
                BundleFile {
                    file: format!("frontend/{name}"),
                    sha256: sha256_bytes(bytes),
                },
            );
        }
        VftsBundle {
            manifest,
            acoustic,
            vocoder,
            frontend,
        }
    }

    #[test]
    fn roundtrip_and_hash_check() {
        let bundle = bundle();
        let bytes = bundle.to_bytes().unwrap();
        let loaded = VftsBundle::read_bytes(&bytes).unwrap();
        assert_eq!(loaded.acoustic, b"fake-acoustic");
        assert_eq!(loaded.frontend["vocab.json"], bundle.frontend["vocab.json"]);
        let mut tampered = loaded;
        tampered.acoustic[0] ^= 1;
        assert!(tampered.validate().is_err());
    }

    #[test]
    fn rejects_path_traversal() {
        let cursor = Cursor::new(Vec::new());
        let mut zip = ZipWriter::new(cursor);
        add_entry(&mut zip, "../evil", b"x").unwrap();
        let bytes = zip.finish().unwrap().into_inner();
        assert!(VftsBundle::read_bytes(&bytes).is_err());
    }

    #[test]
    fn frontend_roundtrip() {
        let bundle = bundle();
        let bytes = bundle.to_bytes().unwrap();
        let loaded = VftsBundle::read_bytes(&bytes).unwrap();
        assert_eq!(loaded.manifest.frontend.len(), 1);
        assert!(loaded.verify_runtime_vocab().is_err());
    }
}
