# Cài đặt ViFastTts

Ưu tiên **Windows** và **macOS**; Linux, Android, iOS, server, extension và TUI ở
các mục sau.

> Release portable nằm ở <https://github.com/dvchd/ViFastTts/releases>. Bản
> `-rc*` là **pre-release**, chưa ký số, model FP32 ~86 MB.

## Windows 10/11 (x64) — ưu tiên

1. Tải `vifasttts-desktop-windows-x64.zip` (hoặc `vifasttts-cli-windows-x64.zip`
   nếu chỉ chạy server).
2. Chuột phải → **Extract All** (đừng chạy trực tiếp trong file ZIP).
3. Mở thư mục, chạy `vifasttts-desktop.exe`.
4. Nếu SmartScreen/Defender cảnh báo: **More info → Run anyway** (bản chưa ký).
5. Bấm **Đọc**; model + ORT đã nằm trong thư mục `models/` và cạnh `.exe`.

Trong desktop:

- **Bật server** → server nội bộ tại `http://127.0.0.1:8000`.
- **Dùng server này** → chuyển chế độ remote sang server vừa bật.
- TUI: mở PowerShell/CMD tại thư mục giải nén:
  ```powershell
  .\vifasttts.exe
  ```

Không cần cài Python/Node/Visual C++ redistributable (bản release đã gom runtime
Rust; nếu Windows thiếu DLL hệ thống, cài VC++ 2015–2022 x64).

## macOS 13+ (Apple Silicon) — ưu tiên

1. Tải `ViFastTts-macos-arm64.zip`.
2. Giải nén, kéo `ViFastTts.app` vào `Applications`.
3. Lần đầu mở: chuột phải → **Open** → **Open** (Gatekeeper).
   Nếu vẫn chặn:
   ```bash
   xattr -dr com.apple.quarantine /Applications/ViFastTts.app
   open /Applications/ViFastTts.app
   ```
4. Vào **Cài đặt → Server nội bộ** để bật server cho extension.

TUI/CLI nằm trong `ViFastTts.app/Contents/MacOS/`:
```bash
# mặc định mở TUI (alias: vifasttts / vtfs)
/Applications/ViFastTts.app/Contents/MacOS/vifasttts
# TUI độc lập
# TUI/CLI/server nằm trong vifasttts
/Applications/ViFastTts.app/Contents/MacOS/vifasttts
# server + web (nếu có web/ cạnh binary)
/Applications/ViFastTts.app/Contents/MacOS/vifasttts server
```

## Linux x64

```bash
tar -xzf vifasttts-desktop-linux-x64.tar.gz
cd vifasttts-desktop-linux-x64
./run.sh
./vifasttts
```

Cần `libasound2`, `libxkbcommon`, X11/Wayland, OpenGL. Ubuntu/Debian:
```bash
sudo apt-get install -y libasound2 libxkbcommon0 libx11-6 libgl1
```
Nếu chạy headless: `./vifasttts-desktop --smoke`.

## Server (Windows/macOS/Linux)

- Windows: `vifasttts-cli-windows-x64.zip` → `vifasttts.exe`.
- macOS: `vifasttts-cli-macos-arm64.tar.gz` → `./run.sh`.
- Linux: `vifasttts-cli-linux-x64.tar.gz` → `./run.sh`.
- Chạy server: `vifasttts server`; API-only: `--api-only`.

```bash
./run.sh --host 127.0.0.1 --port 8000
curl -s http://127.0.0.1:8000/healthz
```

Server nhận `dictionary` text hoặc `overrides` JSON; có thể phục vụ web UI:

```bash
./run.sh --web-dir web --token 'đổi-token' --host 127.0.0.1 --port 8000
# CLI hợp nhất: server + web + auth
vifasttts server --web-dir web --token 'đổi-token' --port 8000
# chỉ API, không phục vụ web
vifasttts server --api-only --port 8000
# web ở origin khác cần thêm --cors
```

Extension remote trỏ tới `http://127.0.0.1:8000`; desktop có nút bật/tắt server
cùng port. Muốn dùng từ điện thoại/IoT trong LAN: bật **Cho phép LAN** (bind
`0.0.0.0`), đặt token, giới hạn firewall; server chưa có TLS.

## Extension + Web

- Extension: tải `extension.zip` → `chrome://extensions` → Developer mode →
  **Load unpacked** → chọn thư mục đã giải nén. Không dùng `ttsEngine`.
- Web local: `web-dist.tar.gz` giải nén (đã kèm `models/` + ORT wasm), phục vụ
  static bằng `python -m http.server` rồi mở `http://127.0.0.1:8000`.

## Android

Tải `app-debug.apk` (debug, chưa ký store), bật **Install unknown apps**, cài và
mở. Đây là client local ONNX + remote HTTP:

- mặc định **local**, model FP32 ~86 MB đóng trong APK;
- tick **Dùng server remote**, nhập URL desktop (`http://IP:8000`) hoặc server
  online, token nếu có;
- chưa có server mode trên Android và chưa có catalog/tải nhiều model;
- quyền: `INTERNET`, `ACCESS_NETWORK_STATE`, Android 16+ `ACCESS_LOCAL_NETWORK`.
  Local HTTP dùng cleartext; production nên HTTPS.

## iOS

`ViFastTtsMobile-ios-simulator.zip` chỉ chạy trên **iOS Simulator** (chưa ký
Apple Developer). Cài Xcode, mở Simulator, kéo app vào; hoặc build từ
`mobile/ios/build-ios.sh`. Thiết bị thật cần ký + ORT device framework.

## Từ source

```bash
# Rust CLI + TUI + server (CLI chứa TUI mặc định)
cargo build --release --manifest-path rust/Cargo.toml \
  -p vifasttts-cli
# binary: rust/target/release/vifasttts (TUI/CLI/server)
# ./vifasttts              -> TUI
# ./vifasttts  / ./vtfs       -> alias ngắn (package release)
# ./vifasttts server       -> server + web
# ./vifasttts synth ...    -> CLI
```

Cần model ONNX + ORT 1.31.1 (`rust/lib/`) như `rust/README.md`. Có thể dùng
bundle `.vfts`:

```bash
rust/target/release/vifasttts vfts pack --output n0.vfts
rust/target/release/vifasttts synth --vfts n0.vfts --text "Xin chào"
```

## Kênh phân phối

| Kênh | Phù hợp | Khuyến nghị |
|---|---|---|
| GitHub Release portable | Desktop Windows/macOS/Linux | **Chính**, đã có CI |
| Winget/Scoop | Windows | Nên thêm sau khi có installer/ký |
| Homebrew cask | macOS | Nên thêm khi có `.dmg`/notarize |
| cargo-binstall | CLI/TUI/server | Nên thêm metadata, tải kèm model/ORT |
| npm/bun | Web/wasm SDK, extension | Chỉ nên đóng gói web/wasm, **không** nhồi model 86 MB |
| PyPI | Server/CLI Python, demo | Đã có Python package; không thay desktop |
| Nix flake | Linux reproducible | Optional/community; cần license ORT/model rõ |
| Flatpak/AppImage | Linux desktop | Sau khi Linux package ổn định |

Model và ORT nên là **asset riêng** (hoặc `.vfts` bundle) thay vì nhét vào npm.

## License

Model/dataset research **CC-BY-NC-4.0 / non-commercial**; ORT MIT. Không phát
hành App Store/Store trước khi xử lý pháp lý.
