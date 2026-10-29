# ViFastTts Chrome extension (MV3)

Extension đọc tiếng Việt **local-first**:

- `vifasttts-browser` — engine async + frontend/karaoke/iSTFT/WAV
- `vifasttts-ort-web` — async backend gọi ORT Web
- ORT Web WASM — chạy acoustic/vocoder
- `chrome.offscreen` — nơi có DOM/wasm, vì service worker không có DOM

## Build

Từ repo root:

```bash
./extension/build.sh
```

Script sẽ:

- build `vifasttts-browser` cho `wasm32-unknown-unknown`;
- chạy `wasm-bindgen --target web` vào `extension/vendor/pkg/`;
- copy ORT Web `.mjs` + `.wasm` vào `extension/vendor/ort/`;
- copy shared catalog `web/shared/{model-api,bundle}.js` vào `extension/shared/`;
- copy model từ `artifacts/onnx/n0_q/` vào `extension/models/` nếu có.

`extension/vendor/`, `extension/models/` không commit. Logo trong
`extension/icons/` được resize từ brand dùng chung `resources/brand/`
(cùng bộ với `deploy/vifasttts_demo/static/brand/`).

## Load extension

1. Mở `chrome://extensions`
2. Bật Developer mode
3. **Load unpacked** → chọn thư mục `extension/`

Trên Edge:

```text
edge://extensions → Developer mode → Load unpacked
```

Bản này **không dùng `ttsEngine`**, nên không có cảnh báo quyền đọc TTS.
Quyền chính: `offscreen`, `storage`, `contextMenus`, `activeTab`, `scripting`.

## Cách dùng

### Popup

Bấm icon ViFastTts:

- nhập text và bấm **Đọc**;
- **Đọc trang** — lấy text từ `article/main/body` của tab hiện tại và đọc;
- chỉnh tốc độ, đọc đều, local/remote, server URL, token, model base URL;
- **Cài đặt → Thêm giọng từ HuggingFace**: tìm/tải `.vfa`/`.vfts` qua server
  dùng chung `/api/models/*`; bundle lưu vào Cache Storage và tự dùng cho local;
- xem karaoke, tải SRT/WebVTT.

### Context menu khi bôi đen

Chuột phải → **ViFastTts**:

- **Đọc đoạn bôi đen (theo cài đặt)** — dùng lựa chọn trong Cài đặt;
- **Đọc ẩn** — synth + phát audio, không mở tab, badge `…/▶/!`;
- **Đọc trong popup** — mở action popup với text đã chọn;
- **Mở tab đọc** — mở tab có UI/karaoke.

Chuột phải trên trang → **Đọc toàn bộ trang bằng ViFastTts**.
Text được lấy từ `article`, `main`, `[role=main]` hoặc `body`, tối đa 50.000 ký tự.

### Cài đặt bôi đen

Trong popup → **Cài đặt** → **Khi bôi đen**:

| Giá trị | Hành vi |
|---|---|
| `Đọc ẩn` | synth + phát audio, không mở tab |
| `Mở popup đọc` | mở popup với text đã chọn |
| `Mở tab mới đọc` | mở tab reader |

## Stream

Popup có checkbox **stream**:

- local: engine streaming PCM, offscreen phát bằng Web Audio;
- remote: đọc NDJSON `/api/tts/stream`;
- karaoke unit được gửi về popup trong lúc đang đọc;
- nút **Dừng** huỷ stream;
- stream không tạo file WAV trong popup;
- text > 1500 ký tự tự dùng stream kể cả khi checkbox tắt.

## Ước lượng thời gian

Background lưu tối đa 20 lần chạy gần nhất vào
`chrome.storage.local["vifasttts_history_v1"]`:

```text
{mode, chars, elapsed_ms, audio_seconds, at}
```

Lần chạy sau hiện ước tính theo median `elapsed_ms / chars` của tối đa 8 lần
cùng mode. Lần đầu/local có load model nên ước tính kém chính xác hơn; đây chỉ
là gợi ý, không phải cam kết.

