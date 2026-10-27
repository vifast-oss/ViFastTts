#!/usr/bin/env bash
# Tải ONNX FP32 N0 (acoustic + Vocos) từ GitHub release, có kiểm sha256.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/artifacts/onnx/n0"
URL="https://github.com/dvchd/ViFastTts/releases/download/n0-ngochuyen-prod-v1/n0_onnx_fp32_q.zip"
SHA="ef35567c4433cf823db78ef90f716a259d14c79d62bed53e621f93b5231a01ed"

if [ -f "$DEST/acoustic.onnx" ] && [ -f "$DEST/vocoder.onnx" ]; then
  echo "ONNX đã có: $DEST"
  exit 0
fi
command -v curl >/dev/null || { echo "Cần curl"; exit 1; }
command -v unzip >/dev/null || { echo "Cần unzip"; exit 1; }
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
echo "Tải ONNX N0…"
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
