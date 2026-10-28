#!/usr/bin/env bash
# Đóng gói server cho macOS/Linux (binary + ORT + model + run.sh).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
MODEL_DIR="${MODEL_DIR:-$ROOT/artifacts/onnx/n0_q}"
ORT_VERSION="${ORT_VERSION:-1.31.1}"
os="$(uname -s)"
arch="$(uname -m)"
case "$os/$arch" in
  Darwin/arm64) ort="osx-arm64"; out="macos-arm64" ;;
  Darwin/x86_64) ort="osx-x64"; out="macos-x64" ;;
  Linux/x86_64) ort="linux-x64"; out="linux-x64" ;;
  *) echo "Chưa hỗ trợ $os/$arch" >&2; exit 2 ;;
esac
[ -f "$MODEL_DIR/acoustic.onnx" ] || { echo "Thiếu model $MODEL_DIR" >&2; exit 2; }
CACHE="${CACHE:-$ROOT/desktop/dist/cache}"
OUT="${OUT:-$ROOT/desktop/dist/vifasttts-cli-$out}"
ARCHIVE="${ARCHIVE:-$ROOT/desktop/dist/vifasttts-cli-$out.tar.gz}"
(cd "$ROOT/rust" && cargo build --release -p vifasttts-cli)
mkdir -p "$CACHE"
archive="$CACHE/onnxruntime-$ort-$ORT_VERSION.tgz"
if [ ! -f "$archive" ]; then
  curl -L --fail -o "$archive" \
    "https://github.com/microsoft/onnxruntime/releases/download/v$ORT_VERSION/onnxruntime-$ort-$ORT_VERSION.tgz"
fi
rm -rf "$CACHE/onnxruntime-$ort-$ORT_VERSION"
tar -xzf "$archive" -C "$CACHE"
ortlib="$CACHE/onnxruntime-$ort-$ORT_VERSION/lib/libonnxruntime.dylib"
[ -f "$ortlib" ] || ortlib="$CACHE/onnxruntime-$ort-$ORT_VERSION/lib/libonnxruntime.so"
[ -f "$ortlib" ] || { echo "Không thấy ORT trong $CACHE" >&2; exit 2; }
rm -rf "$OUT"; mkdir -p "$OUT/models"
cp "$ROOT/rust/target/release/vifasttts" "$OUT/vifasttts"
cp -L "$ortlib" "$OUT/$(basename "$ortlib")"
cp "$MODEL_DIR/acoustic.onnx" "$OUT/models/acoustic.onnx"
cp "$MODEL_DIR/vocoder.onnx" "$OUT/models/vocoder.onnx"
if [ -n "${WEB_DIR:-}" ] && [ -d "$WEB_DIR" ]; then
  rm -rf "$OUT/web"
  cp -R "$WEB_DIR" "$OUT/web"
fi
cat > "$OUT/run.sh" <<'SH'
#!/usr/bin/env bash
cd "$(dirname "$0")"
args=(--acoustic models/acoustic.onnx --vocoder models/vocoder.onnx)
[ -d web ] && args+=(--web-dir web)
exec ./vifasttts server "${args[@]}" "$@"
SH
chmod +x "$OUT/vifasttts" "$OUT/run.sh"
cat > "$OUT/README.txt" <<'TXT'
ViFastTts CLI/TUI/server
Chạy server: ./run.sh --host 127.0.0.1 --port 8000
TUI/CLI: ./vifasttts
Model: models/acoustic.onnx + models/vocoder.onnx
ORT: 1.31.1 (load-dynamic, cùng thư mục)
Endpoints: /healthz, /api/config, /api/tts, /api/tts/stream
TXT
mkdir -p "$(dirname "$ARCHIVE")"
tar -czf "$ARCHIVE" -C "$OUT" .
echo "ARCHIVE: $ARCHIVE"
