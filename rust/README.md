# ViFastTts Rust port

Port **inference** sang Rust (không port train/data/export). Workspace này là
WIP, chưa thay production; xem `docs/RUST_PORT.md` §15.

## Yêu cầu

- Rust **1.99.1** (ghim trong `rust-toolchain.toml`; MSRV khai báo 1.99).
- Model ONNX local (không commit):
  - `artifacts/onnx/n0_q/acoustic.onnx`
  - `artifacts/onnx/n0_q/vocoder.onnx`
- `ort = 2.0.0-rc.15` với `load-dynamic` + **ONNX Runtime 1.31.1** (khớp live).
  Thư viện nằm ở `rust/lib/`; khi phát hành phải đóng gói cạnh binary/app.

## Build / kiểm tra

```bash
cd rust
cargo build --release -p vifasttts-cli -p vifasttts-tools -p vifasttts-parse
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
cargo fmt --all -- --check
```

Binary: `rust/target/release/vifasttts-rs` (~7,5 MB, gồm HTTP client) + thư viện ORT trong `rust/lib/`.

## Lệnh

```bash
# Xem metadata/hash model + ORT thực tế
rust/target/release/vifasttts-rs inspect
rust/target/release/vifasttts-rs inspect --from-bytes
rust/target/release/vifasttts-rs inspect --manifest rust/models/n0-q.manifest.json

# Tổng hợp local
rust/target/release/vifasttts-rs synth --text "Chào bạn" --output out.wav

# Gọi server remote
rust/target/release/vifasttts-rs synth --server http://127.0.0.1:8000 \
  --text "Chào bạn" --output out.wav

# Karaoke: JSON + SRT + WebVTT (karaoke inline timestamp)
rust/target/release/vifasttts-rs synth --text "Xin chào các bạn" \
  --output out.wav --karaoke out.json --srt out.srt --vtt-karaoke out.vtt

# Fixed pause + speed
rust/target/release/vifasttts-rs synth --text "Một. Hai!" \
  --output out.wav --fixed-pauses --speed 0.9

# Mel từ 7 ID (debug/parity)
rust/target/release/vifasttts-rs mel-ids --features features.json --output mel.f32

# Streaming PCM (CLI gom để kiểm tra WAV; có thể xuất karaoke)
rust/target/release/vifasttts-rs stream --text "..." --output out-stream.wav \
  --karaoke out-stream.json

# Server tối thiểu
cargo run --release -p vifasttts-cli -- server --port 8000
curl -s http://127.0.0.1:8000/healthz
curl -sS -X POST http://127.0.0.1:8000/api/tts \
  -H 'Content-Type: application/json' \
  -d '{"text":"Xin chào","karaoke":true}'
curl -sS -N -X POST http://127.0.0.1:8000/api/tts/stream \
  -H 'Content-Type: application/json' \
  -d '{"text":"Xin chào"}'

# Desktop GUI + TUI + server + CLI (cần model local)
cargo build --release -p vifasttts-desktop -p vifasttts-cli
./target/release/vifasttts-desktop --smoke
./target/release/vifasttts-rs              # mặc định mở TUI
# package release có alias: vifasttts, vtfs
./target/release/vifasttts-rs server       # server + web (nếu có web/)
./target/release/vifasttts-rs server --api-only  # chỉ API
./target/release/vifasttts-rs --help

# Model bundle full .vfts (manifest + ONNX + snapshot resources)
rust/target/release/vifasttts-rs vfts pack --output n0.vfts
rust/target/release/vifasttts-rs vfts inspect n0.vfts
rust/target/release/vifasttts-rs synth --vfts n0.vfts --text "Xin chào" --output out.wav

# Acoustic-only .vfa (~28 MB) dùng chung Vocos pretrained
rust/target/release/vifasttts-rs vfa pack --output n0.vfa \
  --vocoder artifacts/onnx/n0_q/vocoder.onnx
rust/target/release/vifasttts-rs synth --vfa n0.vfa \
  --vocoder artifacts/onnx/n0_q/vocoder.onnx --text "Xin chào" --output out.wav

# C ABI (macOS; Linux/Windows build tương tự)
cargo build --release -p vifasttts-ffi
# header: crates/adapters/inbound/ffi/include/vifasttts.h
# artifact: target/release/libvifasttts_ffi.{dylib,so} / vifasttts_ffi.dll
# karaoke: vifasttts_synthesize_karaoke -> WAV + JSON timing

# Benchmark trong process (load một lần)
rust/target/release/vifasttts-rs bench --text "..." --runs 20 --warmup 3
```

