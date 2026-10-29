# ViFastTts Mobile — Android

Client Android **local-first + remote**: text → Rust C ABI (`vifasttts-ffi`) → ONNX
Runtime Android → WAV → `MediaPlayer`, hoặc gọi server `/api/tts` (URL + Bearer
token). Không cần Python/server khi đã có APK local.

Đây là client native đã dùng được hằng ngày (View + JNA), không còn chỉ là smoke
test. UI Compose/Flutter vẫn là lựa chọn tương lai, chưa thay bản hiện tại.

## Đã chạy được (29/10/2026)

- Bản **0.3.0** (`versionCode 8`), APK ~110 MB (model FP32 86 MB + ORT 33 MB +
  Rust 6 MB).
- Local/remote; model bundled, `.vfa/.vfts`, cặp ONNX, HuggingFace trực tiếp/server.
- Stream local/remote có **WAV + SRT/VTT/JSON** (toggle “Lưu WAV + phụ đề khi stream”), drain hết buffer, phát 48 kHz.
- Custom reading token-level, history/ETA, auto-play, chọn thư mục xuất, share
  WAV + phụ đề, kiểm tra `/healthz`, tải/đổi tên/xoá model, karaoke.
- Máy: Mac mini M6, Android Emulator **16 (API 36, arm64-v8a)**; emulator có lỗi
  HAL audio nên chất lượng tai chỉ chốt trên thiết bị thật.
- Bấm **Đọc** local với câu mặc định → status `Xong: 4.41 s`; WAV thật trong
  `cache/vifasttts.wav` dài **4,412 s / 24 kHz / mono / PCM16**.
- Remote mode (**Remote** + URL server LAN; URL mặc định để trống) đã test:
  server desktop trả WAV, emulator dùng `http://10.0.2.2:8000` nếu cần,
  `cache/vifasttts-remote.wav` ~2,38 s. Trên điện thoại đổi URL thành IP desktop
  hoặc server online; token nếu server đặt `--token`.
- Không nghe được trong lần chạy này vì emulator bật `-no-audio`; `MediaPlayer`
  đã `prepare()` + `start()` không lỗi. Cần chạy emulator có audio để kiểm tai.

## Yêu cầu

- JDK **21** (AGP 9.0 chưa chạy với JDK 27).
- Android SDK: platform 36, build-tools 36, NDK 28.2.
- Rust targets `x86_64-linux-android`, `aarch64-linux-android`.
- `cargo-ndk` (`cargo install cargo-ndk`), `gradle` (hoặc wrapper).
- Cấu hình trong app: **Cấu hình** → tốc độ, alpha, pause cố định, peak normalize,
  max ký tự/chunk; lưu trong `SharedPreferences`.
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
  - Server URL trống → gọi trực tiếp HuggingFace;
  - nhập Server URL → gọi `/api/models/search|files|download` qua server;
  - lưu vào `filesDir/models/`, ghi active model vào `SharedPreferences`;
  - `.vfts` nạp bằng `vifasttts_engine_new_vfts`;
  - `.vfa` nạp bằng `vifasttts_engine_new_vfa` + `vocoder.onnx` bundled;
  - remote mode vẫn độc lập, không cần tải model.
- UI native dạng programmatic view, chưa Compose; model browser dùng server
  `/api/models/*` hoặc gọi HuggingFace trực tiếp khi URL trống.
- Theme/icon dùng chung: `VfTheme.java`, font Be Vietnam Pro, launcher icon
  lấy từ `resources/brand/vifasttts-icon-512.png`.
- Chưa có: Compose UI, foreground service (chủ động không chạy server nền),
  huỷ tải model giữa chừng, metadata/hash model trên UI, UniFFI/Kotlin binding.
- Output folder dùng Storage Access Framework; Android 11 không cho chọn thẳng
  root `Download`, cần chọn/tạo thư mục con.
- `custom_reading` và ETA/từ điển/sample lấy từ contract Rust (`vifasttts-app`).
- License dataset CC-BY-NC: không phát hành store trước khi xử lý pháp lý.
