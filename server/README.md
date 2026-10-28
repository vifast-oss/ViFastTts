# ViFastTts HTTP server

Server axum tối giản dùng chung `vifasttts-native`/`vifasttts-app`:

- `GET /healthz`
- `GET /api/config`
- `POST /api/tts` (WAV hoặc JSON karaoke)
- `POST /api/tts/stream` (NDJSON PCM16)
- nhận `dictionary` dạng text hoặc `overrides` JSON; parse bằng
  `vifasttts-app::parse_dictionary`.

## Build

```bash
cargo build --release -p vifasttts-http-server --manifest-path rust/Cargo.toml

# package có ORT + model + run.sh (macOS/Linux)
server/package-unix.sh

# Windows
server/package-windows.ps1
```

## Chạy

```bash
# từ package
./run.sh --host 127.0.0.1 --port 8000

# hoặc từ source (model local)
rust/target/release/vifasttts-server \
  --acoustic artifacts/onnx/n0_q/acoustic.onnx \
  --vocoder artifacts/onnx/n0_q/vocoder.onnx \
  --host 127.0.0.1 --port 8000
```

## Desktop → server → extension

Desktop có nút **Bật server** (cùng port, cùng model). Extension remote trỏ tới
`http://127.0.0.1:8000` (hoặc port đã đổi), cấp host permission localhost.
Đây là cầu nối khuyến nghị; extension **không** gọi trực tiếp native app.

## Giới hạn

- Chưa auth/rate-limit/CORS cho public internet; chỉ dùng localhost/LAN tin cậy.
- macOS/Windows package do CI build; chưa ký notarize.
- Model FP32 ~86 MB; ORT 1.31.1.
