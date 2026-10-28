# Tìm và tải model `.vfa` / `.vfts`

## Desktop

Mở app → nút **Thêm giọng từ HuggingFace**:

1. Nhập từ khóa (mặc định `vifasttts`).
2. Bấm **Tìm**.
3. Chọn repo.
4. Danh sách chỉ hiện file `.vfa` / `.vfts` (file raw `acoustic.onnx` bị bỏ qua).
5. Bấm file để tải; app kiểm manifest/hash khi nạp.
6. `.vfa` được nạp với vocoder bundled; `.vfts` tự chứa vocoder.

Thư mục tải mặc định:

```text
~/Library/Application Support/com.vifasttts.ViFastTts/models/
```

Trên Windows/Linux theo `directories` của hệ điều hành.

## CLI

```bash
# tìm repo
vifasttts models search --query vifasttts

# xem .vfa/.vfts trong repo
vifasttts models files dvchd/vifasttts-ngochuyen-small

# tải bundle
vifasttts models download \
  dvchd/vifasttts-models \
  voices/n0-ngochuyen/n0-ngochuyen.vfa \
  --output models
```

- Public repo không cần token.
- Private repo: `export HF_TOKEN=...`.
- Chỉ tải file kết thúc `.vfa`/`.vfts`.
- Giới hạn tải 512 MB.

## Tìm bằng tay trên web

HuggingFace files API:

```text
https://huggingface.co/api/models?search=vifasttts&limit=20&full=true
https://huggingface.co/api/models/<repo>/tree/main?recursive=true
```

Download:

```text
https://huggingface.co/<repo>/resolve/main/<path>
```

## Lưu ý

- Repo hiện tại có thể chỉ có `onnx/acoustic.onnx`; UI sẽ báo chưa có bundle.
  Cần upload `.vfa`/`.vfts` (xem `docs/MODEL_DISTRIBUTION.md`).
- `.vfa` chỉ chạy nếu vocoder hash khớp; app/package N0 có Vocos pretrained.
- `.vfts` là lựa chọn an toàn khi chia sẻ cho người khác.
- License CC-BY-NC; kiểm tra trước khi tải.
- Web/extension/mobile chưa có model browser riêng; dùng desktop/CLI hoặc remote
  server. API client dùng chung nằm ở crate `vifasttts-huggingface`.
