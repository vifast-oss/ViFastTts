# Định dạng model `.vfts` (đề xuất, chưa triển khai)

> Trạng thái: **đề xuất** — repo hiện chỉ có manifest JSON
> `rust/models/n0-q.manifest.json` + 2 file ONNX. Không tìm thấy spec/implementation
> `.vfts` trong lịch sử repo. Không đổi loader hiện tại khi chưa chốt.

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

## Phase triển khai đề xuất

1. `vifasttts-vfts` crate: `pack`, `read`, `inspect`; test với byte giả.
2. CLI `vifasttts-rs vfts pack|inspect|unpack`.
3. Desktop/mobile mở `.vfts` → `ModelSource` → `from_bytes`.
4. CI: tạo `.vfts` từ release ONNX; upload cạnh model ZIP.
5. Sau khi có spec ổn định mới đổi `rust/models/n0-q.manifest.json` sang bundle.

**Chưa nên** thay manifest/thư mục hiện tại ngay: sẽ phá CLI, desktop, mobile và
các script parity đang dùng path ONNX.
