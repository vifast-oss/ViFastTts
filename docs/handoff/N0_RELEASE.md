# N0 — hai release chính thức (27/10/2026)

> Chỉ còn **2 release**; toàn bộ release audio test cũ đã xoá. Cả hai đều
> **research/non-commercial** vì dataset CC-BY-NC-4.0.

## 1. Prod candidate (nội bộ)

- Tag: `n0-ngochuyen-prod-v1`
- URL: https://github.com/dvchd/ViFastTts/releases/tag/n0-ngochuyen-prod-v1
- Asset: `n0_ngochuyen_prod_v1.zip` (129.507.134 B;
  sha256 `3c7673c98dc62892bb0a987eee5fb265728cf38bd35c80f98d017b586f294ea8`)
  + `prod_SHA256SUMS`; ONNX: `n0_onnx_fp32.zip`
  (79.438.477 B; sha256 `3521ac2e79aabf179017a2ba7abcaf56f13bbf852efd10a3a7742b609045c687`).
- Nội dung: acoustic 60k, config/stats, Vocos pretrained, 10 demo, inference/model card/license;
  ONNX FP32 acoustic + vocoder tách riêng.
- **Không phải release thương mại**: chỉ ứng viên prod nội bộ trong phạm vi CC-BY-NC;
  không bán/phân phối thương mại.
- Mặc định: `sharpen_alpha=1.5`, `pause_mode="model"`, Vocos pretrained; không fine-tune.
- Đã tải lại asset, kiểm sha256, giải nén chạy `inference.py` CPU thành công.

## 2. Research

- Tag: `n0-ngochuyen-research-v1`
- URL: https://github.com/dvchd/ViFastTts/releases/tag/n0-ngochuyen-research-v1
- Asset: `n0_ngochuyen_research_v1.zip` (129.515.554 B;
  sha256 `152d9059aff380e2241e1cc6e995d8e57dbd0ece9688c6d370df352d48f0d4fa`)
  + `research_SHA256SUMS`; ONNX dùng chung `n0_onnx_fp32.zip`.
- Nội dung: như prod + `TRAINING.md` (quá trình, thời gian, khuyến nghị dữ liệu
  small/base) + `REPORT.md` (đo/nghe) + model card.
- **Research/non-commercial, không production.**

## Đã xoá

Toàn bộ release audio test cũ (`demo-audio-*`, `demo-giong-clone-*`,
`n0-ngochuyen-small-research-v1`). `gh release list` hiện chỉ còn 2 tag trên.
