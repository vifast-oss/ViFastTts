# ViFastTts Mobile — Android

Client Android **local-first + remote**: text → Rust C ABI (`vifasttts-ffi`) → ONNX
Runtime Android → WAV → `MediaPlayer`, hoặc gọi server `/api/tts` (URL + Bearer
token). Không cần Python/server khi đã có APK local.

Đây là **smoke client** để chứng minh đường mobile chạy thật, không phải bản UI
production. UI SwiftUI/Compose/Flutter cuối cùng vẫn chưa chốt.

## Đã chạy được (29/10/2026)

- Máy: Mac mini M6, Android Emulator **16 (API 36, arm64-v8a)**, không audio.
- APK: `app-debug.apk` ~110 MB (model FP32 86 MB + ORT 33 MB + Rust 5 MB);
  release asset đổi tên thành `vifasttts-mobile-android.apk`.
- Bấm **Đọc** local với câu mặc định → status `Xong: 4.41 s`; WAV thật trong
  `cache/vifasttts.wav` dài **4,412 s / 24 kHz / mono / PCM16**.
- Remote mode (checkbox **Dùng server remote**, URL mặc định
  `http://10.0.2.2:8000` cho emulator) đã test: server desktop trả WAV,
  `cache/vifasttts-remote.wav` ~2,38 s. Trên điện thoại đổi URL thành IP desktop
  hoặc server online; token nếu server đặt `--token`.
- Không nghe được trong lần chạy này vì emulator bật `-no-audio`; `MediaPlayer`
  đã `prepare()` + `start()` không lỗi. Cần chạy emulator có audio để kiểm tai.

## Yêu cầu

- JDK **21** (AGP 9.0 chưa chạy với JDK 27).
- Android SDK: platform 36, build-tools 36, NDK 28.2.
- Rust targets `x86_64-linux-android`, `aarch64-linux-android`.
- `cargo-ndk` (`cargo install cargo-ndk`), `gradle` (hoặc wrapper).
- Model local: `artifacts/onnx/n0_q/{acoustic,vocoder}.onnx` (không commit).
- ORT Android AAR 1.31.1 (script tự tải từ Maven).

## Build

```bash
# một lần: toolchain
rustup target add x86_64-linux-android aarch64-linux-android
cargo install cargo-ndk
brew install --cask temurin@21 android-commandlinetools gradle
sdkmanager 'platform-tools' 'platforms;android-36' 'build-tools;36.0.0' \
  'ndk;28.2.13676358' 'emulator' 'system-images;android-36;google_apis;arm64-v8a'

# build APK (tự build Rust cdylib, tách ORT, copy model)
ANDROID_HOME=/opt/homebrew/share/android-commandlinetools \
  mobile/android/build.sh
```

`cargo-ndk` đặt `libvifasttts_ffi.so` vào `app/src/main/jniLibs/<abi>/`; ORT
`libonnxruntime.so` nằm cùng thư mục. App set `VIFASTT_ORT_DYLIB` trước khi gọi
C ABI (Rust dùng `load-dynamic`).

## Chạy emulator

```bash
export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
export PATH="$ANDROID_HOME/platform-tools:$PATH"
avdmanager create avd -n vifasttts \
  -k 'system-images;android-36;google_apis;arm64-v8a' --device pixel_7 --force
$ANDROID_HOME/emulator/emulator -avd vifasttts \
  -no-window -no-audio -no-boot-anim -gpu swiftshader_indirect -no-snapshot
adb wait-for-device
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n com.vifasttts.mobile/.MainActivity
```

## Quyền mạng

- `INTERNET`, `ACCESS_NETWORK_STATE`.
- Android 16+ LAN: `ACCESS_LOCAL_NETWORK` (runtime request); Android 17 target
  37 sẽ bắt buộc.
- `usesCleartextTraffic="true"` để gọi local HTTP; production nên dùng HTTPS.
- Không có foreground service vì APK **không chạy server**; server nằm ở desktop.

## Ghi chú kỹ thuật

- Dùng **JNA** gọi C ABI (không cần viết JNI C++); APK phải bật
  `android:extractNativeLibs="true"` + `useLegacyPackaging = true` để ORT có
  đường dẫn thật trong `nativeLibraryDir`.
- Local mặc định vẫn đóng model FP32 ~86 MB trong APK (`assets/`) và copy sang
  `filesDir`; remote mode không cần model local.
- Nút **Tải model .vfa/.vfts** (29/10/2026):
  - gọi server `/api/models/search|files|download` bằng URL/token đang nhập;
  - lưu vào `filesDir/models/`, ghi active model vào `SharedPreferences`;
  - `.vfts` nạp bằng `vifasttts_engine_new_vfts`;
  - `.vfa` nạp bằng `vifasttts_engine_new_vfa` + `vocoder.onnx` bundled;
  - remote mode vẫn độc lập, không cần tải model.
- UI vẫn là smoke client (programmatic view), chưa Compose; catalog nằm ở
  server, không lặp logic HuggingFace trong Java.
- Chưa có: Compose UI, audio focus/foreground service, streaming PCM xuống
  AAudio, history/settings, UniFFI/Kotlin binding, quản lý nhiều model/active
  model bằng UI (hiện chỉ một active model).
- License dataset CC-BY-NC: không phát hành store trước khi xử lý pháp lý.
