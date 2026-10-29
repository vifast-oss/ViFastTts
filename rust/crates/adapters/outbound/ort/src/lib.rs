//! ONNX Runtime backend: session, metadata/hash, tensor I/O.

use std::collections::BTreeMap;
use std::fs::File;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use ort::environment::Environment;
use ort::ep::CPU;
use ort::inputs;
use ort::session::Session;
use ort::session::builder::{AutoDevicePolicy, GraphOptimizationLevel, SessionBuilder};
use ort::value::TensorRef;
use sha2::{Digest, Sha256};

use vifasttts_ports::{
    AcousticModel, AcousticResult, ComplexSpectrogram, MelSpectrogram, ModelInfo, VocoderModel,
};
use vifasttts_text::vocab;

pub mod manifest;
pub use manifest::{ManifestFile, ModelManifest, OrtManifestRef};

#[derive(Clone, Debug, Default)]
pub struct OrtModelMetadata {
    pub arch: Option<String>,
    pub sample_rate: Option<u32>,
    pub n_mels: Option<usize>,
    pub n_fft: Option<usize>,
    pub hop_length: Option<usize>,
    pub vocab_version: Option<String>,
    pub vocab_hash: Option<String>,
    pub mel_hash: Option<String>,
    pub custom: BTreeMap<String, String>,
}

impl OrtModelMetadata {
    fn from_session(session: &Session) -> Result<Self, String> {
        let meta = session
            .metadata()
            .map_err(|err| format!("đọc metadata ONNX: {err}"))?;
        let mut custom = BTreeMap::new();
        if let Ok(keys) = meta.custom_keys() {
            for key in keys {
                if let Some(value) = meta.custom(&key) {
                    custom.insert(key, value.to_string());
                }
            }
        }
        let get = |key: &str| custom.get(key).cloned();
        Ok(Self {
            arch: get("arch"),
            sample_rate: get("sample_rate").and_then(|v| v.parse().ok()),
            n_mels: get("n_mels").and_then(|v| v.parse().ok()),
            n_fft: get("n_fft").and_then(|v| v.parse().ok()),
            hop_length: get("hop_length").and_then(|v| v.parse().ok()),
            vocab_version: get("vocab_version"),
            vocab_hash: get("vocab_hash"),
            mel_hash: get("mel_hash"),
            custom,
        })
    }
}

pub struct OrtModelBundle {
    pub acoustic: OrtAcousticModel,
    pub vocoder: OrtVocoderModel,
    pub info: ModelInfo,
    pub acoustic_path: Option<PathBuf>,
    pub vocoder_path: Option<PathBuf>,
}

pub struct OrtAcousticModel {
    session: Session,
    info: ModelInfo,
    pub input_names: Vec<String>,
    pub output_names: Vec<String>,
    _env: Environment,
}

pub struct OrtVocoderModel {
    session: Session,
    info: ModelInfo,
    pub input_names: Vec<String>,
    pub output_names: Vec<String>,
    _env: Environment,
}

fn sha256_file(path: &Path) -> Result<String, String> {
    let mut file = File::open(path).map_err(|err| format!("mở {}: {err}", path.display()))?;
    let mut digest = Sha256::new();
    let mut buffer = vec![0u8; 1024 * 1024];
    loop {
        let read = file
            .read(&mut buffer)
            .map_err(|err| format!("đọc {}: {err}", path.display()))?;
        if read == 0 {
            break;
        }
        digest.update(&buffer[..read]);
    }
    Ok(hex::encode(digest.finalize()))
}

fn sha256_bytes(bytes: &[u8]) -> String {
    hex::encode(Sha256::digest(bytes))
}

