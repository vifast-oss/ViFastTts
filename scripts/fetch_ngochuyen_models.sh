#!/usr/bin/env bash
# Tải ONNX FP32 N0 Q-init (acoustic + Vocos) từ HuggingFace, có kiểm sha256.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/artifacts/onnx/n0_q"
BASE="https://huggingface.co/dvchd/vifasttts-ngochuyen-small/resolve/main/onnx"
ACOUSTIC_SHA="df61599a15984dccbf61c37d616258d22fc1af79abc681926e74142de7a376a3"
VOCODER_SHA="b3eb09cf5c3baac334b1c0bbea070d02e33e55572e3755865b986cd05cf6b03f"

if [ -f "$DEST/acoustic.onnx" ] && [ -f "$DEST/vocoder.onnx" ]; then
  echo "ONNX đã có: $DEST"
  exit 0
fi
command -v curl >/dev/null || { echo "Cần curl"; exit 1; }
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$DEST"
echo "Tải ONNX N0 Q-init từ HuggingFace…"
curl -L --fail --retry 3 "$BASE/acoustic.onnx" -o "$TMP/acoustic.onnx"
curl -L --fail --retry 3 "$BASE/vocoder.onnx" -o "$TMP/vocoder.onnx"
if command -v shasum >/dev/null; then
  (cd "$TMP" && printf '%s  acoustic.onnx\n%s  vocoder.onnx\n' "$ACOUSTIC_SHA" "$VOCODER_SHA" | shasum -a 256 -c -)
else
  (cd "$TMP" && printf '%s  acoustic.onnx\n%s  vocoder.onnx\n' "$ACOUSTIC_SHA" "$VOCODER_SHA" | sha256sum -c -)
fi
cp "$TMP/acoustic.onnx" "$TMP/vocoder.onnx" "$DEST/"
echo "Đã cài: $DEST/acoustic.onnx · $DEST/vocoder.onnx"
