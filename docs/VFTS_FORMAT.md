# Định dạng model `.vfts` (đề xuất, chưa triển khai)

> Trạng thái: **đã triển khai core** (crate `vifasttts-vfts`, CLI `vifasttts-rs vfts`);
> bundle là optional, loader ONNX hiện tại vẫn là canonical. Trước đây repo chỉ có
> manifest JSON + 2 file ONNX; không có spec `.vfts` cũ để tương thích.

## Mục tiêu

Một file bundle để phát hành/kiểm tra model, không thay ONNX runtime:

```text
model.vfts (ZIP, không mã hoá)
├── manifest.json          # schema vifasttts-model-v1
├── acoustic.onnx
├── vocoder.onnx
├── LICENSE
├── NOTICE
└── README.md
```

## manifest.json

Giữ tương thích schema hiện tại:

```json
{
  "format": "vifasttts-model-v1",
  "arch": "v2_slot5",
  "sample_rate": 24000,
  "n_mels": 100,
  "n_fft": 1024,
  "hop_length": 256,
  "vocab_version": "vi-q25-v1",
  "vocab_hash": "…",
  "acoustic": {"file": "acoustic.onnx", "sha256": "…"},
  "vocoder": {"file": "vocoder.onnx", "sha256": "…"},
  "ort": {"tested": "1.31.1", "mode": "load-dynamic"},
  "license": "research/non-commercial; dataset CC-BY-NC-4.0"
}
```

## Quy tắc

- Chỉ chấp nhận ZIP stored/deflate; không có symlink, path `..` hoặc entry tuyệt đối.
- Đọc manifest trước, kiểm `format`, `arch`, `vocab_hash`, SHA256 của hai ONNX
  trước khi gọi ORT.
- Giới hạn kích thước giải nén (ví dụ 512 MB) để chống zip bomb.
- `.vfts` chỉ là **container phân phối**; `NativeEngine` vẫn nhận bytes ONNX như
  `from_bytes` hiện tại.
- Chữ ký số (minisign/cosign) là phase sau; sha256 trong manifest không thay chữ ký.

## `.vfa` — acoustic-only, vocoder dùng chung

Vocoder hiện tại là **Vocos pretrained `charactr/vocos-mel-24khz`** (không phải
fine-tune N0; fine-tune 10k đã bị loại vì rè). Vì vậy có thể dùng chung vocoder
cho các acoustic model cùng contract mel.

```bash
# đóng gói acoustic-only (~28 MB thay vì ~76 MB full)
rust/target/release/vifasttts-rs vfa pack \
  --output n0.vfa \
  --vocoder artifacts/onnx/n0_q/vocoder.onnx

# synth
rust/target/release/vifasttts-rs synth --vfa n0.vfa \
  --vocoder artifacts/onnx/n0_q/vocoder.onnx --text "Xin chào"
```

`.vfa` manifest ghi `vocoder.id`, `vocoder.sha256`, sample contract; loader trả
lỗi nếu vocoder không khớp hoặc frontend/vocab khác runtime.

## Đã có trong code

```bash
# đóng gói ONNX + snapshot frontend resources
rust/target/release/vifasttts-rs vfts pack \
  --output n0.vfts

# xem manifest/hash/frontend
rust/target/release/vifasttts-rs vfts inspect n0.vfts

# giải nén
rust/target/release/vifasttts-rs vfts unpack n0.vfts --output /tmp/n0
```

- `vifasttts-vfts`: `VftsBundle` + `ModelSource`; kiểm ZIP traversal/zip-bomb,
  SHA256, manifest, `frontend/vocab.json` runtime hash.
- `vifasttts-native::load_vfts`; CLI `--vfts`; server `--vfts`; TUI `--vfts`;
  desktop có ô chọn `.vfts`; FFI `vifasttts_engine_new_vfts`; mobile
  `MobileRuntime::from_vfts`.
- CI job `model-vfts` tạo `n0-ngochuyen.vfts` từ release ONNX.
- Frontend resources được đóng gói để audit/version; runtime vẫn dùng resource
  nhúng trong `vifasttts-text` (vocab được kiểm khớp). Chưa override dictionary
  runtime từ bundle — cần refactor resource loader nếu muốn thay hoàn toàn.

## Phase triển khai tiếp

1. ✅ `vifasttts-vfts` crate: `pack/read/inspect/unpack`; test traversal/zip-bomb/hash.
2. ✅ CLI `vifasttts-rs vfts pack|inspect|unpack`; `--vfts` cho synth/inspect.
3. ✅ Desktop/TUI/server/FFI/mobile có loader `.vfts`; web extension chưa cần.
4. ✅ CI job `model-vfts` tạo bundle từ release ONNX.
5. ⬜ Runtime override toàn bộ dictionary/frontend resource từ bundle (hiện dùng
   resource nhúng; chỉ kiểm vocab khớp).
6. ⬜ Đổi manifest/thư mục hiện tại sang `.vfts` mặc định.

**Chưa nên** thay manifest/thư mục hiện tại ngay: sẽ phá CLI, desktop, mobile và
các script parity đang dùng path ONNX.
