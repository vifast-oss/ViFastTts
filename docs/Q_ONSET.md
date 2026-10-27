# Q onset — triển khai 27/10/2026

> Quyết định Agent 0: thêm **Q** trực tiếp vào vocab, không làm `vocab_version`; chỉ dùng cờ
> metadata `onset_has_q` để phân biệt model cũ/mới. N0 hiện vẫn là giọng Bắc.

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

- Checkpoint/ONNX mới có `onset_has_q=true`.
- Checkpoint/ONNX cũ thiếu cờ bị từ chối rõ ràng; **không có adapter Q→K**.
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
`q-preview-2026-10-27` (release tạm: https://github.com/dvchd/ViFastTts/releases/tag/q-preview-2026-10-27).

## 4. Validator

- `tools/validate_syllables.py` quét manifest, báo `stale_abstract`, `legacy_k_w`,
  coda-tone, medial-nucleus, fallback, strict warnings.
- Allowlist W sau phụ âm môi: `resources/loanword_labial_w.txt` (`buýt`, `voan`, `boa`);
  chỉ cảnh báo.
- Đã reparse N0 train/val/holdout (`*_slot4`): 6.961 + 436 + 404 âm tiết đổi sang Q.
  Validator train: 7 cảnh báo `spelling-k-before-back`; val/holdout: 0.
- Feature cache không chứa token; không cần rebuild cache, chỉ reparse manifest.