#[cfg(not(target_os = "ios"))]
fn ort_library_candidates() -> Vec<PathBuf> {
    let names = [
        "libonnxruntime.dylib",
        "libonnxruntime.so",
        "libonnxruntime.so.1",
        "onnxruntime.dll",
    ];
    let mut roots: Vec<PathBuf> = Vec::new();
    if let Ok(current) = std::env::current_dir() {
        roots.push(current.join("rust").join("lib"));
        roots.push(current.join("lib"));
    }
    roots.push(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../lib"));
    if let Ok(exe) = std::env::current_exe()
        && let Some(parent) = exe.parent()
    {
        roots.push(parent.to_path_buf());
        roots.push(parent.join("lib"));
    }
    let mut candidates = Vec::new();
    for root in roots {
        for name in names {
            candidates.push(root.join(name));
        }
    }
    candidates
}

/// ORT chỉ cho tạo một `Environment`/process. Giữ mạnh để session mới dùng lại;
/// nếu không, đổi model lần hai sẽ lỗi "only one environment is allowed".
static ENVIRONMENT: Mutex<Option<Environment>> = Mutex::new(None);

#[cfg(not(target_os = "ios"))]
fn build_environment() -> Result<Environment, String> {
    for key in ["VIFASTT_ORT_DYLIB", "ORT_DYLIB_PATH"] {
        if let Ok(value) = std::env::var(key) {
            let path = PathBuf::from(value);
            if path.is_file() {
                return ort::init_from(&path)
                    .map_err(|err| format!("nạp ORT từ {key}={}: {err}", path.display()))?
                    .with_name("vifasttts")
                    .build()
                    .map_err(|err| format!("khởi tạo ORT: {err}"));
            }
        }
    }
    for path in ort_library_candidates() {
        if path.is_file() {
            return ort::init_from(&path)
                .map_err(|err| format!("nạp ORT từ {}: {err}", path.display()))?
                .with_name("vifasttts")
                .build()
                .map_err(|err| format!("khởi tạo ORT: {err}"));
        }
    }
    Err(format!(
        "không tìm thấy ONNX Runtime 1.31.1; đặt VIFASTT_ORT_DYLIB hoặc chép \
         libonnxruntime vào rust/lib/ (đã tìm: {:?})",
        ort_library_candidates()
    ))
}

#[cfg(target_os = "ios")]
fn build_environment() -> Result<Environment, String> {
    // iOS không có DLL: ORT đã được link static qua onnxruntime.framework.
    ort::init()
        .with_name("vifasttts")
        .build()
        .map_err(|err| format!("khởi tạo ORT iOS: {err}"))
}

fn init_environment() -> Result<Environment, String> {
    let mut slot = ENVIRONMENT
        .lock()
        .map_err(|_| "khóa ORT environment bị poison".to_string())?;
    if let Some(environment) = slot.as_ref() {
        return Ok(environment.clone());
    }
    let environment = build_environment()?;
    *slot = Some(environment.clone());
    Ok(environment)
}

fn session_options(builder: SessionBuilder) -> Result<SessionBuilder, String> {
    builder
        .with_auto_device(AutoDevicePolicy::PreferCPU)
        .map_err(|err| format!("auto device: {err}"))?
        .with_execution_providers([CPU::default().build()])
        .map_err(|err| format!("CPU EP: {err}"))?
        .with_optimization_level(GraphOptimizationLevel::Level3)
        .map_err(|err| format!("optimization level: {err}"))?
        .with_intra_threads(2)
        .map_err(|err| format!("intra threads: {err}"))?
        .with_inter_threads(1)
        .map_err(|err| format!("inter threads: {err}"))
}

fn validate_metadata(
    acoustic: &OrtModelMetadata,
    vocoder: &OrtModelMetadata,
    acoustic_sha256: String,
    vocoder_sha256: String,
) -> Result<ModelInfo, String> {
    if acoustic.arch.as_deref() != Some("v2_slot5") {
        return Err(format!(
            "model acoustic arch={:?}, yêu cầu v2_slot5",
            acoustic.arch
        ));
    }
    let expected_vocab = vocab::vocab_hash();
    match acoustic.vocab_hash.as_deref() {
        Some(value) if value == expected_vocab => {}
        Some(value) => {
            return Err(format!(
                "vocab_hash ONNX không khớp: {value} vs {expected_vocab}"
            ));
        }
        None => return Err("model acoustic thiếu vocab_hash; từ chối ở production".to_string()),
    }
    let sample_rate = acoustic.sample_rate.unwrap_or(24_000);
    let vocoder_sample_rate = vocoder.sample_rate.unwrap_or(24_000);
    if sample_rate != vocoder_sample_rate {
        return Err(format!(
            "sample_rate acoustic/vocoder khác nhau: {sample_rate} vs {vocoder_sample_rate}"
        ));
    }
    let n_mels = acoustic.n_mels.unwrap_or(100);
    if n_mels != vocoder.n_mels.unwrap_or(100) {
        return Err("n_mels acoustic/vocoder khác nhau".to_string());
    }
    let n_fft = vocoder
        .n_fft
        .ok_or_else(|| "vocoder thiếu metadata n_fft".to_string())?;
    let hop_length = vocoder
        .hop_length
        .ok_or_else(|| "vocoder thiếu metadata hop_length".to_string())?;
    Ok(ModelInfo {
        arch: acoustic.arch.clone().unwrap_or_default(),
        vocab_version: acoustic.vocab_version.clone().unwrap_or_default(),
        vocab_hash: acoustic.vocab_hash.clone().unwrap_or_default(),
        sample_rate,
        n_mels,
        n_fft,
        hop_length,
        acoustic_sha256,
        vocoder_sha256,
        metadata: acoustic.custom.clone(),
        ort_build: ort::info().to_string(),
    })
}

fn make_acoustic(
    env: &Environment,
    session: Session,
    metadata: OrtModelMetadata,
    info: ModelInfo,
) -> Result<OrtAcousticModel, String> {
    let input_names = session
        .inputs()
        .iter()
        .map(|input| input.name().to_string())
        .collect::<Vec<_>>();
    let output_names = session
        .outputs()
        .iter()
        .map(|output| output.name().to_string())
        .collect::<Vec<_>>();
    if input_names.first().map(String::as_str) != Some("features") {
        return Err(format!(
            "input đầu tiên phải là features, nhận {input_names:?}"
        ));
    }
    if !output_names.iter().any(|name| name == "mel") {
        return Err("model acoustic thiếu output mel".to_string());
    }
    let _ = metadata;
    Ok(OrtAcousticModel {
        session,
        info,
        input_names,
        output_names,
        _env: env.clone(),
    })
}

fn make_vocoder(
    env: &Environment,
    session: Session,
    info: ModelInfo,
) -> Result<OrtVocoderModel, String> {
    let input_names = session
        .inputs()
        .iter()
        .map(|input| input.name().to_string())
        .collect::<Vec<_>>();
    let output_names = session
        .outputs()
        .iter()
        .map(|output| output.name().to_string())
        .collect::<Vec<_>>();
    if !output_names.iter().any(|name| name == "spec_real")
        || !output_names.iter().any(|name| name == "spec_imag")
    {
        return Err("vocoder thiếu spec_real/spec_imag".to_string());
    }
    Ok(OrtVocoderModel {
        session,
        info,
        input_names,
        output_names,
        _env: env.clone(),
    })
}

pub fn load_paths(
    acoustic: impl AsRef<Path>,
    vocoder: impl AsRef<Path>,
) -> Result<OrtModelBundle, String> {
    let acoustic_path = acoustic.as_ref().to_path_buf();
    let vocoder_path = vocoder.as_ref().to_path_buf();
    let env = init_environment()?;
    let acoustic_session =
        session_options(Session::builder(&env).map_err(|err| format!("builder acoustic: {err}"))?)?
            .commit_from_file(&acoustic_path)
            .map_err(|err| format!("nạp acoustic {}: {err}", acoustic_path.display()))?;
    let vocoder_session =
        session_options(Session::builder(&env).map_err(|err| format!("builder vocoder: {err}"))?)?
            .commit_from_file(&vocoder_path)
            .map_err(|err| format!("nạp vocoder {}: {err}", vocoder_path.display()))?;
    let acoustic_meta = OrtModelMetadata::from_session(&acoustic_session)?;
    let vocoder_meta = OrtModelMetadata::from_session(&vocoder_session)?;
    let acoustic_sha = sha256_file(&acoustic_path)?;
    let vocoder_sha = sha256_file(&vocoder_path)?;
    let info = validate_metadata(&acoustic_meta, &vocoder_meta, acoustic_sha, vocoder_sha)?;
    let acoustic = make_acoustic(&env, acoustic_session, acoustic_meta, info.clone())?;
    let vocoder = make_vocoder(&env, vocoder_session, info.clone())?;
    Ok(OrtModelBundle {
        acoustic,
        vocoder,
        info,
        acoustic_path: Some(acoustic_path),
        vocoder_path: Some(vocoder_path),
    })
}

pub fn load_paths_with_manifest(
    acoustic: impl AsRef<Path>,
    vocoder: impl AsRef<Path>,
    manifest: impl AsRef<Path>,
) -> Result<OrtModelBundle, String> {
    let components = load_paths(acoustic, vocoder)?;
    let manifest = ModelManifest::from_path(manifest)?;
    manifest.verify(&components.info)?;
    Ok(components)
}

pub fn from_bytes(acoustic_bytes: &[u8], vocoder_bytes: &[u8]) -> Result<OrtModelBundle, String> {
    let env = init_environment()?;
    let acoustic_session =
        session_options(Session::builder(&env).map_err(|err| format!("builder acoustic: {err}"))?)?
            .commit_from_memory(acoustic_bytes)
            .map_err(|err| format!("nạp acoustic từ bytes: {err}"))?;
    let vocoder_session =
        session_options(Session::builder(&env).map_err(|err| format!("builder vocoder: {err}"))?)?
            .commit_from_memory(vocoder_bytes)
            .map_err(|err| format!("nạp vocoder từ bytes: {err}"))?;
    let acoustic_meta = OrtModelMetadata::from_session(&acoustic_session)?;
    let vocoder_meta = OrtModelMetadata::from_session(&vocoder_session)?;
    let info = validate_metadata(
        &acoustic_meta,
        &vocoder_meta,
        sha256_bytes(acoustic_bytes),
        sha256_bytes(vocoder_bytes),
    )?;
    let acoustic = make_acoustic(&env, acoustic_session, acoustic_meta, info.clone())?;
    let vocoder = make_vocoder(&env, vocoder_session, info.clone())?;
    Ok(OrtModelBundle {
        acoustic,
        vocoder,
        info,
        acoustic_path: None,
        vocoder_path: None,
    })
}

impl AcousticModel for OrtAcousticModel {
    async fn run(
        &mut self,
        features: &[[i64; 7]],
        speed: f32,
        gate: f32,
    ) -> Result<AcousticResult, String> {
        let syllables = features.len();
        if syllables == 0 {
            return Err("không có âm tiết".to_string());
        }
        let flat: Vec<i64> = features
            .iter()
            .flat_map(|row| row.iter().copied())
            .collect();
        let input =
            TensorRef::from_array_view((vec![1i64, syllables as i64, 7i64], flat.as_slice()))
                .map_err(|err| format!("tạo tensor features: {err}"))?;
        let speed_values = [speed];
        let speed_tensor = TensorRef::from_array_view((vec![1i64], speed_values.as_slice()))
            .map_err(|err| format!("tạo tensor speed: {err}"))?;
        let gate_values = [gate];
        let gate_tensor = TensorRef::from_array_view((vec![1i64], gate_values.as_slice()))
            .map_err(|err| format!("tạo tensor gate: {err}"))?;
        let outputs = self
            .session
            .run(inputs![input, speed_tensor, gate_tensor])
            .map_err(|err| format!("chạy acoustic: {err}"))?;
        let (shape, data) = outputs
            .get("mel")
            .ok_or_else(|| "acoustic thiếu output mel".to_string())?
            .try_extract_tensor::<f32>()
            .map_err(|err| format!("đọc mel: {err}"))?;
        let dims: Vec<i64> = shape.iter().copied().collect();
        if dims.len() != 3 || dims[0] != 1 {
            return Err(format!("mel shape lạ: {dims:?}"));
        }
        let frames = dims[1] as usize;
        let mels = dims[2] as usize;
        if data.len() != frames * mels {
            return Err("mel data length không khớp shape".to_string());
        }
        let slot_durations = outputs
            .get("slot_durations")
            .map(|value| {
                value
                    .try_extract_tensor::<i64>()
                    .map(|(_, data)| data.to_vec())
                    .map_err(|err| format!("đọc slot_durations: {err}"))
            })
            .transpose()?;
        let durations = outputs
            .get("durations")
            .map(|value| {
                value
                    .try_extract_tensor::<i64>()
                    .map(|(_, data)| data.to_vec())
                    .map_err(|err| format!("đọc durations: {err}"))
            })
            .transpose()?;
        Ok(AcousticResult {
            mel: MelSpectrogram {
                data: data.to_vec(),
                frames,
                mels,
            },
            slot_durations,
            durations,
        })
    }

    fn info(&self) -> &ModelInfo {
        &self.info
    }
}

impl VocoderModel for OrtVocoderModel {
    async fn spectrogram(&mut self, mel: &MelSpectrogram) -> Result<ComplexSpectrogram, String> {
        let input = TensorRef::from_array_view((
            vec![1i64, mel.frames as i64, mel.mels as i64],
            mel.data.as_slice(),
        ))
        .map_err(|err| format!("tạo tensor mel: {err}"))?;
        let outputs = self
            .session
            .run(inputs![input])
            .map_err(|err| format!("chạy vocoder: {err}"))?;
        let (real_shape, real) = outputs
            .get("spec_real")
            .ok_or_else(|| "vocoder thiếu spec_real".to_string())?
            .try_extract_tensor::<f32>()
            .map_err(|err| format!("đọc spec_real: {err}"))?;
        let (imag_shape, imag) = outputs
            .get("spec_imag")
            .ok_or_else(|| "vocoder thiếu spec_imag".to_string())?
            .try_extract_tensor::<f32>()
            .map_err(|err| format!("đọc spec_imag: {err}"))?;
        let dims: Vec<i64> = real_shape.iter().copied().collect();
        let imag_dims: Vec<i64> = imag_shape.iter().copied().collect();
        if dims.len() != 3 || dims[0] != 1 || dims != imag_dims {
            return Err(format!("spec shape lạ: {dims:?} / {imag_dims:?}"));
        }
        Ok(ComplexSpectrogram {
            bins: dims[1] as usize,
            frames: dims[2] as usize,
            real: real.to_vec(),
            imag: imag.to_vec(),
        })
    }

    fn info(&self) -> &ModelInfo {
        &self.info
    }
}

pub fn ort_info() -> &'static str {
    ort::info()
}