## Giới hạn ký tự

- **3000 là ký tự**, không phải từ.
- Server Rust/Python mặc định `MAX_CHARS=3000` để giới hạn request/CPU.
- Extension **không còn cắt local ở 3000**; textarea cho nhập dài.
- Page/selection được lấy tối đa 50.000 ký tự để tránh trang quá lớn.
- Remote vẫn bị server chặn nếu vượt `max_chars`.
- Local stream xử lý theo chunk nên không cần giới hạn 3000; memory/UI vẫn nên
  có điểm dừng hợp lý.

## Local

- wasm + ORT Web chạy trong extension;
- không gửi text ra ngoài;
- model bundle hoặc tải từ Model base URL rồi cache vào Cache Storage;
- có thể dùng `.vfa`/`.vfts` tải qua server: offscreen giải nén ZIP, kiểm SHA256
  bằng `crypto.subtle`, rồi tạo session; `.vfa` lấy vocoder bundled/model base;
- lần đầu chậm do nạp model/khởi tạo session.

## Remote

- gọi `POST /api/tts` với `karaoke: true`;
- server local: `http://127.0.0.1:8000`;
- domain VPS: `https://tts.domain.vn`;
- Chrome hỏi host permission nếu server không phải localhost;
- model base URL cũng xin host permission nếu khác origin;
- token gửi qua `Authorization: Bearer ...`;
- VPS cần TLS hợp lệ; server cần auth/rate-limit trước khi public.

## Từ điển local

Trong popup → **Cài đặt** → **Từ điển local**, mỗi dòng:

```text
AI = ây ai
VPS = vi pi ét
xyzabc = ích dét
```

Giá trị phải là âm tiết tiếng Việt hợp lệ. Ví dụ chữ Z nên viết `dét` hoặc
`giét`; viết `zét` sẽ bị parser fallback thành “a”.

- Lưu trong `chrome.storage.local`;
- Local: merge với built-in `overrides_vi.json` rồi đưa vào
  `synthesize_with_options`;
- Remote: gửi object `overrides` + raw `dictionary` tới server; Python demo đọc
  `overrides`, Rust server parse `dictionary` bằng `vifasttts-app::parse_dictionary`;
- `custom_reading` token-level chưa có UI riêng.

## Logic dùng chung `vifasttts-app`

- `offscreen.js` gọi wasm `dictionary_json` (parse/validate/warnings từ Rust),
  không còn parser `key = value` riêng.
- `background.js` gọi wasm `eta_estimate` (`EtaEstimator`) cho ETA; history vẫn
  lưu bằng `chrome.storage` vì đó là adapter UI.
- Engine/synth/karaoke/iSTFT dùng `vifasttts-browser`/`vifasttts-engine`.
- Settings form vẫn là JS (adapter `chrome.storage`); chưa có binding wasm cho
  toàn bộ `AppSettings`.

## Cache model

Hai loại cache trong `vifasttts-models-v1`:

- raw `acoustic.onnx`/`vocoder.onnx` từ Model base URL;
- bundle người dùng `.vfa`/`.vfts` (key `https://vifasttts.invalid/bundles/...`).

Bundle đang dùng nằm trong `bundleKey`/`bundleName` của `chrome.storage.local`.
Nút **Bỏ bundle** chỉ bỏ active bundle; **Xoá cache model** xoá toàn bộ cache và
active bundle.

## Giới hạn hiện tại

- Chưa có native messaging/desktop app.
- Raw ONNX tải từ Model base URL chưa có manifest; bundle `.vfa/.vfts` có
  manifest/hash và được ưu tiên.
- Stream hiện chạy trong offscreen; chưa Web Worker riêng.
- Catalog dùng server proxy; extension không gọi HuggingFace trực tiếp.
- Edge chưa test trên máy này; API dùng là Chromium (`chrome.*`, MV3,
  `offscreen`, `contextMenus`, `activeTab`, `scripting`).
