# Cài đặt ViFastTts

Ưu tiên **Windows** và **macOS**; Linux, Android, iOS, server, extension và TUI ở
các mục sau.

> Release portable mới nhất: <https://github.com/dvchd/ViFastTts/releases/tag/v0.3.5>.
> Bản desktop chưa ký số; model FP32 nằm sẵn trong gói.

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
- TUI chạy từ terminal (GUI desktop không mở TUI):
  ```powershell
  .\vifasttts.exe tui
  .\vifasttts.exe tui --server http://127.0.0.1:8000
  ```

Không cần cài Python/Node/Visual C++ redistributable (bản release đã gom runtime
Rust; nếu Windows thiếu DLL hệ thống, cài VC++ 2015–2022 x64).

### Tìm model HuggingFace — cần server nào?

| Ứng dụng | Tìm HF | Cần server? |
|---|---|---|
| Desktop | Trực tiếp trong app | **Không** |
| CLI/TUI | Trực tiếp | **Không** |
| Extension | `/api/models/*` | Có, mặc định `http://127.0.0.1:8000` |
| Android/iOS | HuggingFace trực tiếp nếu URL trống; hoặc `/api/models/*` | **Không bắt buộc** |
| Web qua server | `/api/models/*` | Có |
| Web tĩnh | Không tìm, nạp file thủ công | Không |

Nút **Bật server** trên desktop chỉ dành cho extension/mobile/web; desktop vẫn tìm
HuggingFace bình thường khi server tắt. Điện thoại không dùng được `127.0.0.1`;
nhập `http://IP-LAN:8000` và bật **Cho phép LAN** trên desktop.

## macOS 13+ (Apple Silicon) — ưu tiên

1. Tải `vifasttts-desktop-macos-arm64.zip`.
2. Giải nén, kéo `ViFastTts.app` vào `Applications`.
3. Lần đầu mở: chuột phải → **Open** → **Open** (Gatekeeper).
   Nếu vẫn chặn:
   ```bash
   xattr -dr com.apple.quarantine /Applications/ViFastTts.app
   open /Applications/ViFastTts.app
   ```
4. Vào **Cài đặt → Server nội bộ** để bật server cho extension.

Desktop kèm unified binary `ViFastTts.app/Contents/MacOS/vifasttts`
(CLI/TUI/server; GUI không mở TUI):
```bash
# server + web (nếu có web/ cạnh binary)
/Applications/ViFastTts.app/Contents/MacOS/vifasttts server
# TUI local/remote, chỉ từ terminal
/Applications/ViFastTts.app/Contents/MacOS/vifasttts tui
/Applications/ViFastTts.app/Contents/MacOS/vifasttts tui --server http://127.0.0.1:8000
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
- Package CLI/desktop đã kèm thư mục `web/`; server tự tìm `web/` cạnh binary
  (hoặc `web/dist` trong cwd) — không cần tải web riêng.
- Package chỉ giữ **một bản model**: desktop dùng `Resources/`/`models/`, web
  local lấy cùng file qua route `/models/acoustic.onnx` và `/models/vocoder.onnx`.
  Bản `web-dist.tar.gz` standalone vẫn tự kèm `models/` để chạy static.
- Model bundled trong app/APK vẫn là **raw ONNX** để tránh giải nén mỗi lần
  khởi động. `.vfa`/`.vfts` là container để tải/chia sẻ/kiểm hash; server vẫn
  hỗ trợ `--vfa/--vfts`, model browser tải bundle. Raw bundled không phải file
  catalog người dùng tải.

```bash
./run.sh --host 127.0.0.1 --port 8000
curl -s http://127.0.0.1:8000/healthz
```

Server nhận `dictionary` text hoặc `overrides` JSON; có thể phục vụ web UI:

```bash
./run.sh --token 'đổi-token' --host 127.0.0.1 --port 8000
# CLI hợp nhất: server + web + auth (web tự tìm cạnh binary)
vifasttts server --token 'đổi-token' --port 8000
# chỉ API, không phục vụ web
vifasttts server --api-only --port 8000
# web ở origin khác cần thêm --cors
```

Binary **không nhúng** HTML/WASM/ORT; web là asset tĩnh trong package. Nếu chỉ
copy mỗi binary, server vẫn chạy API nhưng không có web. Muốn tách web riêng,
dùng `web-dist.tar.gz` và `--web-dir /đường/dẫn/web-dist`.

Extension remote trỏ tới `http://127.0.0.1:8000`; desktop có nút bật/tắt server
cùng port. Muốn dùng từ điện thoại/IoT trong LAN: bật **Cho phép LAN** (bind
`0.0.0.0`), đặt token, giới hạn firewall; server chưa có TLS.

