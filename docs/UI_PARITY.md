# UI parity — trạng thái tính năng

Cập nhật: 29/10/2026. Mục tiêu: mọi UI đều có cùng bộ tính năng TTS cơ bản và
không lặp lại tình trạng Android/iOS chỉ có “Đọc / Dừng”.

## Bộ tính năng chuẩn

- Nhập text, đếm ký tự, đọc câu dài (chia chunk).
- Local / Remote.
- Chọn model: bundled, `.vfa/.vfts`, HuggingFace (server hoặc trực tiếp).
- Phát / dừng, trạng thái và lỗi rõ ràng.
- Tốc độ 0,5–2,0×; alpha 0,5–3,0; pause cố định; peak normalize; max ký tự/chunk.
- Phương ngữ Bắc/Trung/Nam; resolve OOV; từ điển `key = cách đọc`.
- Karaoke/timing; xuất WAV, SRT, VTT (nơi có timing).
- Model browser và cấu hình được lưu lại.

## Ma trận UI

| UI | Local/Remote | Model | Cấu hình | Karaoke / phụ đề | Ghi chú |
|---|---|---|---|---|---|
| Desktop egui | Có | ONNX, bundle, HF trực tiếp | Đầy đủ + auto-play + history/ETA | Có, lưu SRT/VTT | Bản đầy đủ nhất |
| CLI | Có | `--vfa/--vfts`, HF | Đầy đủ qua flags | WAV/SRT/VTT/JSON | Dùng script/terminal |
| TUI | Có | `Ctrl+O`, HF | Speed/alpha/max/dialect/OOV/dictionary file | WAV/SRT/VTT | `Ctrl+P` cấu hình; dictionary qua `--dictionary` |
| Web Python (server) | Remote | Model server cố định | Speed/alpha/fixed/peak/max/dialect | WAV/SRT/VTT | Demo server, không có local WASM |
| Web Vite | Có | HF trực tiếp hoặc server, file `.vfa/.vfts` | Đầy đủ | Có, WAV/SRT/VTT | Chạy được trong trình duyệt |
| Chrome extension | Có | HF trực tiếp hoặc server, bundled | Đầy đủ | Có, WAV/SRT/VTT | Thêm stream/history/ETA |
| Android | Có | Bundled ONNX, `.vfa/.vfts`, ONNX pair, HF trực tiếp/server | Đầy đủ + stream local | Karaoke trên màn hình; WAV/SRT/VTT/JSON vào Downloads | Câu mặc định có chữ “Android” |
| iOS | Có | HF trực tiếp/server, bundle | Đầy đủ | Karaoke trên màn hình; ShareLink WAV/SRT/VTT/JSON | Câu mặc định có chữ “iOS” |

## Android — kiểm tra parity (29/10)

**Đã có:** local/remote, model bundled ONNX, danh sách `.vfa/.vfts` đã cài, tải
HuggingFace trực tiếp/server, chọn file bundle, chọn cặp `acoustic.onnx` +
`vocoder.onnx`; speed/alpha/pause/peak/max/dialect/OOV/từ điển; stream local;
karaoke; WAV/SRT/VTT/JSON vào Downloads; audio focus.

**Chưa có so với desktop/extension:**

1. History + ETA.
2. Share sheet (hiện chỉ lưu Downloads; iOS có ShareLink).
3. Custom reading token-level (Android chỉ có dictionary `key = cách đọc`).
4. Nút kiểm tra server (`/healthz`).
5. Đếm ký tự + toggle auto-play (Android luôn tự phát).
6. Tiến trình/huỷ tải model, xoá/đổi tên model, metadata model.
7. Chọn thư mục xuất.
8. Stream chưa lưu WAV/SRT; remote stream mới thêm, cần test end-to-end.

## Cách đọc tên sản phẩm

Đã chốt trong `overrides_vi.json` (Rust + Python demo):

```json
"ios": "ai âu ét",
"android": "an đờ roi"
```

- `iOS` đọc theo hướng tiếng Anh `/aɪ.oʊˈɛs/`, không còn `ai ốt ét`.
- `Android` đọc tự nhiên `/ˈændrɔɪd/`; không dùng `an đờ rô ít`.
- Có test hồi quy trong `rust/crates/core/domain/text/src/pipeline.rs`.

## Các điểm còn cần kiểm trên máy thật

1. **Android audio thật**: đã thêm AudioFocus/AudioAttributes và karaoke; emulator
   chạy được, nhưng chưa xác nhận hết giật trên thiết bị thật.
2. **iOS thiết bị thật**: simulator đã chạy local/remote + phụ đề; ký Apple
   Developer và framework device vẫn là bước riêng.
3. **Chrome/Edge store**: extension đã có host permission cho HuggingFace trực
   tiếp; cần chụp ảnh 1280×800 và nộp store.
4. **TUI**: dictionary hiện nhập qua file `--dictionary`; chưa có editor văn bản
   trong terminal (không chặn dùng).

## Lệnh kiểm tra nhanh

```bash
# Rust
cd rust
cargo test -p vifasttts-text -p vifasttts-http-server -p vifasttts-ffi -p vifasttts-tui

# Python
.venv/bin/ruff check .
.venv/bin/python -m pytest -q

# Web + extension
./web/build.sh && (cd web && npm run build)
./extension/build.sh

# Mobile
JAVA_HOME="$(/usr/libexec/java_home -v 21)" ./mobile/android/build.sh
ONNXRUNTIME_XCFRAMEWORK=/private/tmp/opencode/ios-ort/onnxruntime.xcframework ./mobile/ios/build-ios.sh
```
