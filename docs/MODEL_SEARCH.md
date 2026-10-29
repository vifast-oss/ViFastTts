# Tìm và tải model `.vfa` / `.vfts`

Mọi UI dùng **cùng một catalog** và **chỉ tải bundle**:

- native (CLI/desktop/TUI/server): crate `vifasttts-model-manager` →
  `vifasttts-huggingface`.
- web/extension: module chung `web/shared/model-api.js` (extension copy qua
  `extension/build.sh`).
- Android/iOS: mặc định gọi HuggingFace **trực tiếp** khi Server URL trống;
  nhập URL server LAN thì dùng `/api/models/*` (proxy/kiểm hash).
- Server: `vifasttts-model-manager` kiểm manifest/hash trước khi trả file.

**Desktop/CLI/TUI/Android/iOS tìm HuggingFace trực tiếp**, không cần server.
Extension và web chạy qua server dùng `/api/models/*`; nếu dùng server cho mobile
thì nhập IP LAN (không dùng `127.0.0.1`).

Raw `acoustic.onnx`/`vocoder.onnx` là file nội bộ/dev, không hiện trong catalog
người dùng.

## Bảng hỗ trợ

| UI | Tìm HF | Tải `.vfa/.vfts` | Nạp local |
|---|---|---|---|
| CLI | ✅ `vifasttts models search` | ✅ `models download` | ✅ `synth --vfa/--vfts` |
| Desktop | ✅ model browser | ✅ tự kiểm hash | ✅ nút model |
| TUI | ✅ `Ctrl+O` | ✅ chọn repo/file | ✅ tự reload engine |
| Web (server) | ✅ mục HuggingFace | ✅ qua `/api/models/download` | ✅ ORT Web |
| Web (static) | — | ✅ input file | ✅ ORT Web |
| Extension | ✅ Cài đặt → HuggingFace | ✅ cache + active bundle | ✅ ORT Web |
| Android | ✅ nút Tải model (trực tiếp nếu URL trống) | ✅ lưu `filesDir/models` | ✅ FFI `.vfa/.vfts` |
| iOS | ✅ sheet Model (trực tiếp nếu URL trống) | ✅ Application Support | ✅ FFI `.vfa/.vfts` + remote HTTP (simulator đã chạy) |

## Desktop

Mở app → **Thêm giọng từ HuggingFace**:

1. Nhập từ khóa (mặc định `vifasttts`).
2. Bấm **Tìm**.
3. Chọn repo.
4. Danh sách chỉ hiện file `.vfa` / `.vfts`.
5. Bấm file để tải; `ModelManager` kiểm manifest/hash trước khi lưu.
6. `.vfa` dùng vocoder bundled; `.vfts` tự chứa vocoder.

Thư mục tải mặc định (cùng tên `vifasttts`, base dir theo OS):

```text
macOS:   ~/Library/Application Support/vifasttts/models/
Linux:   ~/.local/share/vifasttts/models/
Windows: %APPDATA%\vifasttts\data\models\
```

