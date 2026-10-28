//! Manifest model để kiểm provenance/hash trước khi nạp.

use std::path::Path;

use serde::{Deserialize, Serialize};

use vifasttts_ports::ModelInfo;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ManifestFile {
    pub file: String,
    pub sha256: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct OrtManifestRef {
    pub tested: String,
    pub mode: String,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ModelManifest {
    pub format: String,
    pub arch: String,
    pub sample_rate: u32,
    pub n_mels: usize,
    pub n_fft: usize,
    pub hop_length: usize,
    pub vocab_version: String,
    pub vocab_hash: String,
    pub acoustic: ManifestFile,
    pub vocoder: ManifestFile,
    pub ort: OrtManifestRef,
    pub license: String,
}

impl ModelManifest {
    pub fn from_path(path: impl AsRef<Path>) -> Result<Self, String> {
        let text = std::fs::read_to_string(path.as_ref())
            .map_err(|err| format!("đọc manifest {}: {err}", path.as_ref().display()))?;
        serde_json::from_str(&text)
            .map_err(|err| format!("parse manifest {}: {err}", path.as_ref().display()))
    }

    pub fn verify(&self, info: &ModelInfo) -> Result<(), String> {
        if self.arch != info.arch {
            return Err(format!(
                "manifest arch {} != model {}",
                self.arch, info.arch
            ));
        }
        if self.vocab_hash != info.vocab_hash {
            return Err("manifest vocab_hash != model".to_string());
        }
        if self.sample_rate != info.sample_rate
            || self.n_mels != info.n_mels
            || self.n_fft != info.n_fft
            || self.hop_length != info.hop_length
        {
            return Err("manifest audio contract != model metadata".to_string());
        }
        if self.acoustic.sha256 != info.acoustic_sha256 {
            return Err("manifest acoustic sha256 != file".to_string());
        }
        if self.vocoder.sha256 != info.vocoder_sha256 {
            return Err("manifest vocoder sha256 != file".to_string());
        }
        Ok(())
    }
}
