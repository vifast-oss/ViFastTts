//! Native adapter: async `vifasttts-engine` + ORT backend, API sync tiện dụng.
//!
//! `vifasttts-browser` là adapter ngang hàng cho browser: cùng engine, backend
//! ORT Web, API async. Native backend trả future sẵn sàng ngay nên `block_on`
//! chỉ là cầu nối, không thêm thread hay runtime async.

use std::future::Future;
use std::sync::Arc;
use std::task::{Context, Poll, Wake, Waker};

pub use vifasttts_engine::{
    AcousticModel, AcousticResult, ComplexSpectrogram, KaraokeDocument, KaraokeLine,
    MelSpectrogram, ModelInfo, StreamControl, StreamSummary,
    SynthesisEngine as AsyncSynthesisEngine, SynthesisOptions, SynthesisResult, TimedUnit,
    UnitKind, VocoderModel,
};
pub use vifasttts_ort::{
    ManifestFile, ModelManifest, OrtAcousticModel, OrtManifestRef, OrtModelBundle,
    OrtModelMetadata, OrtVocoderModel, from_bytes as ort_from_bytes, load_paths,
    load_paths_with_manifest, ort_info,
};
pub use vifasttts_vfts::{
    PackOptions, VfaBundle, VfaManifest, VfaOptions, VftsBundle, VftsManifest, VocoderRef,
};

struct ThreadWaker(std::thread::Thread);

impl Wake for ThreadWaker {
    fn wake(self: Arc<Self>) {
        self.0.unpark();
    }

    fn wake_by_ref(self: &Arc<Self>) {
        self.0.unpark();
    }
}

/// Chạy future trên thread hiện tại. ORT native luôn hoàn tất ngay; vẫn xử lý
/// đúng trường hợp future `Pending` (backend async khác) bằng park/unpark.
fn block_on<F: Future>(future: F) -> F::Output {
    let waker = Waker::from(Arc::new(ThreadWaker(std::thread::current())));
    let mut context = Context::from_waker(&waker);
    let mut future = std::pin::pin!(future);
    loop {
        match future.as_mut().poll(&mut context) {
            Poll::Ready(value) => return value,
            Poll::Pending => std::thread::park(),
        }
    }
}

/// NativeEngine native: bọc async engine + ORT, expose API sync cho CLI/server/FFI.
pub struct NativeEngine {
    inner: AsyncSynthesisEngine<OrtAcousticModel, OrtVocoderModel>,
}

impl NativeEngine {
    pub fn new(acoustic: OrtAcousticModel, vocoder: OrtVocoderModel, info: ModelInfo) -> Self {
        Self {
            inner: AsyncSynthesisEngine::new(acoustic, vocoder, info),
        }
    }

    pub fn info(&self) -> &ModelInfo {
        &self.inner.info
    }

    pub fn acoustic(&self) -> &OrtAcousticModel {
        &self.inner.acoustic
    }

    pub fn vocoder(&self) -> &OrtVocoderModel {
        &self.inner.vocoder
    }

    pub fn acoustic_mut(&mut self) -> &mut OrtAcousticModel {
        &mut self.inner.acoustic
    }

    pub fn vocoder_mut(&mut self) -> &mut OrtVocoderModel {
        &mut self.inner.vocoder
    }

    pub fn as_async(&self) -> &AsyncSynthesisEngine<OrtAcousticModel, OrtVocoderModel> {
        &self.inner
    }

    pub fn as_async_mut(&mut self) -> &mut AsyncSynthesisEngine<OrtAcousticModel, OrtVocoderModel> {
        &mut self.inner
    }

    pub fn synthesize(
        &mut self,
        text: &str,
        options: &SynthesisOptions,
    ) -> Result<SynthesisResult, String> {
        block_on(self.inner.synthesize(text, options))
    }

    pub fn acoustic_mel(
        &mut self,
        features: &[[i64; 7]],
        speed: f32,
        gate: f32,
    ) -> Result<MelSpectrogram, String> {
        block_on(self.inner.acoustic_mel(features, speed, gate))
    }

    pub fn synthesize_ids(
        &mut self,
        features: &[[i64; 7]],
        speed: f32,
        gate: f32,
        alpha: f32,
        peak_normalize: bool,
    ) -> Result<SynthesisResult, String> {
        block_on(
            self.inner
                .synthesize_ids(features, speed, gate, alpha, peak_normalize),
        )
    }

    pub fn synthesize_stream<F>(
        &mut self,
        text: &str,
        options: &SynthesisOptions,
        emit: F,
    ) -> Result<StreamSummary, String>
    where
        F: FnMut(&[f32], u32) -> StreamControl,
    {
        block_on(self.inner.synthesize_stream(text, options, emit))
    }

    pub fn synthesize_stream_with_units<F, U>(
        &mut self,
        text: &str,
        options: &SynthesisOptions,
        emit: F,
        units_emit: U,
    ) -> Result<StreamSummary, String>
    where
        F: FnMut(&[f32], u32) -> StreamControl,
        U: FnMut(&[TimedUnit]),
    {
        block_on(
            self.inner
                .synthesize_stream_with_units(text, options, emit, units_emit),
        )
    }
}

/// Nạp model từ path (API tiện dụng cho CLI/desktop/server).
pub fn load(
    acoustic: impl AsRef<std::path::Path>,
    vocoder: impl AsRef<std::path::Path>,
) -> Result<NativeEngine, String> {
    let components = load_paths(acoustic, vocoder)?;
    Ok(NativeEngine::new(
        components.acoustic,
        components.vocoder,
        components.info,
    ))
}

/// Nạp model từ bundle `.vfts` (manifest + ONNX + snapshot frontend).
pub fn load_vfts(path: impl AsRef<std::path::Path>) -> Result<NativeEngine, String> {
    let bundle = VftsBundle::read_path(path)?;
    bundle.verify_runtime_vocab()?;
    from_bytes(&bundle.acoustic, &bundle.vocoder)
}

/// Nạp acoustic-only `.vfa` với vocoder dùng chung.
pub fn load_vfa(
    vfa: impl AsRef<std::path::Path>,
    vocoder: impl AsRef<std::path::Path>,
) -> Result<NativeEngine, String> {
    let bundle = VfaBundle::read_path(vfa)?;
    bundle.verify_runtime_vocab()?;
    let vocoder = std::fs::read(vocoder.as_ref())
        .map_err(|error| format!("đọc {}: {error}", vocoder.as_ref().display()))?;
    bundle.verify_vocoder(&vocoder)?;
    from_bytes(&bundle.acoustic, &vocoder)
}

/// Nạp model từ bytes (iOS/Android/browser bundle không có path).
pub fn from_bytes(acoustic: &[u8], vocoder: &[u8]) -> Result<NativeEngine, String> {
    let components = ort_from_bytes(acoustic, vocoder)?;
    Ok(NativeEngine::new(
        components.acoustic,
        components.vocoder,
        components.info,
    ))
}

/// Nạp model + kiểm manifest (arch/hash/audio contract).
pub fn load_verified(
    acoustic: impl AsRef<std::path::Path>,
    vocoder: impl AsRef<std::path::Path>,
    manifest: impl AsRef<std::path::Path>,
) -> Result<NativeEngine, String> {
    let components = load_paths_with_manifest(acoustic, vocoder, manifest)?;
    Ok(NativeEngine::new(
        components.acoustic,
        components.vocoder,
        components.info,
    ))
}
