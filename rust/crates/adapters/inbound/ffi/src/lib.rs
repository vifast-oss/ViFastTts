//! C ABI tối thiểu cho mobile/desktop.
//!
//! Mọi lỗi được trả qua `vifasttts_last_error`; panic bị chặn ở biên FFI.
//! C ABI nhận raw pointer theo hợp đồng C; caller chịu trách nhiệm lifetime.
#![allow(clippy::not_unsafe_ptr_arg_deref)]

use std::cell::RefCell;
use std::ffi::{CStr, CString, c_char, c_void};
use std::panic::{AssertUnwindSafe, catch_unwind};
use std::ptr;
use std::slice;

use vifasttts_app::{
    api_contract_json, default_text, dictionary_json, eta_estimate_json, parse_dictionary,
    sample_texts, settings_defaults_json, settings_normalize_json,
};
use vifasttts_native::{
    NativeEngine, StreamControl, SynthesisOptions, from_bytes, load, load_vfa, load_vfa_auto,
    load_vfts, ort_info,
};
use vifasttts_text::dialect::Dialect;
use vifasttts_text::karaoke::KaraokeDocument;
use vifasttts_text::pipeline::live_parse_options;

thread_local! {
    static LAST_ERROR: RefCell<CString> = RefCell::new(CString::new("").unwrap());
}

fn set_error(message: impl Into<String>) {
    let text = message.into().replace('\0', " ");
    LAST_ERROR.with(|slot| {
        *slot.borrow_mut() = CString::new(text).unwrap_or_else(|_| CString::new("error").unwrap());
    });
}

/// Con trỏ lỗi gần nhất trên thread hiện tại; sống đến lần gọi kế tiếp.
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_last_error() -> *const c_char {
    LAST_ERROR.with(|slot| slot.borrow().as_ptr())
}

/// Phiên bản crate.
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_version() -> *const c_char {
    concat!(env!("CARGO_PKG_VERSION"), "\0").as_ptr().cast()
}

/// Build info ORT (chuỗi tĩnh).
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_ort_info() -> *const c_char {
    // `ort_info()` trả &'static str; cấp phát CString một lần và giữ static.
    static INFO: std::sync::OnceLock<CString> = std::sync::OnceLock::new();
    INFO.get_or_init(|| CString::new(ort_info()).unwrap_or_else(|_| CString::new("ORT").unwrap()))
        .as_ptr()
}

fn c_path(value: *const c_char) -> Result<std::path::PathBuf, String> {
    if value.is_null() {
        return Err("path null".to_string());
    }
    let text = unsafe { CStr::from_ptr(value) }
        .to_str()
        .map_err(|_| "path không phải UTF-8".to_string())?;
    Ok(std::path::PathBuf::from(text))
}

fn c_text(value: *const c_char) -> Result<String, String> {
    if value.is_null() {
        return Err("text null".to_string());
    }
    unsafe { CStr::from_ptr(value) }
        .to_str()
        .map(str::to_string)
        .map_err(|_| "text không phải UTF-8".to_string())
}

