#!/usr/bin/env bash
# Tải 3 mẫu nghe thử N0 từ HuggingFace vào static VPS.
# Không commit WAV; script này tái tạo thư mục samples.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/deploy/vifasttts_demo/static/samples"
BASE="${DEMO_SAMPLES_URL:-https://huggingface.co/dvchd/vifasttts-ngochuyen-small/resolve/main/demo}"

if [ -f "$DEST/fresh01.wav" ] && [ -f "$DEST/fresh02.wav" ] && [ -f "$DEST/fresh04.wav" ]; then
  echo "Mẫu nghe thử đã có: $DEST"
  exit 0
fi
command -v curl >/dev/null || { echo "Cần curl"; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
echo "Tải mẫu nghe thử N0 từ HuggingFace…"
for name in fresh01.wav fresh02.wav fresh04.wav; do
  curl -L --fail --retry 3 "$BASE/$name" -o "$TMP/$name"
done
if command -v shasum >/dev/null; then
  (cd "$TMP" && printf '%s  fresh01.wav\n%s  fresh02.wav\n%s  fresh04.wav\n' \
    "8efaf28b215398bcfb33cac7886b1ffd369a46fd1584b7ecc26f2639616b19ad" \
    "b2a7121d98cfeead4eb3fb0107eb8f80d7907b11786957635b91584ab7fdc458" \
    "8289d5d593330c8a287ca3db1d128a1cf13b6dcfee288e1578c2ac6578360cfd" \
    | shasum -a 256 -c -)
else
  (cd "$TMP" && printf '%s  fresh01.wav\n%s  fresh02.wav\n%s  fresh04.wav\n' \
    "8efaf28b215398bcfb33cac7886b1ffd369a46fd1584b7ecc26f2639616b19ad" \
    "b2a7121d98cfeead4eb3fb0107eb8f80d7907b11786957635b91584ab7fdc458" \
    "8289d5d593330c8a287ca3db1d128a1cf13b6dcfee288e1578c2ac6578360cfd" \
    | sha256sum -c -)
fi
mkdir -p "$DEST"
cp "$TMP"/fresh0*.wav "$DEST/"
echo "Đã cài: $DEST/fresh01.wav · fresh02.wav · fresh04.wav"
