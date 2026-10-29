# ViFastTts — browser local (WASM + ORT Web)

Demo chạy **hoàn toàn local trong trình duyệt**:

- async engine + frontend/karaoke/iSTFT/WAV: Rust → WASM (`vifasttts-browser`)
- acoustic + vocoder ONNX: **ONNX Runtime Web**; `vifasttts-ort-web` là backend async, JS chỉ chạy model/session
- không server, không gửi text/model ra ngoài

## Chuẩn bị

```bash
# wasm-bindgen CLI (một lần)
cargo install wasm-bindgen-cli --version 0.2.129

# build wasm + npm install + copy model/ORT wasm
./web/build.sh
cd web
npm run dev
```

`build.sh` sẽ:

- build `vifasttts-browser` cho `wasm32-unknown-unknown`;
- chạy `wasm-bindgen --target web` vào `web/pkg/`;
- `npm install`;
- copy `onnxruntime-web/dist/*.wasm` + `*.mjs` vào `web/public/ort/`;
- copy model từ `artifacts/onnx/n0_q/` vào `web/public/models/` nếu có.

## Model

```bash
mkdir -p web/public/models
cp artifacts/onnx/n0_q/acoustic.onnx web/public/models/
cp artifacts/onnx/n0_q/vocoder.onnx web/public/models/
```

Model ~86 MB; lần đầu tải lâu. Không commit `web/public/models/`, `web/pkg/`,
`web/node_modules/`, `web/public/ort/`.

## Chế độ

- **Local WASM**: mặc định, chạy model trong browser.
- **Remote server**: nếu web được server phục vụ, app tự kiểm tra `/healthz`
  và mặc định dùng same-origin remote; nếu mở static/file thì mặc định local.
  Nhập server URL local (`127.0.0.1`), LAN (IP desktop) hoặc online + token nếu cần.
- Đây là **local WASM**, không phải native binary; muốn native dùng desktop/CLI/
  mobile. Remote dùng API `/api/tts` hoặc `/api/tts/stream` của server.
- **Nạp `.vfa`/`.vfts`**: input file trong web; kiểm manifest/SHA256, tạo ONNX
  session ngay trong browser. `.vfa` dùng `/models/vocoder.onnx`; `.vfts` tự chứa
  vocoder.
- **Tìm/tải từ HuggingFace**: khi có server, mục cùng tên gọi
  `/api/models/search|files|download` qua `web/shared/model-api.js` dùng chung
  với extension; server kiểm manifest/hash trước khi trả bundle.
- Server cùng origin có thể phục vụ web bằng `--web-dir web/dist`; server khác
  origin cần bật `--cors` và cấu hình TLS/reverse proxy nếu public.
- Nếu dùng remote, browser không cần tải model local.

## Lưu ý

- `web/app.js` dùng ONNX Runtime Web WASM (`numThreads=1`).
- `web/vite.config.js` trả ORT `.mjs` trong `/ort/` nguyên bản; Vite mặc định
  chặn import module từ `public/`.
- Karaoke/SRT/VTT dùng `slot_durations` từ acoustic.
- Trình duyệt/CPU yếu sẽ chậm hơn native; demo chưa tối ưu, chưa Web Worker/WebGPU.
- Model không khớp vocab/arch: xem `docs/RUST_PORT.md` §15.
- License dataset CC-BY-NC vẫn áp dụng.
