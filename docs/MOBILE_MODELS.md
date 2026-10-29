# Mobile model packaging & nhiều giọng

## Hiện tại (29/10/2026)

- Android APK **đóng gói sẵn** N0 Ngọc Huyền FP32:
  - `assets/acoustic.onnx` ~31,6 MB
  - `assets/vocoder.onnx` ~54,2 MB
  - APK ~110 MB; copy sang `filesDir` lần đầu.
- Model bundled có sẵn; model browser có thể tải HuggingFace trực tiếp nếu Server URL trống.
- Chỉ có một model; chưa có catalog/chọn giọng/tải thêm.
- Android đã có **local + remote**; remote gọi `/api/tts` của desktop/server.
- Không có server mode trên mobile (theo quyết định hiện tại).

## Có nên bỏ bundle, tải từ HuggingFace lần đầu?

### Nếu ưu tiên offline / đơn giản

Giữ bundle như hiện tại:

- mở app là chạy được, không cần mạng;
- không cần progress/retry/hash;
- APK lớn ~110 MB (vẫn dưới giới hạn sideload; Play có thể dùng App Bundle).

### Full bundle vs acoustic-only

- `.vfts`: full, ~76 MB, an toàn/offline, chứa cả vocoder.
- `.vfa`: acoustic + frontend, ~28 MB; tham chiếu vocoder bằng SHA256. Dùng khi
  vocoder pretrained/shared đã có và khớp contract mel.
- Mặc định tải full `.vfts`; client có thể chọn `.vfa` nếu `vocoder.sha256`
  khớp vocoder đang có.

### Nếu ưu tiên APK nhỏ

Thin APK + tải lần đầu:

```text
https://huggingface.co/dvchd/vifasttts-ngochuyen-small/resolve/main/onnx/acoustic.onnx
https://huggingface.co/dvchd/vifasttts-ngochuyen-small/resolve/main/onnx/vocoder.onnx
```

Cần:

- `INTERNET`, `ACCESS_NETWORK_STATE`, Android 16+ `ACCESS_LOCAL_NETWORK`;
- progress + retry + resume;
- SHA256 cố định từ manifest;
- kiểm dung lượng trống trước khi tải;
- lỗi rõ nếu offline; fallback remote mode;
- lưu theo `filesDir/models/<id>/` và chỉ kích hoạt sau khi hash đúng;
- license CC-BY-NC hiển thị trước khi tải.

## Nhiều model

Nên dùng **catalog** thay vì hard-code URL:

```json
{
  "version": 1,
  "models": [
    {
      "id": "n0-ngochuyen-q",
      "name": "Ngọc Huyền",
      "arch": "v2_slot5",
      "vocab_hash": "…",
      "size": 85785390,
      "license": "CC-BY-NC-4.0",
      "url": "https://…/n0-ngochuyen.vfts",
      "sha256": "…"
    }
  ]
}
```

- Nguồn catalog: HuggingFace trực tiếp (mặc định khi Server URL trống) hoặc desktop server `/api/models` (tuỳ chọn).
- File tải nên là `.vfts` (manifest + ONNX + dictionary snapshot) để một file
  chứa đủ model và kiểm hash.
- Client lưu nhiều model, chọn active model; xoá từng model; không tải trùng.
- Android/iOS có cấu hình local: tốc độ, alpha, pause cố định, peak normalize,
  max ký tự/chunk, phương ngữ, resolve OOV và từ điển `key = cách đọc`.
- Có karaoke theo âm tiết trên màn hình; lưu/chia sẻ WAV + SRT + VTT + JSON.
- Câu mặc định Android có chữ **Android**, iOS có chữ **iOS** để phân biệt bản
  test; core đọc `iOS` = **ai âu ét**, `Android` = **an đờ roi**.
- Model base 60k nặng hơn small nên máy yếu nên dùng small.
- Không cần server riêng cho model public; server chỉ hữu ích cho model nội bộ
  hoặc LAN.
- Khi remote, không cần tải model local.

## Khuyến nghị

1. **Giữ bundle N0 mặc định** cho bản mobile đầu tiên để direct-first/offline.
2. Thêm **remote mode** (đã có).
3. Thêm catalog + tải `.vfts` như tính năng optional, không auto-tải model thay
   thế model đang dùng.
4. Nếu cần giảm APK mạnh: chuyển sang thin-client + tải N0 từ HF, nhưng phải
   chấp nhận first-run cần mạng.
