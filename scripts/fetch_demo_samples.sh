#!/usr/bin/env bash
# Tải 3 mẫu nghe thử N0 từ GitHub release vào static VPS.
# Không commit WAV (demo audio nằm ở release); script này tái tạo thư mục samples.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/deploy/vifasttts_demo/static/samples"
BASE="${DEMO_SAMPLES_URL:-https://github.com/dvchd/ViFastTts/releases/download/n0-demo-samples-v1}"

if [ -f "$DEST/fresh01.wav" ] && [ -f "$DEST/fresh02.wav" ] && [ -f "$DEST/fresh04.wav" ]; then
  echo "Mẫu nghe thử đã có: $DEST"
  exit 0
fi
command -v curl >/dev/null || { echo "Cần curl"; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
echo "Tải mẫu nghe thử N0…"
curl -L --fail --retry 3 "$BASE/SHA256SUMS" -o "$TMP/SHA256SUMS"
for name in fresh01.wav fresh02.wav fresh04.wav; do
  curl -L --fail --retry 3 "$BASE/$name" -o "$TMP/$name"
done
if command -v shasum >/dev/null; then
  (cd "$TMP" && shasum -a 256 -c SHA256SUMS)
else
  (cd "$TMP" && sha256sum -c SHA256SUMS)
fi
mkdir -p "$DEST"
cp "$TMP"/fresh0*.wav "$DEST/"
echo "Đã cài: $DEST/fresh01.wav · fresh02.wav · fresh04.wav"
