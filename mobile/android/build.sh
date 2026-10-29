#!/usr/bin/env bash
# Build APK Android từ Rust C ABI + ORT Android + model ONNX.
# Chạy từ repo root hoặc bất kỳ đâu; mọi artifact local nằm trong mobile/android.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-/opt/homebrew/share/android-commandlinetools}}"
NDK="${ANDROID_NDK_HOME:-$SDK/ndk/28.2.13676358}"
MODEL_DIR="${MODEL_DIR:-$ROOT/artifacts/onnx/n0_q}"
ORT_VERSION="${ORT_VERSION:-1.31.1}"
ORT_AAR="${ORT_AAR:-$ROOT/artifacts/onnx/onnxruntime-android-$ORT_VERSION.aar}"

command -v cargo >/dev/null || { echo "Thiếu cargo" >&2; exit 2; }
command -v cargo-ndk >/dev/null || { echo "Thiếu cargo-ndk: cargo install cargo-ndk" >&2; exit 2; }
[ -d "$NDK" ] || { echo "Thiếu NDK: $NDK" >&2; exit 2; }
[ -f "$MODEL_DIR/acoustic.onnx" ] || { echo "Thiếu $MODEL_DIR/acoustic.onnx" >&2; exit 2; }
[ -f "$MODEL_DIR/vocoder.onnx" ] || { echo "Thiếu $MODEL_DIR/vocoder.onnx" >&2; exit 2; }

if [ ! -f "$ORT_AAR" ]; then
  mkdir -p "$(dirname "$ORT_AAR")"
  curl -L --fail -o "$ORT_AAR" \
    "https://repo1.maven.org/maven2/com/microsoft/onnxruntime/onnxruntime-android/$ORT_VERSION/onnxruntime-android-$ORT_VERSION.aar"
fi

export ANDROID_HOME="$SDK"
export ANDROID_SDK_ROOT="$SDK"
export ANDROID_NDK_HOME="$NDK"
export PATH="$SDK/platform-tools:$PATH"
# AGP 9.0 cần JDK 21; JDK 27 làm jlink/desugar lỗi.
if [ -z "${JAVA_HOME:-}" ] || ! "$JAVA_HOME/bin/java" -version 2>&1 | grep -q 'version "21'; then
  JAVA_HOME="$(/usr/libexec/java_home -v 21 2>/dev/null || true)"
fi
[ -n "${JAVA_HOME:-}" ] || { echo "Cần JDK 21 (đặt JAVA_HOME; macOS: brew install --cask temurin@21)" >&2; exit 2; }
export JAVA_HOME

APP="$ROOT/mobile/android/app/src/main"
mkdir -p "$APP/assets" "$APP/jniLibs/x86_64" "$APP/jniLibs/arm64-v8a"

# Rust cdylib cho hai ABI; cargo-ndk đặt đúng thư mục jniLibs/<abi>.
cd "$ROOT/rust"
cargo ndk -t x86_64 -t arm64-v8a -o "$APP/jniLibs" \
  build --release -p vifasttts-ffi

# ORT Android tách từ AAR; Rust dùng load-dynamic nên phải nằm cạnh cdylib.
for abi in x86_64 arm64-v8a; do
  unzip -p "$ORT_AAR" "jni/$abi/libonnxruntime.so" > "$APP/jniLibs/$abi/libonnxruntime.so"
done

cp "$MODEL_DIR/acoustic.onnx" "$APP/assets/acoustic.onnx"
cp "$MODEL_DIR/vocoder.onnx" "$APP/assets/vocoder.onnx"

cd "$ROOT/mobile/android"
if [ -x ./gradlew ]; then
  ./gradlew assembleDebug
else
  command -v gradle >/dev/null || { echo "Thiếu gradle hoặc gradlew" >&2; exit 2; }
  gradle assembleDebug --no-daemon
fi

APK="$ROOT/mobile/android/app/build/outputs/apk/debug/app-debug.apk"
mkdir -p "$ROOT/desktop/dist"
cp "$APK" "$ROOT/desktop/dist/vifasttts-mobile-android.apk"
echo "APK: $APK"
echo "Release APK: $ROOT/desktop/dist/vifasttts-mobile-android.apk"
echo "Cài: adb install -r app/build/outputs/apk/debug/app-debug.apk"
