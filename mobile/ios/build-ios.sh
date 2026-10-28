#!/usr/bin/env bash
# Build iOS simulator với Rust staticlib + ORT iOS.
# Cần Xcode đầy đủ (không chỉ Command Line Tools) và ORT iOS .a/.xcframework.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
FFI_DIR="$HERE/ViFastTtsFFI"
MODEL_DIR="${MODEL_DIR:-$ROOT/artifacts/onnx/n0_q}"
SIM_TARGET="${SIM_TARGET:-aarch64-apple-ios-sim}"
SIM_LIB="${ONNXRUNTIME_SIM_LIB:-${ONNXRUNTIME_LIB:-}}"
DEVICE_LIB="${ONNXRUNTIME_DEVICE_LIB:-${ONNXRUNTIME_LIB:-}}"

command -v xcodebuild >/dev/null || { echo "Thiếu xcodebuild" >&2; exit 2; }
if ! xcodebuild -version >/dev/null 2>&1; then
  echo "Cần Xcode đầy đủ, không chỉ Command Line Tools: xcode-select --install chỉ có macOS SDK." >&2
  echo "Cài Xcode từ App Store/Apple Developer rồi chạy: sudo xcode-select -s /Applications/Xcode.app" >&2
  exit 2
fi
[ -f "$MODEL_DIR/acoustic.onnx" ] || { echo "Thiếu model $MODEL_DIR" >&2; exit 2; }
[ -n "$SIM_LIB" ] && [ -f "$SIM_LIB" ] || {
  echo "Thiếu ORT iOS static lib cho simulator; đặt ONNXRUNTIME_SIM_LIB." >&2
  echo "ORT iOS lấy từ onnxruntime-c/onnxruntime.xcframework (đúng bản 1.31.1)." >&2
  exit 2
}

rustup target add "$SIM_TARGET" aarch64-apple-ios >/dev/null 2>&1 || true
(cd "$ROOT/rust" && cargo build --release -p vifasttts-ffi --target "$SIM_TARGET")
(cd "$ROOT/rust" && cargo build --release -p vifasttts-ffi --target aarch64-apple-ios)

mkdir -p "$FFI_DIR/lib" "$HERE/Resources"
cp "$ROOT/rust/target/$SIM_TARGET/release/libvifasttts_ffi.a" "$FFI_DIR/lib/libvifasttts_ffi.a"
cp "$SIM_LIB" "$FFI_DIR/lib/libonnxruntime.a"
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
  -configuration Debug \
  build \
  CODE_SIGNING_ALLOWED=NO

echo "Build xong. Mở Xcode: open $HERE/ViFastTtsMobile.xcodeproj"
echo "Thiết bị thật cần thêm libonnxruntime thiết bị + ký Apple Developer."