## Extension + Web

- Extension: tải `vifasttts-extension.zip` → `chrome://extensions` → Developer mode →
  **Load unpacked** → chọn thư mục đã giải nén. Không dùng `ttsEngine`.
- Web local: package desktop/CLI đã kèm `web/`; server tự phục vụ tại `/`.
  Nếu cần web tĩnh riêng, dùng `web-dist.tar.gz` (đã kèm `models/` + ORT wasm),
  phục vụ bằng `python -m http.server` rồi mở `http://127.0.0.1:8000`.
- Khi web được server phục vụ, nó tự kiểm tra `/healthz` và mặc định gọi
  remote same-origin; mở static/file thì mặc định local WASM.
- Web có input nạp `.vfa`/`.vfts`: `.vfa` dùng `/models/vocoder.onnx`, `.vfts`
  tự chứa vocoder; kiểm SHA256 trước khi tạo session.
- Khi server đang chạy, web và extension có mục **Thêm giọng từ HuggingFace**
  gọi `/api/models/*`; không cần tải file thủ công. Server kiểm manifest/hash
  trước khi trả bundle.

## Android

Tải `vifasttts-mobile-android.apk` (debug, chưa ký store), bật **Install unknown apps**, cài và
mở. Đây là client local ONNX + remote HTTP:

- mặc định **local**, model FP32 ~86 MB đóng trong APK;
- nút **Tải model .vfa/.vfts**: để trống Server URL thì tải **trực tiếp
  HuggingFace**; nhập URL server LAN thì tải qua `/api/models/*`; lưu vào
  `filesDir/models/` và dùng cho lần đọc local sau;
- tick **Dùng server remote**, nhập URL desktop (`http://IP:8000`) hoặc server
  online, token nếu có;
- chưa có server mode trên Android;
- quyền: `INTERNET`, `ACCESS_NETWORK_STATE`, Android 16+ `ACCESS_LOCAL_NETWORK`.
  Local HTTP dùng cleartext; production nên HTTPS.

## iOS

`vifasttts-mobile-ios-simulator.zip` chỉ chạy trên **iOS Simulator** (chưa ký
Apple Developer). Cài Xcode, mở Simulator, kéo app vào; hoặc build từ
`mobile/ios/build-ios.sh`. Thiết bị thật cần ký + ORT device framework.

Sheet **Model** trong app: để trống Server URL thì tìm/tải trực tiếp
HuggingFace; nhập URL server LAN thì qua `/api/models/*`; lưu Application
Support và tự nạp lại C ABI.

App có **Local** và **Remote**:

- Local: FFI + ONNX Runtime iOS, model bundled/`.vfa/.vfts`.
- Remote: nhập Server URL (`http://192.168.1.100:8000` — IP LAN của máy chạy
  server, hoặc URL online) + Bearer token, gọi `/api/tts`. Không dùng
  `127.0.0.1` trên điện thoại.
- HTTP dev dùng ATS exception + mô tả Local Network; production nên HTTPS.

Đã build/chạy simulator iOS 27.0 (Xcode 27.1): local FFI và remote đều trả WAV
thành công. Thiết bị thật vẫn cần ký Apple Developer + ORT device slice. Cài
Xcode cần Apple ID/2FA (App Store hoặc Apple Developer), không chỉ mật khẩu sudo.

## Từ source

```bash
# Rust CLI + TUI + server (CLI chứa TUI mặc định)
cargo build --release --manifest-path rust/Cargo.toml \
  -p vifasttts-cli
# binary: rust/target/release/vifasttts (TUI/CLI/server)
# ./vifasttts                          -> TUI local
# ./vifasttts tui --server URL --token ... -> TUI remote
# ./vifasttts tui --vfa n0.vfa --vocoder vocoder.onnx
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