/// Chuỗi tuỳ chọn: NULL/chuỗi rỗng đều trả None.
fn c_text_optional(value: *const c_char) -> Result<Option<String>, String> {
    if value.is_null() {
        return Ok(None);
    }
    let text = unsafe { CStr::from_ptr(value) }
        .to_str()
        .map_err(|_| "chuỗi không phải UTF-8".to_string())?
        .to_string();
    Ok((!text.trim().is_empty()).then_some(text))
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct VifasttOptions {
    pub speed: f32,
    pub alpha: f32,
    pub max_chars: usize,
    pub fixed_pauses: bool,
    pub peak_normalize: bool,
}

impl Default for VifasttOptions {
    fn default() -> Self {
        Self {
            speed: 1.0,
            alpha: 1.5,
            max_chars: 300,
            fixed_pauses: false,
            peak_normalize: false,
        }
    }
}

fn synth_options(options: *const VifasttOptions) -> SynthesisOptions {
    let raw = if options.is_null() {
        VifasttOptions::default()
    } else {
        unsafe { *options }
    };
    let mut result = SynthesisOptions {
        speed: raw.speed.clamp(0.5, 2.0),
        alpha: raw.alpha,
        max_chars: raw.max_chars.max(1),
        fixed_pauses: raw.fixed_pauses,
        peak_normalize: raw.peak_normalize,
        ..SynthesisOptions::default()
    };
    if result.fixed_pauses {
        result.gate_threshold = 1.01;
    }
    result
}

/// Options + các trường mobile cần nhưng chưa có trong struct ABI cũ.
/// Tách hàm `_ex` để không phá client FFI đang dùng `VifasttOptions`.
fn synth_options_ex(
    options: *const VifasttOptions,
    dialect: *const c_char,
    resolve_oov: bool,
    dictionary: *const c_char,
) -> Result<SynthesisOptions, String> {
    let mut result = synth_options(options);
    let dialect_name = c_text_optional(dialect)?.unwrap_or_else(|| "north".to_string());
    let dialect = Dialect::from_name(&dialect_name)?;
    let dictionary_text = c_text_optional(dictionary)?;
    let mut merged = std::collections::HashMap::new();
    if let Some(text) = dictionary_text {
        merged.extend(parse_dictionary(&text).overrides());
    }
    let mut parse = live_parse_options(dialect, Some(&merged), None);
    parse.resolve_oov = resolve_oov;
    result.parse = parse;
    Ok(result)
}

fn guard<T>(default: T, f: impl FnOnce() -> Result<T, String>) -> T {
    match catch_unwind(AssertUnwindSafe(f)) {
        Ok(Ok(value)) => value,
        Ok(Err(error)) => {
            set_error(error);
            default
        }
        Err(_) => {
            set_error("panic trong FFI");
            default
        }
    }
}

/// Chuyển JSON String thành C string; caller giải phóng bằng `vifasttts_string_free`.
fn json_c_string(result: Result<String, String>) -> *mut c_char {
    guard(ptr::null_mut(), || {
        let value = result?;
        CString::new(value)
            .map(CString::into_raw)
            .map_err(|_| "JSON chứa NUL".to_string())
    })
}

/// Defaults/validate dùng chung cho mọi UI. Trả JSON UTF-8.
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_settings_defaults_json() -> *mut c_char {
    json_c_string(settings_defaults_json())
}

/// Chuẩn hoá settings JSON cũ/lạ; trả JSON đã normalize hoặc NULL + last_error.
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_settings_normalize_json(json: *const c_char) -> *mut c_char {
    json_c_string((|| {
        let raw = c_text(json)?;
        settings_normalize_json(&raw)
    })())
}

/// Sample text theo platform (`android`, `ios`, `desktop`, `tui`, `web`, ...).
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_sample_texts_json(platform: *const c_char) -> *mut c_char {
    json_c_string((|| {
        let platform = c_text_optional(platform)?.unwrap_or_default();
        let payload = serde_json::json!({
            "default": default_text(&platform),
            "samples": sample_texts(&platform),
        });
        serde_json::to_string(&payload).map_err(|error| format!("sample texts JSON: {error}"))
    })())
}

/// ETA dùng chung; history có thể chứa field UI riêng (serde bỏ qua field lạ).
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_eta_estimate_json(
    history_json: *const c_char,
    mode: *const c_char,
    chars: u32,
    max_samples: u32,
) -> *mut c_char {
    json_c_string((|| {
        let history = c_text_optional(history_json)?.unwrap_or_default();
        let mode = c_text(mode)?;
        eta_estimate_json(&history, &mode, chars, max_samples)
    })())
}

/// Parse từ điển dùng chung; trả `{rules,warnings,overrides}`.
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_dictionary_json(dictionary: *const c_char) -> *mut c_char {
    json_c_string((|| {
        let dictionary = c_text_optional(dictionary)?.unwrap_or_default();
        dictionary_json(&dictionary)
    })())
}

/// Hợp đồng endpoint/version để client không tự đoán path.
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_api_contract_json() -> *mut c_char {
    json_c_string(api_contract_json())
}

/// Nạp model từ path. Trả NULL nếu lỗi.
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_engine_new(
    acoustic: *const c_char,
    vocoder: *const c_char,
) -> *mut NativeEngine {
    guard(ptr::null_mut(), || {
        let acoustic = c_path(acoustic)?;
        let vocoder = c_path(vocoder)?;
        let engine = load(acoustic, vocoder)?;
        Ok(Box::into_raw(Box::new(engine)))
    })
}

/// Nạp model từ bundle `.vfts` (manifest + ONNX + snapshot frontend).
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_engine_new_vfts(path: *const c_char) -> *mut NativeEngine {
    guard(ptr::null_mut(), || {
        let path = c_path(path)?;
        let engine = load_vfts(path)?;
        Ok(Box::into_raw(Box::new(engine)))
    })
}

/// Nạp acoustic-only `.vfa` + vocoder dùng chung.
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_engine_new_vfa(
    vfa: *const c_char,
    vocoder: *const c_char,
) -> *mut NativeEngine {
    guard(ptr::null_mut(), || {
        let vfa = c_path(vfa)?;
        let vocoder = c_path(vocoder)?;
        let engine = load_vfa(vfa, vocoder)?;
        Ok(Box::into_raw(Box::new(engine)))
    })
}

/// Nạp `.vfa` tự tìm vocoder bundled cạnh app/package.
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_engine_new_vfa_auto(vfa: *const c_char) -> *mut NativeEngine {
    guard(ptr::null_mut(), || {
        let vfa = c_path(vfa)?;
        let engine = load_vfa_auto(vfa)?;
        Ok(Box::into_raw(Box::new(engine)))
    })
}

/// Nạp model từ path + manifest (kiểm hash/arch/contract).
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_engine_new_verified(
    acoustic: *const c_char,
    vocoder: *const c_char,
    manifest: *const c_char,
) -> *mut NativeEngine {
    guard(ptr::null_mut(), || {
        let acoustic = c_path(acoustic)?;
        let vocoder = c_path(vocoder)?;
        let manifest = c_path(manifest)?;
        let engine = vifasttts_native::load_verified(acoustic, vocoder, manifest)?;
        Ok(Box::into_raw(Box::new(engine)))
    })
}

/// Nạp model từ bytes (bundle iOS/Android). Trả NULL nếu lỗi.
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_engine_from_bytes(
    acoustic: *const u8,
    acoustic_len: usize,
    vocoder: *const u8,
    vocoder_len: usize,
) -> *mut NativeEngine {
    guard(ptr::null_mut(), || {
        if acoustic.is_null() || vocoder.is_null() || acoustic_len == 0 || vocoder_len == 0 {
            return Err("bytes model null/rỗng".to_string());
        }
        let acoustic = unsafe { slice::from_raw_parts(acoustic, acoustic_len) };
        let vocoder = unsafe { slice::from_raw_parts(vocoder, vocoder_len) };
        Ok(Box::into_raw(Box::new(from_bytes(acoustic, vocoder)?)))
    })
}

#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_engine_free(engine: *mut NativeEngine) {
    if engine.is_null() {
        return;
    }
    let _ = catch_unwind(AssertUnwindSafe(|| unsafe {
        drop(Box::from_raw(engine));
    }));
}

