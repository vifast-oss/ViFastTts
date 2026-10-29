#!/usr/bin/env bash
# Build wasm/pkg + copy ORT Web + model vào extension (local, không commit).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXT="$ROOT/extension"
WEB="$ROOT/web"
ORT="$WEB/node_modules/onnxruntime-web/dist"

mkdir -p "$EXT/vendor/pkg" "$EXT/vendor/ort" "$EXT/models" "$EXT/shared"

echo "==> Copy shared model API"
cp "$ROOT/web/shared/model-api.js" "$EXT/shared/model-api.js"
cp "$ROOT/web/shared/bundle.js" "$EXT/shared/bundle.js"
cp "$ROOT/web/shared/theme.css" "$EXT/shared/theme.css"
mkdir -p "$EXT/fonts"
cp "$ROOT/resources/fonts/BeVietnamPro-Regular.ttf" "$EXT/fonts/BeVietnamPro-Regular.ttf"

echo "==> Build wasm"
cd "$ROOT/rust"
cargo build --release -p vifasttts-browser --target wasm32-unknown-unknown
wasm-bindgen --target web \
  --out-dir "$EXT/vendor/pkg" \
  --out-name vifasttts_wasm \
  target/wasm32-unknown-unknown/release/vifasttts_wasm.wasm

echo "==> Chuẩn bị ORT Web"
cd "$WEB"
if [ ! -d "$ORT" ]; then
  npm install
fi
cp "$ORT/ort.wasm.min.mjs" "$EXT/vendor/ort/"
cp "$ORT/ort-wasm-simd-threaded.mjs" "$EXT/vendor/ort/"
cp "$ORT/ort-wasm-simd-threaded.wasm" "$EXT/vendor/ort/"

echo "==> Copy model (nếu có)"
for name in acoustic vocoder; do
  src="$ROOT/artifacts/onnx/n0_q/$name.onnx"
  if [ -f "$src" ]; then
    cp "$src" "$EXT/models/$name.onnx"
  else
    echo "    thiếu $src — extension sẽ cần Model base URL"
  fi
done

echo "==> Xong"
echo "Load unpacked: $EXT"
echo "Hoặc test: agent-browser --extension '$EXT' open about:blank"
