#!/usr/bin/env bash
# Build wasm + JS glue cho browser local demo.
# Chạy từ repo root: ./web/build.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/rust"

cargo build --release -p vifasttts-browser --target wasm32-unknown-unknown
mkdir -p "$ROOT/web/pkg"
wasm-bindgen --target web \
  --out-dir "$ROOT/web/pkg" \
  --out-name vifasttts_wasm \
  target/wasm32-unknown-unknown/release/vifasttts_wasm.wasm

cd "$ROOT/web"
npm install
mkdir -p public/ort models
if [ -d node_modules/onnxruntime-web/dist ]; then
  cp node_modules/onnxruntime-web/dist/*.wasm public/ort/ 2>/dev/null || true
  cp node_modules/onnxruntime-web/dist/*.mjs public/ort/ 2>/dev/null || true
fi
if [ -f "$ROOT/artifacts/onnx/n0_q/acoustic.onnx" ]; then
  cp "$ROOT/artifacts/onnx/n0_q/acoustic.onnx" models/
  cp "$ROOT/artifacts/onnx/n0_q/vocoder.onnx" models/
fi

echo "Xong. Chạy: cd web && npm run dev"