/// Tổng hợp → WAV bytes. Caller giải phóng bằng `vifasttts_buffer_free`.
/// Trả NULL nếu lỗi; `*out_len` là số byte.
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_synthesize(
    engine: *mut NativeEngine,
    text: *const c_char,
    options: *const VifasttOptions,
    out_len: *mut usize,
) -> *mut u8 {
    guard(ptr::null_mut(), || {
        if engine.is_null() || out_len.is_null() {
            return Err("engine/out_len null".to_string());
        }
        let text = c_text(text)?;
        let options = synth_options(options);
        let engine = unsafe { &mut *engine };
        let result = engine.synthesize(&text, &options)?;
        let bytes: Box<[u8]> = result.wav.into_boxed_slice();
        let len = bytes.len();
        let ptr = Box::into_raw(bytes) as *mut u8;
        unsafe { *out_len = len };
        Ok(ptr)
    })
}

/// Tổng hợp WAV + karaoke JSON trong một lần chạy.
///
/// - `out_wav`/`out_wav_len`: WAV bytes; giải phóng bằng `vifasttts_buffer_free`.
/// - `out_karaoke`: chuỗi JSON UTF-8; giải phóng bằng `vifasttts_string_free`.
///
/// Trả 0 nếu OK, -1 nếu lỗi; lỗi xem `vifasttts_last_error`.
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_synthesize_karaoke(
    engine: *mut NativeEngine,
    text: *const c_char,
    options: *const VifasttOptions,
    out_wav: *mut *mut u8,
    out_wav_len: *mut usize,
    out_karaoke: *mut *mut c_char,
) -> i32 {
    guard(-1, || {
        if engine.is_null() || out_wav.is_null() || out_wav_len.is_null() || out_karaoke.is_null() {
            return Err("engine/out null".to_string());
        }
        let text = c_text(text)?;
        let options = synth_options(options);
        let engine = unsafe { &mut *engine };
        let result = engine.synthesize(&text, &options)?;
        let document = result
            .karaoke
            .ok_or_else(|| "model không xuất timing (slot_durations)".to_string())?;
        let json =
            serde_json::to_string(&document).map_err(|err| format!("serialize karaoke: {err}"))?;
        let json = CString::new(json).map_err(|_| "karaoke JSON chứa NUL".to_string())?;
        let bytes: Box<[u8]> = result.wav.into_boxed_slice();
        let len = bytes.len();
        unsafe {
            *out_wav = Box::into_raw(bytes) as *mut u8;
            *out_wav_len = len;
            *out_karaoke = json.into_raw();
        }
        Ok(0)
    })
}

