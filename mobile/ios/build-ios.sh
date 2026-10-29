#!/usr/bin/env bash
# Build iOS simulator với Rust staticlib + ORT iOS.
# Cần Xcode đầy đủ (không chỉ Command Line Tools) và ORT iOS .a/.xcframework.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
FFI_DIR="$HERE/ViFastTtsFFI"
MODEL_DIR="${MODEL_DIR:-$ROOT/artifacts/onnx/n0_q}"
SIM_TARGET="${SIM_TARGET:-aarch64-apple-ios-sim}"
ORT_FRAMEWORK="${ONNXRUNTIME_FRAMEWORK:-}"
ORT_XCFRAMEWORK="${ONNXRUNTIME_XCFRAMEWORK:-}"

command -v xcodebuild >/dev/null || { echo "Thiếu xcodebuild" >&2; exit 2; }
if ! xcodebuild -version >/dev/null 2>&1; then
  echo "Cần Xcode đầy đủ, không chỉ Command Line Tools: xcode-select --install chỉ có macOS SDK." >&2
  echo "Cài Xcode từ App Store/Apple Developer rồi chạy: sudo xcode-select -s /Applications/Xcode.app" >&2
  exit 2
fi
[ -f "$MODEL_DIR/acoustic.onnx" ] || { echo "Thiếu model $MODEL_DIR" >&2; exit 2; }

# ORT iOS: nhận framework đã tách hoặc xcframework gốc (onnxruntime-c).
SIM_FRAMEWORK="$FFI_DIR/Frameworks/onnxruntime.framework"
rm -rf "$SIM_FRAMEWORK"
mkdir -p "$FFI_DIR/Frameworks"
if [ -n "$ORT_FRAMEWORK" ] && [ -d "$ORT_FRAMEWORK" ]; then
  cp -R "$ORT_FRAMEWORK" "$SIM_FRAMEWORK"
elif [ -n "$ORT_XCFRAMEWORK" ] && [ -d "$ORT_XCFRAMEWORK/ios-arm64_x86_64-simulator/onnxruntime.framework" ]; then
  cp -R "$ORT_XCFRAMEWORK/ios-arm64_x86_64-simulator/onnxruntime.framework" "$SIM_FRAMEWORK"
elif [ -n "$ORT_XCFRAMEWORK" ] && [ -d "$ORT_XCFRAMEWORK/onnxruntime.framework" ]; then
  cp -R "$ORT_XCFRAMEWORK/onnxruntime.framework" "$SIM_FRAMEWORK"
else
  echo "Thiếu ORT iOS framework; đặt ONNXRUNTIME_FRAMEWORK hoặc ONNXRUNTIME_XCFRAMEWORK." >&2
  echo "Ví dụ: ONNXRUNTIME_XCFRAMEWORK=/tmp/onnxruntime.xcframework (onnxruntime-c)." >&2
  exit 2
fi

rustup target add --toolchain 1.99.1 aarch64-apple-ios-sim aarch64-apple-ios >/dev/null 2>&1 || true
# ORT iOS là framework static: chỉ build staticlib, Xcode app link framework.
export ORT_IOS_XCFWK_PATH="${ORT_IOS_XCFWK_PATH:-$ORT_XCFRAMEWORK}"
(cd "$ROOT/rust" && cargo rustc --release -p vifasttts-ffi --target "$SIM_TARGET" --crate-type staticlib)
(cd "$ROOT/rust" && cargo rustc --release -p vifasttts-ffi --target aarch64-apple-ios --crate-type staticlib)

mkdir -p "$FFI_DIR/lib" "$HERE/Resources"
cp "$ROOT/rust/target/$SIM_TARGET/release/libvifasttts_ffi.a" "$FFI_DIR/lib/libvifasttts_ffi.a"
cp "$MODEL_DIR/acoustic.onnx" "$HERE/Resources/acoustic.onnx"
cp "$MODEL_DIR/vocoder.onnx" "$HERE/Resources/vocoder.onnx"

if command -v xcodegen >/dev/null; then
  (cd "$HERE" && xcodegen generate)
else
  echo "Thiếu xcodegen: brew install xcodegen" >&2
  exit 2
fi

xcodebuild \
  -project "$HERE/ViFastTtsMobile.xcodeproj" \
  -scheme ViFastTtsMobile \
  -sdk iphonesimulator \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath "$HERE/build" \
  -configuration Debug \
  ARCHS=arm64 ONLY_ACTIVE_ARCH=YES \
  build \
  CODE_SIGNING_ALLOWED=NO

APP="$HERE/build/Build/Products/Debug-iphonesimulator/ViFastTtsMobile.app"
[ -d "$APP" ] || { echo "Không thấy app: $APP" >&2; exit 1; }
ARCHIVE="$HERE/build/ViFastTtsMobile-ios-simulator.zip"
rm -f "$ARCHIVE"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ARCHIVE"
echo "APP: $APP"
echo "ARCHIVE: $ARCHIVE"
echo "Thiết bị thật cần framework device + ký Apple Developer."
