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

use vifasttts_native::{NativeEngine, StreamControl, SynthesisOptions, from_bytes, load, ort_info};

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
