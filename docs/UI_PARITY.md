# UI parity — trạng thái tính năng

Cập nhật: 30/10/2026. Mục tiêu: mọi UI đều có cùng bộ tính năng TTS cơ bản và
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
| Web Python (server) | Remote | Model server cố định | Speed/alpha/fixed/peak/max/dialect + `/api/config` defaults | WAV/SRT/VTT; **stream NDJSON + WebAudio** | Engine Python `OnnxTtsEngine`; stream toggle |
| Web Vite | Có | HF trực tiếp hoặc server, file `.vfa/.vfts` | Đầy đủ | Có, WAV/SRT/VTT | Chạy được trong trình duyệt |
| Chrome extension | Có | HF trực tiếp hoặc server, bundled | Đầy đủ | Có, WAV/SRT/VTT | Thêm stream/history/ETA |
| Android | Có | Bundled ONNX, `.vfa/.vfts`, ONNX pair, HF trực tiếp/server | Đầy đủ + custom reading + auto-play + output folder + stream local/remote + history/ETA + share + health + huỷ tải model | Karaoke; WAV/SRT/VTT/JSON; stream có WAV + phụ đề (tùy chọn lưu) | Câu mặc định có chữ “Android”; sample/ETA/từ điển/catalog dùng contract Rust |
| iOS | Có | HF trực tiếp/server, bundle; progress tải model | Đầy đủ + history/ETA | Karaoke; ShareLink WAV/SRT/VTT/JSON; stream local/remote có toggle lưu | Câu mặc định có chữ “iOS”; sample/ETA/catalog qua contract Rust |

## Android — kiểm tra parity (29/10)

**Đã có:** local/remote, model bundled ONNX, danh sách `.vfa/.vfts` đã cài, tải
HuggingFace trực tiếp/server, chọn file bundle, chọn cặp `acoustic.onnx` +
`vocoder.onnx`; speed/alpha/pause/peak/max/dialect/OOV/từ điển + custom reading;
auto-play; chọn thư mục xuất; stream local/remote; history + ETA; share WAV +
SRT/VTT/JSON; kiểm tra `/healthz`; tiến trình tải, đổi tên và xoá model; karaoke;
WAV/SRT/VTT/JSON; stream có thể lưu WAV + phụ đề nếu bật; audio focus.

**Chưa có / còn kiểm:**

1. Metadata/hash model trên UI (hiện tên + size).
2. Auto-play chỉ áp dụng cho full; stream luôn phát ngay, và có toggle riêng
   “Lưu WAV + phụ đề khi stream” (mặc định bật).
3. Chọn thư mục xuất phụ thuộc Storage Access Framework; Android 11 không cho
   chọn thẳng root `Download`, cần chọn/tạo thư mục con.
4. Test thiết bị thật: emulator vẫn log lỗi HAL audio; chưa kết luận chất lượng.
5. iOS đã có stream local/remote + progress tải model; vẫn cần test máy thật.

Phần dùng chung đã tách (settings/sample/ETA/từ điển) nằm ở
`docs/UI_REUSE_AUDIT.md`.

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