/// Như `vifasttts_synthesize` nhưng nhận dialect/OOV/từ điển text.
///
/// Các tham số chuỗi có thể NULL; `dictionary` dùng cùng cú pháp `key = cách đọc`.
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_synthesize_ex(
    engine: *mut NativeEngine,
    text: *const c_char,
    options: *const VifasttOptions,
    dialect: *const c_char,
    resolve_oov: u8,
    dictionary: *const c_char,
    out_len: *mut usize,
) -> *mut u8 {
    guard(ptr::null_mut(), || {
        if engine.is_null() || out_len.is_null() {
            return Err("engine/out_len null".to_string());
        }
        let text = c_text(text)?;
        let options = synth_options_ex(options, dialect, resolve_oov != 0, dictionary)?;
        let engine = unsafe { &mut *engine };
        let result = engine.synthesize(&text, &options)?;
        let bytes: Box<[u8]> = result.wav.into_boxed_slice();
        let len = bytes.len();
        let ptr = Box::into_raw(bytes) as *mut u8;
        unsafe { *out_len = len };
        Ok(ptr)
    })
}

/// Như `vifasttts_synthesize_karaoke` nhưng nhận dialect/OOV/từ điển text.
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_synthesize_karaoke_ex(
    engine: *mut NativeEngine,
    text: *const c_char,
    options: *const VifasttOptions,
    dialect: *const c_char,
    resolve_oov: u8,
    dictionary: *const c_char,
    out_wav: *mut *mut u8,
    out_wav_len: *mut usize,
    out_karaoke: *mut *mut c_char,
) -> i32 {
    guard(-1, || {
        if engine.is_null() || out_wav.is_null() || out_wav_len.is_null() || out_karaoke.is_null() {
            return Err("engine/out null".to_string());
        }
        let text = c_text(text)?;
        let options = synth_options_ex(options, dialect, resolve_oov != 0, dictionary)?;
        let engine = unsafe { &mut *engine };
        let result = engine.synthesize(&text, &options)?;
        let document = result
            .karaoke
            .ok_or_else(|| "model không xuất timing (slot_durations)".to_string())?;
        let json =
            serde_json::to_string(&document).map_err(|err| format!("serialize karaoke: {err}"))?;
        let json = CString::new(json).map_err(|_| "karaoke JSON chứa NUL".to_string())?;
        let bytes: Box<[u8]> = result.wav.into_boxed_slice();
        let len = bytes.len();
        unsafe {
            *out_wav = Box::into_raw(bytes) as *mut u8;
            *out_wav_len = len;
            *out_karaoke = json.into_raw();
        }
        Ok(0)
    })
}

/// Chuyển JSON karaoke thành SRT; caller giải phóng bằng `vifasttts_string_free`.
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_karaoke_to_srt(json: *const c_char) -> *mut c_char {
    guard(ptr::null_mut(), || {
        let text = c_text(json)?;
        let document: KaraokeDocument =
            serde_json::from_str(&text).map_err(|err| format!("karaoke JSON: {err}"))?;
        CString::new(document.to_srt())
            .map(CString::into_raw)
            .map_err(|_| "SRT chứa NUL".to_string())
    })
}

/// Chuyển JSON karaoke thành WebVTT karaoke; caller giải phóng bằng `vifasttts_string_free`.
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_karaoke_to_vtt(json: *const c_char) -> *mut c_char {
    guard(ptr::null_mut(), || {
        let text = c_text(json)?;
        let document: KaraokeDocument =
            serde_json::from_str(&text).map_err(|err| format!("karaoke JSON: {err}"))?;
        CString::new(document.to_vtt_karaoke())
            .map(CString::into_raw)
            .map_err(|_| "VTT chứa NUL".to_string())
    })
}

/// Giải phóng chuỗi do FFI trả về (ví dụ JSON karaoke).
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_string_free(value: *mut c_char) {
    if value.is_null() {
        return;
    }
    let _ = catch_unwind(AssertUnwindSafe(|| unsafe {
        drop(CString::from_raw(value));
    }));
}

