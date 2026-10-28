# ViFastTts Mobile

Hai client native, cùng dùng Rust runtime/FFI:

| Nền tảng | Trạng thái | Tài liệu |
|---|---|---|
| Android | **đã build APK + chạy emulator** (local ONNX, C ABI/JNA) | `android/README.md` |
| iOS | **scaffold SwiftUI**, chưa build vì thiếu Xcode/iOS SDK | `ios/README.md` |

## Kiến trúc

```text
Compose / SwiftUI
  → C ABI vifasttts-ffi (JNA hoặc bridging header)
      → NativeEngine (sync wrapper)
          → SynthesisEngine + OrtAcousticModel/OrtVocoderModel
```

- Model ONNX FP32 ~86 MB được đóng trong app (chưa quantize).
- ORT Android 1.31.1 lấy từ AAR; iOS cần ORT 1.31.1 `.a`/XCFramework.
- `vifasttts-mobile` là composition root cho audio sink; client smoke hiện gọi
  C ABI trực tiếp để giảm tầng.

## Kết quả Android (29/10/2026)

- Emulator Android 16 (API 36, arm64-v8a), `-no-audio`.
- APK debug 110 MB; câu mặc định → WAV 4,412 s / 24 kHz / mono PCM16.
- Chưa kiểm tai vì emulator không audio; chưa test thiết bị thật.

## iOS

Máy hiện tại chỉ có Command Line Tools:

```text
xcrun: error: SDK "iphonesimulator" cannot be located
xcodebuild: error: requires Xcode
```

Không thể tự cài Xcode (cần Apple ID/2FA). Scaffold + XcodeGen project đã có;
khi có Xcode chạy `ios/build-ios.sh` (cần ORT iOS).
