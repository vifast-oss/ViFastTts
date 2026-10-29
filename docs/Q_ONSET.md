# Q onset — triển khai 27/10/2026

> Quyết định Agent 0: thêm **Q** trực tiếp vào vocab. Từ 28/10/2026 bỏ cờ `onset_has_q`;
> thay bằng `vocab_version=vi-q25-v1` + `vocab_hash`. N0 hiện vẫn là giọng Bắc.

## 1. Token và parser

- Q là onset thứ **25**, đứng **cuối** danh sách (ID 24); ID cũ 0–23 không đổi.
- Mọi chữ `qu` dùng **Q**:
  - `quốc` = Q + NONE + UÔ + C + sắc;
  - `cuốc` = K + NONE + UÔ + C + sắc (Bắc đồng âm, khác token);
  - `qua` = Q + W + A; `quất` = Q + W + Â + T; `quyển` = Q + W + IÊ + N.
- `D/GI/R/V` vẫn 4 token riêng. Lý do: một số thổ ngữ Bắc Trung Bộ còn phân biệt
  d/gi/r; Trung bộ chính (Huế/Quảng Nam) và Nam gộp d/gi; Nam đọc r khác d/gi.
  Không ghi “Nam phân biệt D/GI”.
- G2P/IPA chỉ là tài liệu; code map Q như K cho Bắc. IPA Nam (`qu ≈ [w]`) chưa cài.
- Không thêm dialect id/speaker embedding trong N0. TODO: nếu train một model chung
  nhiều vùng thì bắt buộc thêm conditioning; train riêng từng vùng thì không.

## 2. Checkpoint / ONNX

- Checkpoint/ONNX mới có `vocab_version` + `vocab_hash`.
- Artifact cũ không còn được hỗ trợ; **không có adapter Q→K**.
- `--init-from` cho phép fine-tune một lần từ checkpoint v2 cũ: thêm hàng Q = embedding K.
- ONNX Q dùng metadata và `runtime/onnx_engine` kiểm tra trước khi chạy.
- Q-init checkpoint (`runs/acoustic_ngochuyen_q/init_q.pt`) cho output **bit-exact** model
  N0 Bắc cũ (đã kiểm mel/durations/f0 trên câu có quốc/quê/qua/quyển/quân).

## 3. Fine-tune candidate

Config `configs/small_ngochuyen_q.yaml`; 3.000 bước, LR 5e-5, Q khởi tạo bằng K:

| Mốc | val mel hữu thanh | val rough |
|---|---:|---:|
| N0 cũ | 0,26340 | 0,7624 |
| 1.000 | 0,26403 | 0,75956 |
| 2.500 | 0,26329 | 0,76151 |
| 3.000 | 0,26320 | 0,76318 |

Fine-tune không thắng rõ cả mel và rough; **chưa deploy**. Q-init (Q=K) đang là bản
an toàn cho N0 Bắc, giữ đúng giọng đã được nghe. Candidate fine-tune để so tai:
release nghe thử `q-preview-2026-10-27` (đã xoá 29/10/2026; artifact QFT giữ local, chưa đưa lên HF).

## 4. Validator

- `tools/validate_syllables.py` quét manifest, báo `stale_abstract`, `legacy_k_w`,
  coda-tone, medial-nucleus, fallback, strict warnings.
- Allowlist W sau phụ âm môi: `resources/loanword_labial_w.txt` (`buýt`, `voan`, `boa`);
  chỉ cảnh báo.
- Đã reparse N0 train/val/holdout (`*_slot4`): 6.961 + 436 + 404 âm tiết đổi sang Q.
  Validator train: 7 cảnh báo `spelling-k-before-back`; val/holdout: 0.
- Feature cache không chứa token; không cần rebuild cache, chỉ reparse manifest.

## 5. Trạng thái triển khai (27/10/2026)

- **Đang live:** Q-init, `Q = K`, output **bit-exact** với N0 Bắc cũ.
  - Checkpoint: `runs/acoustic_ngochuyen_q/init_q.pt` sha256 `3c330cfcec9ad2…`.
  - ONNX: `artifacts/onnx/n0_q/acoustic.onnx` sha256 `df61599a15984dcc…`;
    vocoder `b3eb09cf5c3baa…`; `healthz` báo `vocab_version` + `vocab_hash`.
  - HuggingFace: `onnx/acoustic.onnx` (`df61599a…`) + `onnx/vocoder.onnx` (`b3eb09cf…`)
    trong `dvchd/vifasttts-ngochuyen-small`; bundle `bundles/n0-ngochuyen.vfa/.vfts`.
  - GitHub Releases cũ đã xoá ngày 29/10/2026.
- **Chưa live:** fine-tune 3k `runs/acoustic_ngochuyen_q/best.pt`
  (sha256 `30dc41642461…`), ONNX `artifacts/onnx/n0_q_ft/acoustic.onnx`
  (sha256 `394fa657fc6e52…`). Release nghe A/B `q-preview-2026-10-27` đã xoá;
  artifact QFT giữ local, chưa đưa lên HF vì chưa chọn.
- **Bản cũ bị từ chối:** ONNX N0 `6c8bde3d…` thiếu hash; không có adapter Q→K.
- Quyết định chọn model + hash/release cập nhật ở `docs/handoff/TRANG_THAI.md`.