`synth` mặc định dùng **profile live**: built-in `overrides_vi.json` + custom
reading rỗng (đúng container hiện tại). Có thể truyền `--overrides file.json`
và `--custom-reading file.json`.

## Parity frontend

Chạy từ repo root (build `vifasttts-parse` trước):

```bash
cargo build --release -p vifasttts-parse
.venv/bin/python tools/rust_parity.py --matrix --reuse \
  --output artifacts/rust_parity_matrix
.venv/bin/python tools/rust_parity.py --full-custom \
  --output artifacts/rust_parity_full
.venv/bin/python tools/rust_parity.py --fuzz 3000 \
  --output artifacts/rust_parity_fuzz_clean
```

Kết quả chốt 28/10/2026:

- matrix 50.789 case: 0 mismatch (normalized + parsed + 7 ID);
- full custom 1.995 case: 0 mismatch;
- fuzz NFC thực tế 4.980 case: 0 mismatch;
- fuzz raw có dấu kết hợp rời: 391 mismatch — ngoại lệ có tên, ngoài input
  canonical; không dùng để kết luận parser lỗi.

## Cấu trúc

- `vifasttts-text`: frontend/parser/vocab/normalizer/chunk/karaoke text; tài nguyên nhúng `resources/`.
- `vifasttts-audio`: iSTFT/sharpen/fade/WAV.
- `vifasttts-vfts`: bundle `.vfts` (manifest + ONNX + snapshot frontend; hash/loader).
- `vifasttts-ports`: async trait `AcousticModel`/`VocoderModel` + `MelSpectrogram`/`ComplexSpectrogram`/`ModelInfo`.
- `vifasttts-audio-sink`, `vifasttts-transport`, `vifasttts-settings`, `vifasttts-model-source`: port contracts cho UI/native.
- `vifasttts-engine`: orchestration async backend-agnostic + streaming + timing.
- `vifasttts-app`: headless command/event + ETA cho UI.
- `vifasttts-ort`: ONNX Runtime native session/metadata/hash/from_bytes/manifest.
- `vifasttts-ort-web`: ORT Web async backend (JS callback) cho browser.
- `vifasttts-native`: native adapter — async engine + ORT, API sync `load`/`from_bytes`/`load_verified`.
- `vifasttts-mobile`: mobile composition root — model, status, synth, `AudioSink` (iOS/Android).
- `vifasttts-browser`: browser adapter — async engine + `ort-web`, parse/karaoke/DSP helpers.
- `vifasttts-desktop`: app desktop egui (local + remote + server nội bộ, settings/dictionary/ETA, audio playback).
- `vifasttts-tui`: library TUI ratatui/crossterm; CLI không args mở TUI.
- `vifasttts-http-client`: HTTP client `/healthz`, `/api/config`, `/api/tts` (WAV/karaoke).
- `vifasttts-cli`: CLI production (synth/stream/bench/inspect).
- `vifasttts-tools`: parity model (mel-ids, synth-ids).
- `vifasttts-parse`: parse/parse-batch text-only (không ORT).
- `vifasttts-ffi`: C ABI cho iOS/Android/desktop; header trong `include/`;
  hướng dẫn mobile trong `rust/crates/adapters/inbound/ffi/README.md`.
- `vifasttts-http-server`: library axum; CLI `server` là entrypoint; `/healthz`, `/api/tts`, stream, web/API-only.

## Browser local

`vifasttts-browser` + `vifasttts-ort-web` + ORT Web demo: xem `web/README.md`.
Model chạy hoàn toàn trong browser; cần copy model + ORT Web wasm vào `web/`.
`browser` và `native` là hai adapter ngang hàng, cùng dùng async `vifasttts-engine`.