Settings: `desktop.json` trong config dir (`~/.config/vifasttts/` · `%APPDATA%\vifasttts\config\`).

## CLI

```bash
# tìm repo
vifasttts models search --query vifasttts

# xem .vfa/.vfts trong repo
vifasttts models files dvchd/vifasttts-ngochuyen-small

# tải bundle (kiểm manifest/hash)
vifasttts models download \
  dvchd/vifasttts-ngochuyen-small \
  bundles/n0-ngochuyen.vfa \
  --output models

# liệt kê bundle đã tải
vifasttts models installed --directory models
```

- Public repo không cần token.
- Private repo: `export HF_TOKEN=...`.
- Chỉ tải file kết thúc `.vfa`/`.vfts`.
- Giới hạn tải 512 MB.

## TUI

Trong `vifasttts` (không tham số):

```text
Ctrl+O  mở model browser
Enter   tìm / xem file / tải file đang chọn
↑ ↓     chọn repo hoặc file
Esc     đóng
```

Sau khi tải, TUI gọi `LocalCommand::Reload` để thay engine đang chạy, không cần
thoát. `.vfa` dùng `--vocoder` hiện tại; `.vfts` tự chứa vocoder.

## Web

Khi web được server phục vụ (`vifasttts server --web-dir web/dist`):

1. Mở **Thêm giọng từ HuggingFace (qua server)**.
2. Nhập từ khóa → **Tìm**.
3. Chọn repo → chọn `.vfa/.vfts`.
4. Web tải qua `/api/models/download`, kiểm SHA256, tạo ORT Web session.

Web tĩnh (mở file/không có server) vẫn nạp bundle thủ công bằng input
`.vfa/.vfts`; `.vfa` cần `/models/vocoder.onnx`, `.vfts` tự chứa vocoder.

## Extension

Popup → **Cài đặt** → **Thêm giọng từ HuggingFace (qua server)**:

1. Nhập Server URL + token (nếu server đặt token).
2. Tìm repo, chọn file.
3. Bundle lưu trong Cache Storage (`vifasttts-models-v1`) và được đặt làm
   active bundle; lần đọc local tiếp theo nạp acoustic/vocoder từ bundle.
4. **Bỏ bundle** hoặc **Xoá cache model** quay về model bundled/Model base URL.

Extension không gọi HuggingFace trực tiếp; server là proxy đã kiểm hash, tránh
CORS và tránh tải file raw.

## Android

Nút **Tải model .vfa/.vfts**:

- để trống Server URL → tải trực tiếp HuggingFace; nhập URL → qua server;
- tìm repo → chọn file → tải vào `filesDir/models/`;
- lưu active model trong `SharedPreferences`;
- lần đọc local sau dùng FFI:
  - `.vfts` → `vifasttts_engine_new_vfts`
  - `.vfa` → `vifasttts_engine_new_vfa` với `vocoder.onnx` bundled.

Remote mode vẫn dùng `/api/tts`, không cần model local.

## iOS

Sheet **Model** trong app:

- để trống Server URL → tải trực tiếp HuggingFace; nhập URL → qua server;
- tìm repo, chọn file;
- lưu vào Application Support, gọi `TtsEngine.loadModel`;
- `.vfts/.vfa` nạp qua C ABI; `.vfa` dùng vocoder bundled.

App iOS đã chạy simulator với cả **Local FFI** và **Remote `/api/tts`**; remote
dùng Server URL/token trong UI. Thiết bị thật chưa test vì cần ký Apple Developer.

## Server API

```text
GET /api/models/search?q=vifasttts&limit=20
GET /api/models/files?repo=dvchd/vifasttts-ngochuyen-small
GET /api/models/download?repo=...&path=voices/n0.vfa
```

- Cùng token với `/api/tts` nếu server chạy `--token`.
- CORS bật bằng `--cors` khi web/extension khác origin.
- `download` tải qua HuggingFace, lưu cache `--model-dir` (mặc định
  `models/`), kiểm manifest/hash rồi trả bytes; không trả raw ONNX.
- Các UI remote dùng chung endpoint này nên không lặp logic kiểm bundle.

## Tìm bằng tay trên web

```text
https://huggingface.co/api/models?search=vifasttts&limit=20&full=true
https://huggingface.co/api/models/<repo>/tree/main?recursive=true
https://huggingface.co/<repo>/resolve/main/<path>
```

## Lưu ý

- Repo hiện tại có thể chỉ có `onnx/acoustic.onnx`; UI sẽ báo chưa có bundle.
  Cần upload `.vfa`/`.vfts` (xem `docs/MODEL_DISTRIBUTION.md`).
- `.vfa` chỉ chạy nếu vocoder hash khớp; app/package N0 có Vocos pretrained.
- `.vfts` là lựa chọn an toàn khi chia sẻ cho người khác.
- License CC-BY-NC; kiểm tra trước khi tải.
