#!/usr/bin/env bash
# Tải ONNX FP32 N0 Q-init (acoustic + Vocos) từ GitHub release, có kiểm sha256.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/artifacts/onnx/n0_q"
URL="https://github.com/dvchd/ViFastTts/releases/download/n0-ngochuyen-prod-v1/n0_onnx_fp32.zip"
SHA="c613b1206cb8b57140d9429564da71c969c71b2491ae4d0da87becc2c89ba98a"

if [ -f "$DEST/acoustic.onnx" ] && [ -f "$DEST/vocoder.onnx" ]; then
  echo "ONNX đã có: $DEST"
  exit 0
fi
command -v curl >/dev/null || { echo "Cần curl"; exit 1; }
command -v unzip >/dev/null || { echo "Cần unzip"; exit 1; }
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
echo "Tải ONNX N0 Q-init…"
curl -L --fail --retry 3 "$URL" -o "$TMP/n0_onnx_fp32.zip"
if command -v shasum >/dev/null; then
  echo "$SHA  $TMP/n0_onnx_fp32.zip" | shasum -a 256 -c -
else
  echo "$SHA  $TMP/n0_onnx_fp32.zip" | sha256sum -c -
fi
unzip -q "$TMP/n0_onnx_fp32.zip" -d "$TMP"
mkdir -p "$DEST"
cp "$TMP"/n0_onnx_fp32/acoustic.onnx "$TMP"/n0_onnx_fp32/vocoder.onnx "$DEST/"
echo "Đã cài: $DEST/acoustic.onnx · $DEST/vocoder.onnx"
