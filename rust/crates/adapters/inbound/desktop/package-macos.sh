#!/usr/bin/env bash
# Đóng gói .app macOS cho desktop app (không ký notarize).
# Dùng: package-macos.sh [--run]
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../../../.." && pwd)"
APP="$ROOT/desktop/dist/ViFastTts.app"
MODEL_DIR="${MODEL_DIR:-$ROOT/artifacts/onnx/n0_q}"
ORT_LIB="${ORT_LIB:-$ROOT/rust/lib/libonnxruntime.dylib}"
ORT_VERSION="${ORT_VERSION:-1.31.1}"
CACHE="${CACHE:-$ROOT/desktop/dist/cache}"

[ -f "$MODEL_DIR/acoustic.onnx" ] || { echo "Thiếu $MODEL_DIR/acoustic.onnx" >&2; exit 2; }
[ -f "$MODEL_DIR/vocoder.onnx" ] || { echo "Thiếu $MODEL_DIR/vocoder.onnx" >&2; exit 2; }

if [ ! -f "$ORT_LIB" ]; then
  arch="$(uname -m)"
  case "$arch" in
    arm64) ort_arch="arm64" ;;
    x86_64) ort_arch="x64" ;;
    *) echo "Kiến trúc macOS không hỗ trợ: $arch" >&2; exit 2 ;;
  esac
  mkdir -p "$CACHE"
  archive="$CACHE/onnxruntime-osx-$ort_arch-$ORT_VERSION.tgz"
  if [ ! -f "$archive" ]; then
    curl -L --fail -o "$archive" \
      "https://github.com/microsoft/onnxruntime/releases/download/v$ORT_VERSION/onnxruntime-osx-$ort_arch-$ORT_VERSION.tgz"
  fi
  rm -rf "$CACHE/onnxruntime-osx-$ort_arch-$ORT_VERSION"
  tar -xzf "$archive" -C "$CACHE"
  ORT_LIB="$CACHE/onnxruntime-osx-$ort_arch-$ORT_VERSION/lib/libonnxruntime.dylib"
fi
[ -f "$ORT_LIB" ] || { echo "Thiếu ORT: $ORT_LIB" >&2; exit 2; }

cd "$ROOT/rust"
cargo build --release -p vifasttts-desktop -p vifasttts-cli

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$ROOT/rust/target/release/vifasttts-desktop" "$APP/Contents/MacOS/vifasttts-desktop"
cp "$ROOT/rust/target/release/vifasttts-rs" "$APP/Contents/MacOS/vifasttts-rs"
ln -sf vifasttts-rs "$APP/Contents/MacOS/vifasttts"
ln -sf vifasttts-rs "$APP/Contents/MacOS/vtfs"
if [ -n "${WEB_DIR:-}" ] && [ -d "$WEB_DIR" ]; then cp -R "$WEB_DIR" "$APP/Contents/MacOS/web"; fi
cp "$ORT_LIB" "$APP/Contents/MacOS/libonnxruntime.dylib"
cp "$MODEL_DIR/acoustic.onnx" "$APP/Contents/Resources/acoustic.onnx"
cp "$MODEL_DIR/vocoder.onnx" "$APP/Contents/Resources/vocoder.onnx"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key><string>vifasttts-desktop</string>
  <key>CFBundleIdentifier</key><string>com.vifasttts.desktop</string>
  <key>CFBundleName</key><string>ViFastTts</string>
  <key>CFBundleDisplayName</key><string>ViFastTts</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.1.0</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

chmod +x "$APP/Contents/MacOS/vifasttts-desktop" "$APP/Contents/MacOS/vifasttts-rs"
if command -v codesign >/dev/null; then
  codesign --force --deep --sign - "$APP" >/dev/null
fi

echo "APP: $APP"
ARCHIVE="$ROOT/desktop/dist/ViFastTts-macos-$(uname -m).zip"
mkdir -p "$(dirname "$ARCHIVE")"
rm -f "$ARCHIVE"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ARCHIVE"
echo "ARCHIVE: $ARCHIVE"
if [ "${1:-}" = "--run" ]; then
  open "$APP"
fi
