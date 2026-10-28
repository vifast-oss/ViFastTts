# ViFastTts Mobile — iOS

Client SwiftUI **local-first** gọi Rust C ABI (`vifasttts-ffi`) → ONNX Runtime
iOS → WAV → `AVAudioPlayer`.

## Trạng thái (29/10/2026)

**Chưa build/chạy được trên máy này** vì không có Xcode/iOS SDK:

```text
xcodebuild: error: tool 'xcodebuild' requires Xcode, but active developer
directory '/Library/Developer/CommandLineTools' is a command line tools instance
xcrun: error: SDK "iphonesimulator" cannot be located
```

Vì vậy đây là **scaffold source + script**, không phải bằng chứng chạy iOS.
Không thể tự cài Xcode: cần Apple ID/2FA và App Store/Apple Developer.

## Có gì

- `App.swift`, `ContentView.swift`: UI SwiftUI tối thiểu (text, đọc, dừng, trạng thái).
- `TtsEngine.swift`: cầu nối C ABI, serial queue, synth async, ghi WAV tạm,
  `AVAudioPlayer`.
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

# 2) ORT iOS: tải pod archive onnxruntime-c (bản mới nhất có sẵn; hiện 1.30.0)
#    https://download.onnxruntime.ai/pod-archive-onnxruntime-c-1.30.0.zip
#    rồi trỏ tới xcframework đã giải nén:
ONNXRUNTIME_XCFRAMEWORK=/path/to/onnxruntime.xcframework \
  mobile/ios/build-ios.sh
```

`project.yml` dùng `OTHER_LDFLAGS="-lvifasttts_ffi -framework onnxruntime -lc++"`,
`LIBRARY_SEARCH_PATHS=ViFastTtsFFI/lib` và `FRAMEWORK_SEARCH_PATHS=ViFastTtsFFI/Frameworks`;
script đổ Rust `.a` + framework + model vào đó.

## Chưa có

- Chạy trên simulator/thiết bị thật, ký Apple Developer, XCFramework/bitcode.
- Audio session/background playback, streaming PCM, settings/history/dictionary.
- UniFFI/Swift binding tự sinh; hiện gọi C ABI trực tiếp.
- ORT iOS adapter hoàn chỉnh: pod archive mới nhất là **1.30.0** (chưa có 1.31.1
  trên CocoaPods); Rust dùng load-dynamic 1.31.1 nên cần test runtime tương thích.
- Artifact CI chỉ build simulator arm64; thiết bị thật cần slice device + ký.
- License CC-BY-NC trước khi phát hành App Store.

## Vì sao không dùng Flutter?

Chưa chốt. Scaffold này cố ý native SwiftUI để đo runtime/FFI trước; nếu sau
này chọn Flutter, `MobileRuntime` + C ABI vẫn dùng được qua `dart:ffi`.
