# ViFastTts Mobile — iOS

Client SwiftUI **local-first + remote HTTP**:

- Local: Rust C ABI (`vifasttts-ffi`) → ONNX Runtime iOS → WAV.
- Remote: `POST /api/tts` tới server desktop/LAN/online → WAV.
- UI chọn Local/Remote, nhập Server URL + Bearer token. `AVAudioPlayer` phát WAV.

## Trạng thái (29/10/2026)

**Đã build và chạy trên iOS Simulator 27.0** với Xcode 27.1:

```text
Local FFI:  Xong local  · 2.77 s
Remote:     Xong remote · 2.77 s
Model:      Bundled acoustic/vocoder
```

Xcode cài đặt cần Apple ID/2FA (App Store/Apple Developer), không chỉ mật khẩu
sudo. Thiết bị thật vẫn cần ký Apple Developer và ORT device slice.

## Có gì

- `App.swift`, `ContentView.swift`: UI SwiftUI tối thiểu (text, local/remote,
  server URL/token, đọc, dừng, trạng thái, sheet Model).
- `Theme.swift`: palette/font dùng chung; icon app lấy từ `resources/brand/`.
- `TtsEngine.swift`: cầu nối C ABI, serial queue, synth async, ghi WAV tạm,
  `AVAudioPlayer`; nạp `.vfa/.vfts` và ghi nhớ active model.
- `RemoteTts.swift`: gọi `/api/tts`, nhận WAV hoặc JSON `audio_base64`,
  Bearer token; dùng chung Server URL/token với model browser.
- `ModelCatalog.swift`, `ModelBrowserView.swift`: Server URL trống → gọi
  HuggingFace trực tiếp; nhập URL → qua server `/api/models/*`.
- `ContentView` + `TtsEngine`/`RemoteTts`: sheet **Cấu hình** cho tốc độ, alpha,
  pause cố định, peak normalize, max ký tự/chunk; truyền vào FFI local và server remote.
- `ViFastTtsMobile-Bridging-Header.h`: include trực tiếp header canonical của
  crate FFI, không copy hợp đồng.
- `project.yml`: XcodeGen spec; link `libvifasttts_ffi.a` + `onnxruntime.framework`.
- `build-ios.sh`: build Rust staticlib simulator/device, copy ORT framework + model,
  generate project, `xcodebuild`, zip app simulator.

## Build khi có Xcode

```bash
# 1) Cài Xcode đầy đủ, chọn developer dir
sudo xcode-select -s /Applications/Xcode.app
xcodebuild -version

# 2) ORT iOS: tải pod archive onnxruntime-c 1.30.0
#    https://download.onnxruntime.ai/pod-archive-onnxruntime-c-1.30.0.zip
#    rồi trỏ tới xcframework đã giải nén:
ONNXRUNTIME_XCFRAMEWORK=/path/to/onnxruntime.xcframework \
  mobile/ios/build-ios.sh
```

`project.yml` dùng `OTHER_LDFLAGS="-lvifasttts_ffi -framework onnxruntime -framework Network -lc++"`,
`LIBRARY_SEARCH_PATHS=ViFastTtsFFI/lib` và `FRAMEWORK_SEARCH_PATHS=ViFastTtsFFI/Frameworks`;
script đổ Rust `.a` + framework + model vào đó.

## Chưa có

- Thiết bị thật: ký Apple Developer, ORT device slice/chứng chỉ.
- HTTP remote dùng ATS exception cho dev; production nên HTTPS.
- Audio session/background playback, streaming PCM, settings/history/dictionary.
- UniFFI/Swift binding tự sinh; hiện gọi C ABI trực tiếp.
- ORT iOS dùng framework **static 1.30.0** (`api-30`); desktop/Android vẫn dùng
  load-dynamic 1.31.1. Build iOS dùng `cargo rustc --crate-type staticlib`, Xcode
  link `onnxruntime.framework`.
- Artifact CI chỉ build simulator arm64; thiết bị thật cần slice device + ký.
- License CC-BY-NC trước khi phát hành App Store.

## Vì sao không dùng Flutter?

Chưa chốt. Scaffold này cố ý native SwiftUI để đo runtime/FFI trước; nếu sau
này chọn Flutter, `MobileRuntime` + C ABI vẫn dùng được qua `dart:ffi`.
