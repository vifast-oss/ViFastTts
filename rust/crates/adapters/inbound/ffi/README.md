# vifasttts-ffi — C ABI cho mobile/desktop

Crate này là **inbound adapter C ABI**, dùng chung cho:

- iOS (staticlib / XCFramework)
- Android (cdylib / JNI hoặc C ABI)
- desktop native (dylib/staticlib)
- bất kỳ host nào gọi được C

## Đã có

```text
vifasttts_engine_new
vifasttts_engine_new_verified
vifasttts_engine_from_bytes
vifasttts_engine_free

vifasttts_synthesize
vifasttts_synthesize_karaoke
vifasttts_synthesize_stream
vifasttts_buffer_free
vifasttts_string_free

vifasttts_last_error
vifasttts_version
vifasttts_ort_info
```

Header: `include/vifasttts.h`.

- `from_bytes` cho model trong app bundle/asset.
- `catch_unwind` ở biên FFI.
- lỗi qua `vifasttts_last_error` (thread-local).
- streaming PCM qua callback; callback trả khác 0 để huỷ.
- karaoke trả WAV + JSON.
- binary names giữ ổn định (`vifasttts_ffi`), không đổi theo tên crate.

## Build

```bash
# macOS/Linux desktop
cargo build --release -p vifasttts-ffi

# iOS arm64
cargo build --release -p vifasttts-ffi --target aarch64-apple-ios

# Android arm64
cargo build --release -p vifasttts-ffi --target aarch64-linux-android
```

Model và ONNX Runtime mobile phải được đóng gói cùng app; ORT native desktop
dùng `rust/lib/libonnxruntime.*`, còn iOS/Android cần ORT mobile tương ứng.

## Chưa có

- UniFFI bindings tự sinh cho Swift/Kotlin.
- XCFramework script.
- Android NDK/JNI wrapper + `jniLibs` packaging.
- SwiftUI/Kotlin/Compose client.
- desktop client.
- test trên thiết bị iOS/Android thật.
- ORT mobile static/dynamic packaging.

## Quy ước

- `VifasttOptions`, tên hàm C và header **giữ ổn định** để không phá client.
- `NativeEngine` là opaque pointer; caller không cần biết Rust type.
- Engine không thread-safe; mỗi instance gọi từ một worker hoặc bọc mutex ở client.
- Không gọi FFI từ UI thread nếu synth lâu; dùng background thread/queue.