pub type VifasttChunkCallback =
    extern "C" fn(samples: *const f32, len: usize, sample_rate: u32, user_data: *mut c_void) -> i32;

/// Streaming PCM. Callback trả 0 = tiếp, khác 0 = huỷ. Trả 0 nếu OK.
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_synthesize_stream(
    engine: *mut NativeEngine,
    text: *const c_char,
    options: *const VifasttOptions,
    callback: Option<VifasttChunkCallback>,
    user_data: *mut c_void,
) -> i32 {
    guard(-1, || {
        let Some(callback) = callback else {
            return Err("callback null".to_string());
        };
        if engine.is_null() {
            return Err("engine null".to_string());
        }
        let text = c_text(text)?;
        let options = synth_options(options);
        let engine = unsafe { &mut *engine };
        let summary = engine.synthesize_stream(&text, &options, |samples, sample_rate| {
            let code = callback(samples.as_ptr(), samples.len(), sample_rate, user_data);
            if code == 0 {
                StreamControl::Continue
            } else {
                StreamControl::Cancel
            }
        })?;
        Ok(if summary.cancelled { 1 } else { 0 })
    })
}

/// Streaming PCM có đầy đủ phương ngữ/OOV/từ điển (dùng cho mobile).
#[allow(clippy::too_many_arguments)]
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_synthesize_stream_ex(
    engine: *mut NativeEngine,
    text: *const c_char,
    options: *const VifasttOptions,
    dialect: *const c_char,
    resolve_oov: u8,
    dictionary: *const c_char,
    callback: Option<VifasttChunkCallback>,
    user_data: *mut c_void,
) -> i32 {
    guard(-1, || {
        let Some(callback) = callback else {
            return Err("callback null".to_string());
        };
        if engine.is_null() {
            return Err("engine null".to_string());
        }
        let text = c_text(text)?;
        let options = synth_options_ex(options, dialect, resolve_oov != 0, dictionary)?;
        let engine = unsafe { &mut *engine };
        let summary = engine.synthesize_stream(&text, &options, |samples, sample_rate| {
            let code = callback(samples.as_ptr(), samples.len(), sample_rate, user_data);
            if code == 0 {
                StreamControl::Continue
            } else {
                StreamControl::Cancel
            }
        })?;
        Ok(if summary.cancelled { 1 } else { 0 })
    })
}

/// Giải phóng buffer WAV do `vifasttts_synthesize` trả về.
#[unsafe(no_mangle)]
pub extern "C" fn vifasttts_buffer_free(ptr: *mut u8, len: usize) {
    if ptr.is_null() || len == 0 {
        return;
    }
    let _ = catch_unwind(AssertUnwindSafe(|| unsafe {
        let slice = ptr::slice_from_raw_parts_mut(ptr, len);
        drop(Box::from_raw(slice));
    }));
}

#[cfg(test)]
mod tests {
    use super::*;

    fn take(ptr: *mut c_char) -> String {
        assert!(!ptr.is_null(), "FFI trả NULL: {}", unsafe {
            CStr::from_ptr(vifasttts_last_error()).to_string_lossy()
        });
        let text = unsafe { CStr::from_ptr(ptr) }.to_string_lossy().to_string();
        vifasttts_string_free(ptr);
        text
    }

    #[test]
    fn json_contract_ffi_roundtrip() {
        let defaults = take(vifasttts_settings_defaults_json());
        assert!(defaults.contains("\"max_chars\": 300"));
        assert!(defaults.contains("\"resolve_oov\": true"));

        let platform = CString::new("android").unwrap();
        let samples = take(vifasttts_sample_texts_json(platform.as_ptr()));
        assert!(samples.contains("Android"));

        let history =
            CString::new(r#"[{"mode":"local","chars":100,"elapsed_ms":500,"audio_seconds":1.0}]"#)
                .unwrap();
        let mode = CString::new("local").unwrap();
        let eta = take(vifasttts_eta_estimate_json(
            history.as_ptr(),
            mode.as_ptr(),
            200,
            20,
        ));
        assert_eq!(eta, "1000");

        let dictionary = CString::new("AI = ây ai").unwrap();
        let parsed = take(vifasttts_dictionary_json(dictionary.as_ptr()));
        assert!(parsed.contains("\"rules\""));
        assert!(!take(vifasttts_api_contract_json()).is_empty());
    }
}
