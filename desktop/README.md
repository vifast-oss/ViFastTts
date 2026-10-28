# ViFastTts Desktop

App desktop **local-first** bằng Rust + egui; dùng chung runtime Rust/ONNX với
CLI, server, extension và mobile.

- Local: nạp `acoustic.onnx` + `vocoder.onnx`, synth bằng `vifasttts-native`.
- Remote: gọi server `/api/tts` (WAV + karaoke JSON) qua `vifasttts-http-client`.
- Có: chọn phương ngữ, tốc độ, alpha, fixed pause, peak normalize, ETA theo lịch
  sử, từ điển local, phát audio, lưu WAV/SRT/VTT, cấu hình model/thư mục xuất,
  mở tệp `.txt/.md`, `Cmd+Enter` để đọc, `Esc` để dừng phát.
- Cùng `vifasttts-app` / `vifasttts-text` / `vifasttts-engine`; UI không chứa
  logic model.

## Chạy từ source

```bash
# từ repo root (model mặc định artifacts/onnx/n0_q)
rust/target/release/vifasttts-desktop

# hoặc build rồi chạy
cargo build --release -p vifasttts-desktop --manifest-path rust/Cargo.toml
rust/target/release/vifasttts-desktop
```

Kiểm tra headless (nạp model + synth + WAV, không mở cửa sổ):

```bash
rust/target/release/vifasttts-desktop --smoke
# SMOKE OK 24000 Hz · 2.51 s · 120364 B WAV · riff=true
```

## Đóng gói

### macOS

```bash
rust/crates/adapters/inbound/desktop/package-macos.sh --run
# APP: .../desktop/dist/ViFastTts.app
# ZIP: .../desktop/dist/ViFastTts-macos-<arch>.zip
```

App tự tìm model trong `Contents/Resources/` và ORT trong `Contents/MacOS/`
(nhờ `resolve_model_path` + `load-dynamic`). Bundle ~127 MB (model FP32 86 MB + ORT 32 MB + binary 13 MB). Chưa ký notarize; `codesign --sign -` chỉ là ad-hoc.

### Linux x64

```bash
rust/crates/adapters/inbound/desktop/package-linux.sh
# .../desktop/dist/vifasttts-desktop-linux-x64.tar.gz
# giải nén: ./run.sh hoặc ./vifasttts-desktop --smoke
```

### Windows x64

```powershell
rust/crates/adapters/inbound/desktop/package-windows.ps1
# ...\desktop\dist\vifasttts-desktop-windows-x64.zip
# giải nén: .\vifasttts-desktop.exe --smoke
```

Cả hai package chứa `models/acoustic.onnx`, `models/vocoder.onnx`,
`libonnxruntime`/`onnxruntime.dll`, kèm `vifasttts` (CLI/TUI/server) và `web/` nếu build có web; app tự tìm theo
thư mục executable. CI build cả ba nền tảng; macOS/Linux đã test
smoke, Windows do CI test.

## Cấu hình

- `~/Library/Application Support/com.vifasttts.ViFastTts/desktop.json` (theo
  `directories`); lưu settings + history ETA + đường dẫn model/`.vfts`.
- Model mặc định tương đối `artifacts/onnx/n0_q/` khi chạy từ repo.
- Remote mặc định `http://127.0.0.1:8000`; token Bearer tuỳ chọn.

## Giới hạn hiện tại

- Local synth chạy trên worker thread nhưng **chưa streaming PCM**; nút **Dừng phát**
  chỉ dừng audio, request local đang chạy vẫn hoàn tất (engine không có cancel cho
  `synthesize` thường).
- Có **server nội bộ** trong Settings: bật/tắt `vifasttts server` cùng port;
  extension/điện thoại/IoT remote trỏ tới `http://127.0.0.1:<port>` (không gọi
  native trực tiếp). Đặt thư mục `web/` cạnh binary (giải nén `web-dist.tar.gz`)
  để server nội bộ tự phục vụ web UI.
- Có **TUI/CLI/server** trong `vifasttts` (không tham số = TUI;
  `server` = HTTP server + web nếu có `web/`).
- Chưa có system tray, menu native, auto-update, ký notarize; Linux/Windows
  package do CI tạo và smoke, chưa test tay trên máy thật.
- UI chưa dùng chung asset/theme với extension; sẽ gom branding khi chốt Flutter
  vs native.
