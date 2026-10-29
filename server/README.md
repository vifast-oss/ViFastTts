# ViFastTts HTTP server

Server axum tối giản dùng chung `vifasttts-native`/`vifasttts-app`:

- `GET /healthz`
- `GET /api/config`
- `POST /api/tts` (WAV hoặc JSON karaoke)
- `POST /api/tts/stream` (NDJSON PCM16)
- `GET /api/models/search?q=...` (HuggingFace catalog, chỉ trả bundle)
- `GET /api/models/files?repo=...`
- `GET /api/models/download?repo=...&path=...` (đã kiểm manifest/hash)
- nhận `dictionary` dạng text hoặc `overrides` JSON; parse bằng
  `vifasttts-app::parse_dictionary`;
- `--web-dir web/dist` phục vụ web UI (SPA + model/ORT) tại `/`; nếu không
  truyền, server tự tìm `web/` cạnh binary hoặc `web/dist`/`web` trong cwd;
- `--cors` cho web UI ở origin khác gọi API (chỉ bật khi cần);
- `--api-only` bỏ web UI, chỉ chạy API dù có thư mục web;
- `--token` (hoặc env `VIFASTTS_TOKEN`) bảo vệ `/api/*` bằng Bearer;
- `--vfts model.vfts` nạp bundle full thay cho `--acoustic/--vocoder`.
- `--vfa model.vfa --vocoder vocoder.onnx` nạp acoustic-only, dùng chung vocoder;
- `--model-dir models` cache bundle tải bởi model browser/UI (mặc định `models`).

## Build

```bash
cargo build --release -p vifasttts-cli --manifest-path rust/Cargo.toml

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
rust/target/release/vifasttts server \
  --acoustic artifacts/onnx/n0_q/acoustic.onnx \
  --vocoder artifacts/onnx/n0_q/vocoder.onnx \
  --host 127.0.0.1 --port 8000

# gộp web UI + auth
rust/target/release/vifasttts server \
  --acoustic artifacts/onnx/n0_q/acoustic.onnx \
  --vocoder artifacts/onnx/n0_q/vocoder.onnx \
  --web-dir web/dist --token 'đổi-token' --port 8000

# hoặc bundle .vfts
rust/target/release/vifasttts server --vfts n0.vfts --port 8000
```

## Desktop → server → extension/điện thoại/IoT

Desktop có nút **Bật server** (cùng port, cùng model), mặc định bind
`127.0.0.1`. Bật **Cho phép LAN** để bind `0.0.0.0` và dùng từ điện thoại/IoT:

```text
http://<LAN-IP>:8000/api/tts        (POST JSON, trả WAV)
http://<LAN-IP>:8000/api/tts/stream (NDJSON)
```

- Chỉ dùng LAN tin cậy; **đặt token** và firewall. Server chưa có TLS.
- Extension remote trỏ tới `http://127.0.0.1:8000` (hoặc LAN URL), cấp host
  permission. Đây là cầu nối khuyến nghị; extension **không** gọi trực tiếp native app.
- Web UI có thể được server phục vụ bằng `--web-dir web/dist` (cùng origin,
  không cần CORS).

## Giới hạn

- Model API dùng chung cho desktop/CLI/TUI/web/extension/Android/iOS; server
  kiểm manifest/hash trước khi trả `.vfa/.vfts`.
- Chưa rate-limit; CORS phải bật rõ bằng `--cors`; chỉ dùng localhost/LAN tin cậy.
- macOS/Windows package do CI build; chưa ký notarize.
- Model FP32 ~86 MB; ORT 1.31.1.
