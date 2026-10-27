# N0 — release chính thức + preview Q (27/10/2026)

> **Trạng thái:** 2 release chính (`prod`, `research`) + **1 preview tạm** cho A/B Q-init vs
> fine-tune. Tất cả đều **research/non-commercial** vì dataset CC-BY-NC-4.0.
> Release audio test cũ đã xoá.

## 1. Prod candidate (nội bộ)

- Tag: `n0-ngochuyen-prod-v1`
- URL: https://github.com/dvchd/ViFastTts/releases/tag/n0-ngochuyen-prod-v1
- Asset chính: `n0_ngochuyen_prod_v1.zip` (129.507.134 B;
  sha256 `3c7673c98dc62892bb0a987eee5fb265728cf38bd35c80f98d017b586f294ea8`)
  + `prod_SHA256SUMS`.
- ONNX:
  - **`n0_onnx_fp32_q.zip`** — Q-init, **đang live**: 79.437.883 B,
    sha256 `ef35567c4433cf823db78ef90f716a259d14c79d62bed53e621f93b5231a01ed`;
    acoustic `16e66b70…`, vocoder `b3eb09cf…` (có `SHA256SUMS` bên trong).
  - `n0_onnx_fp32.zip` — N0 cũ chưa có Q: 79.438.477 B,
    sha256 `3521ac2e79aabf179017a2ba7abcaf56f13bbf852efd10a3a7742b609045c687`;
    **bị runtime mới từ chối** vì thiếu `onset_has_q=true`, giữ lịch sử.
  - `n0_onnx_fp32_SHA256SUMS` — checksum của gói N0 cũ, **không** áp dụng cho gói Q.
- Nội dung package: acoustic 60k, config/stats, Vocos pretrained, 10 demo, inference/model card/license;
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
  + `research_SHA256SUMS`; ONNX dùng chung `n0_onnx_fp32.zip` (N0 cũ, chưa Q).
- Nội dung: như prod + `TRAINING.md` (quá trình, thời gian, khuyến nghị dữ liệu
  small/base) + `REPORT.md` (đo/nghe) + model card.
- **Research/non-commercial, không production.**

## 3. Preview Q (tạm)

- Tag: `q-preview-2026-10-27` (pre-release)
- URL: https://github.com/dvchd/ViFastTts/releases/tag/q-preview-2026-10-27
- Chỉ 2 WAV để nghe A/B, **không phải asset triển khai**:
  - `init.wav` — Q-init, sha256 `85f8951c…e083a80`
  - `finetune.wav` — fine-tune 3k, sha256 `891d6d97…8c26199`
- Xoá sau khi người dùng chọn model live (`gh release delete q-preview-2026-10-27 --yes`).

## 4. Đã xoá

Toàn bộ release audio test cũ (`demo-audio-*`, `demo-giong-clone-*`,
`n0-ngochuyen-small-research-v1`). `gh release list` hiện còn 3 tag: 2 chính + preview Q.

## 5. Hugging Face

- https://huggingface.co/dvchd/vifasttts-ngochuyen-small
- License metadata `cc-by-nc-4.0`; có checkpoint, config/stats, Vocos, ONNX, demo, model card.
- ONNX Q: commit `0b08245ee96710a738d7b1e543151e026b4f6cde`; model card gốc:
  `6cfd13e16be700aaec68175086ee44be929bc01b`.
- Static Space: https://huggingface.co/spaces/dvchd/vifasttts-ngochuyen-demo
