#!/usr/bin/env bash
# Đóng gói desktop Linux x64: binary + ORT + model + launcher.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../../../.." && pwd)"
MODEL_DIR="${MODEL_DIR:-$ROOT/artifacts/onnx/n0_q}"
OUT="${OUT:-$ROOT/desktop/dist/vifasttts-desktop-linux-x64}"
ARCHIVE="${ARCHIVE:-$ROOT/desktop/dist/vifasttts-desktop-linux-x64.tar.gz}"
ORT_VERSION="${ORT_VERSION:-1.31.1}"
CACHE="${CACHE:-$ROOT/desktop/dist/cache}"
ORT_LIB="${ORT_LIB:-}"

[ -f "$MODEL_DIR/acoustic.onnx" ] || { echo "Thiếu $MODEL_DIR/acoustic.onnx" >&2; exit 2; }
[ -f "$MODEL_DIR/vocoder.onnx" ] || { echo "Thiếu $MODEL_DIR/vocoder.onnx" >&2; exit 2; }

if [ -z "$ORT_LIB" ] || [ ! -f "$ORT_LIB" ]; then
  mkdir -p "$CACHE"
  archive="$CACHE/onnxruntime-linux-x64-$ORT_VERSION.tgz"
  if [ ! -f "$archive" ]; then
    curl -L --fail -o "$archive" \
      "https://github.com/microsoft/onnxruntime/releases/download/v$ORT_VERSION/onnxruntime-linux-x64-$ORT_VERSION.tgz"
  fi
  rm -rf "$CACHE/onnxruntime-linux-x64-$ORT_VERSION"
  tar -xzf "$archive" -C "$CACHE"
  ORT_LIB="$CACHE/onnxruntime-linux-x64-$ORT_VERSION/lib/libonnxruntime.so"
fi

(cd "$ROOT/rust" && cargo build --release -p vifasttts-desktop -p vifasttts-cli)

rm -rf "$OUT"
mkdir -p "$OUT/models"
cp "$ROOT/rust/target/release/vifasttts-desktop" "$OUT/vifasttts-desktop"
cp "$ROOT/rust/target/release/vifasttts" "$OUT/vifasttts"
if [ -n "${WEB_DIR:-}" ] && [ -d "$WEB_DIR" ]; then cp -R "$WEB_DIR" "$OUT/web"; fi
cp -L "$ORT_LIB" "$OUT/libonnxruntime.so"
cp "$MODEL_DIR/acoustic.onnx" "$OUT/models/acoustic.onnx"
cp "$MODEL_DIR/vocoder.onnx" "$OUT/models/vocoder.onnx"
cat > "$OUT/run.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec ./vifasttts-desktop "$@"
SH
chmod +x "$OUT/vifasttts-desktop" "$OUT/vifasttts" "$OUT/run.sh"
cat > "$OUT/README.txt" <<'TXT'
ViFastTts Desktop + server + TUI (Linux x64)
Chạy GUI: ./run.sh
TUI: ./vifasttts
Server + web: ./vifasttts server --acoustic models/acoustic.onnx --vocoder models/vocoder.onnx --port 8000
CLI: ./vifasttts synth --text "..." --output out.wav
Kiểm tra headless: ./vifasttts-desktop --smoke
Model: models/acoustic.onnx + models/vocoder.onnx
ORT: libonnxruntime.so (1.31.1, load-dynamic)
TXT

mkdir -p "$(dirname "$ARCHIVE")"
tar -czf "$ARCHIVE" -C "$OUT" .
echo "ARCHIVE: $ARCHIVE"
echo "DIR: $OUT"
