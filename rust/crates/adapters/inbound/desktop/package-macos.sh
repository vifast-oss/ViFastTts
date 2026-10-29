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

WEB_DIR="${WEB_DIR:-}"
if [ -z "$WEB_DIR" ] && [ -d "$ROOT/web/dist" ]; then WEB_DIR="$ROOT/web/dist"; fi
if [ -n "$WEB_DIR" ] && [ "${WEB_DIR#/}" = "$WEB_DIR" ]; then WEB_DIR="$ROOT/$WEB_DIR"; fi
if [ -n "$WEB_DIR" ] && [ ! -d "$WEB_DIR" ]; then
  echo "Thiếu web dir: $WEB_DIR" >&2
  exit 2
fi

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
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/licenses"
cp "$ROOT/rust/target/release/vifasttts-desktop" "$APP/Contents/MacOS/vifasttts-desktop"
cp "$ROOT/rust/target/release/vifasttts" "$APP/Contents/MacOS/vifasttts"
if [ -n "${WEB_DIR:-}" ] && [ -d "$WEB_DIR" ]; then
  cp -R "$WEB_DIR" "$APP/Contents/MacOS/web"
  # Model đã nằm trong Resources; server phục vụ /models/*, không copy trùng.
  rm -rf "$APP/Contents/MacOS/web/models"
fi
cp "$ORT_LIB" "$APP/Contents/MacOS/libonnxruntime.dylib"
cp "$MODEL_DIR/acoustic.onnx" "$APP/Contents/Resources/acoustic.onnx"
cp "$MODEL_DIR/vocoder.onnx" "$APP/Contents/Resources/vocoder.onnx"
cp "$ROOT/resources/fonts/BeVietnamPro-OFL.txt" "$APP/Contents/Resources/licenses/"
# App icon từ brand dùng chung (512 → iconset/.icns).
ICONSET="$CACHE/AppIcon.iconset"
rm -rf "$ICONSET"
mkdir -p "$ICONSET"
for pair in 16:icon_16x16 32:icon_16x16@2x 32:icon_32x32 64:icon_32x32@2x 128:icon_128x128 256:icon_128x128@2x 256:icon_256x256 512:icon_256x256@2x 512:icon_512x512 1024:icon_512x512@2x; do
  size="${pair%%:*}"; name="${pair##*:}"
  sips -z "$size" "$size" "$ROOT/resources/brand/vifasttts-icon-512.png" --out "$ICONSET/$name.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"
rm -rf "$ICONSET"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key><string>vifasttts-desktop</string>
  <key>CFBundleIdentifier</key><string>com.vifasttts.desktop</string>
  <key>CFBundleName</key><string>ViFastTts</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundleDisplayName</key><string>ViFastTts</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.3.4</string>
  <key>CFBundleVersion</key><string>8</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

chmod +x "$APP/Contents/MacOS/vifasttts-desktop" "$APP/Contents/MacOS/vifasttts"
if command -v codesign >/dev/null; then
  codesign --force --deep --sign - "$APP" >/dev/null
fi

echo "APP: $APP"
ARCHIVE="$ROOT/desktop/dist/vifasttts-desktop-macos-$(uname -m).zip"
mkdir -p "$(dirname "$ARCHIVE")"
rm -f "$ARCHIVE"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ARCHIVE"
echo "ARCHIVE: $ARCHIVE"
if [ "${1:-}" = "--run" ]; then
  open "$APP"
fi
