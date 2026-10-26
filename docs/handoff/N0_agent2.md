# N0 — Agent 2: train small mới trên `ngochuyen_voice`

> **Trạng thái: DỪNG — ĐÃ TRAIN XONG, CHỜ NGƯỜI NGHE.** Không đổi production, không ONNX.
> **Dataset CC-BY-NC-4.0** → chỉ dùng phi thương mại/nghiên cứu.
> **Commit gốc**: `8a2b94f` · **Báo cáo này**: commit hồ sơ cuối vòng.
> Tệp đặc tả/recipe: `docs/handoff/NGUYEN_DATA.md`.

## 0. Tóm tắt

| Việc | Kết quả |
|---|---|
| Nguồn | `pnnbao-ump/ngochuyen_voice`, 7.540 clip, 24 kHz, **21,569 h** |
| Lọc/split | **19,893 h** (6.989 clip); 17,894 train / 1,014 val / 0,985 holdout |
| MFA | **6.989/6.989** TextGrid, 0 drop; từ khớp 100% âm tiết |
| Segment | 9.546 train / 537 val / 527 holdout; 0 lỗi bất biến |
| Acoustic | small v2_slot5 6,1M, **60.000 bước từ đầu**; best val mel **0,2634** |
| Holdout | mel **4,0 dB** (z 0,298); F0 median 67–159 cents; duration MAE 1,4 frame |
| Free-run | mel **16,57 dB** · length 0,999 · pause F1 **0,825** (P2: 28,31 dB / 0,960 / 0,510) |
| Thanh | thật **0,9835** · copy **0,9784** · free **0,9743** |
| Vocos | fine-tune 10k: mel **0,1167** (pretrained 0,1432) |
| Nghe | https://instant-weblogs-reductions-separated.trycloudflare.com/ |

## 1. Dữ liệu

- 7.540 clip WAV 24 kHz mono; peak 0,51–0,84; **0 clip clipping**; lặng đuôi 0,20–0,56 s.
- Sửa số/ngày trước parse: `02 → 2`, `23/4/2024 → ngày 23 tháng 4 năm 2024`,
  `06/5 → ngày 6 tháng 5`, `-> → đến`.
- Lọc: parse VALID 100%, không mã trộn chữ+số, 2–20 s, tốc độ 2,5–6,0 syl/s,
  không trùng audio/text. Loại 551 clip (487 parse fallback, 32 mã trộn, 23 audio trùng,
  8 text trùng, 1 tốc độ).
- Split 90/5/5 theo hash text, seed 42 — không rò rỉ câu trùng.
- MFA 2.2.17 + acoustic `vietnamese_mfa` + G2P 1.044 OOV; align 6.989 clip,
  `--single_speaker --beam 100 --retry_beam 400`, 408 s; **0 clip thiếu/lệch**.
- Cắt 3–10 s tại pause (`max_gap 60`, `tail_cap 67`), sàn 0,25 s; 0 fail `seg_durations`.

## 2. Train

- Config `configs/small_ngochuyen.yaml`; `v2_slot5` small: dim 64 · hidden 192 ·
  4 encoder · 2 decoder · postnet; batch 8 `SameNBatchSampler`; LR 2e-4 cosine 60k;
  phase A 2.000; cache v3 `cache/ngochuyen_v2`; phát hiện/sửa lỗi schema f0.
- Checkpoint chính: `runs/acoustic_ngochuyen/best.pt`, step **60.000**,
  sha256 `d1b216423485d8ebaf7ae6e3a63260372299694559f52aa7730f79022f640070`.
- History: val mel hữu thanh **0,26340**; độ nét **0,7624**; plateau từ ~44k (0,2660).
- Không warm-start, không adversarial, không tone_disc.

## 3. Đo

### 3.1 Acoustic (tf_seg)

| Tập | clip | mel L1 z | raw | dB | VUV | duration MAE |
|---|---:|---:|---:|---:|---:|---:|
| val | 300 | 0,2954 | 0,4585 | 4,0 | 0,987 | 1,33 frame |
| holdout | 300 | 0,2980 | 0,4626 | 4,0 | 0,987 | 1,37 frame |

F0 median (holdout): NGANG 77 · HUYEN 67 · SAC **159** · HOI 79 · NGA 92 · NANG 104 cents.
SAC là thanh yếu nhất, giống xu hướng dữ liệu cũ nhưng mức tuyệt đối thấp hơn nhiều.

### 3.2 Free-run 80 holdout (Vocos pretrained)

| | model mới | P2 zero-shot |
|---|---:|---:|
| mel dB | **16,57** | 28,31 |
| mel dB speech | **15,06** | 19,83 |
| length ratio | **0,999** | 0,960 |
| duration MAE | **1,39 frame** | 3,52 frame |
| pause F1 | **0,8247** | 0,5098 |
| mel_gap dB | **2,285** | 6,224 |
| VUV | 0,9887 | 0,9870 |

### 3.3 Thanh (thước R5b train riêng giọng mới)

- Thật **0,9835** (2.362 âm tiết) — trần thước trên giọng này.
- Copy-synthesis **0,9784**; free-run **0,9743** (Vocos pretrained), **0,9749** (Vocos 10k).
- Mất **0,0092** tuyệt đối từ thật → free-run; không có dấu hiệu model bỏ thanh.

### 3.4 Rè (80 clip, CPU)

- NGÃ: ΔHNR **+1,86 dB** · Δjitter **−0,0106** (synth sạch hơn thật).
- NẶNG: ΔHNR +0,30 dB · Δjitter +0,0143.
- Không thấy tăng rè theo thanh nặng; clipping 0.

### 3.5 Vocos

- Fine-tune 10.000 bước MPS trên 17,9 h; `runs/vocoder_ngochuyen/last.pt`,
  sha256 `a5c89ead105dd054f9a1bd9906d44da110cc68e2acb0af0b6a225d33c320d477`.
- Copy-synthesis 100 holdout: **mel 0,1167** vs pretrained **0,1432** (−18,5%);
  F0 85,2 vs 88,9 cents; VUV 0,0223 vs 0,0206; clipping ~0.

## 4. Nghe

- A/B mù (thật · mới · P2; Vocos pretrained, 24 câu):
  https://instant-weblogs-reductions-separated.trycloudflare.com/ab/
- Model mới + Vocos pretrained: `/new/`
- Model mới + Vocos fine-tune 10k: `/new_vocos/`
- P2 zero-shot: `/p2/`
- Key A/B: `artifacts/ngochuyen/ab_key.json` (local, không commit).

## 5. TỰ QUYẾT KHÁC ĐẶC TẢ

1. **Sửa chain**: `compute_f0_stats.py` sinh schema cũ (DCT, thiếu `shape_mean`) làm train
   dừng; thay bằng `r5b_segment_stats.py` trước khi train. Đã ghi trong `NGUYEN_DATA.md`.
2. **Vocos CPU song song** thử 18 phút nhưng 1 bước quá chậm; kill, chạy MPS tuần tự.
3. `eval_creak` có bug device khi `--device mps` (model CPU, vocoder MPS) → chạy CPU.
4. A/B dùng **cùng Vocos pretrained** cho cả hai acoustic để so công bằng; Vocos fine-tune
   để trang riêng.
5. Không dùng CER/ASR làm cổng; không UTMOS; không cắt/ghi đè audio gốc.

## 6. Cảnh báo

- **License CC-BY-NC-4.0**: không dùng thương mại, không đưa vào production thương mại khi
  chưa có phép/nguồn khác.
- Chỉ **một người nghe** (chưa có CSV A/B); kết luận "tốt nhất" là trong phạm vi run này,
  chưa phải bằng chứng ngoài.
- Đây là model **single-speaker**; không nhận speaker ID, không zero-shot giọng khác.
- Không đổi production/ONNX; P2 vẫn là production hiện tại.

## 7. Git log vòng này

```
8a2b94f docs(v18.52): scan toàn bộ xong 20.837 segment; chưa tổng hợp
0d484d4 n0(data): ngochuyen_voice 19,89 h sạch + MFA + split 90/5/5 + config small
96130b8 n0(fix): dùng r5b_segment_stats cho f0 shape_mean
372b3cf n0(data): ghi kết quả segment + sửa schema f0 stats
116de7a n0(demo): steady_demo nhận --vocoder riêng
4a5bff4 n0(eval): số acoustic/tone + trang A/B + eval script
(+ commit hồ sơ này)
```

**Trạng thái: DỪNG — CHỜ NGƯỜI NGHE.** Nếu nghe đạt: chốt `best.pt` + `vocoder_ngochuyen/last.pt`.
Nếu cần production: xử lý license trước; không tự chuyển.

## 8. Kết quả tai — A/B (27/10/2026)

- CSV 24/24 câu, không thiếu, không “hòa”: **model mới 24 · P2 zero-shot 0**.
- **A/B dùng Vocos pretrained mặc định** `artifacts/pretrained/vocos-mel-24khz/pytorch_model.bin`,
  không dùng Vocos fine-tune.
- Nhận xét người nghe: **“model mới đọc như thật, không rè, không nhiễu”**.
- Kết luận: giữ **Vocos mặc định** cho acoustic mới. Vocos fine-tune 10k chỉ là ứng viên riêng
  (`/new_vocos`), chưa được tai xác nhận; **không đưa vào production**.

## 9. Câu mới ngoài train — kiểm Vocos (27/10/2026)

- 10 câu tự soạn, **không có trong train/val/holdout**; kiểm 5-gram trên toàn bộ manifest:
  **0 trùng** cho cả 10 câu.
- Cùng acoustic `best.pt`, chỉ đổi vocoder; trang:
  `https://instant-weblogs-reductions-separated.trycloudflare.com/fresh/`
- Người dùng nghe: **Vocos fine-tune 10k còn vị rè**; bản mặc định sạch hơn.
- Đo lại 10 câu (cùng extractor): fine-tune vs mặc định:
  jitter mean **0,0664 vs 0,0630** (p95 0,264 vs 0,242);
  glottalization mean **0,00486 vs 0,00227**; HNR gần nhau (0,755 vs 0,763).
  Xu hướng khớp tai: fine-tune hơi “rè/ghé” hơn.
- **Quyết định: giữ Vocos pretrained mặc định**; Vocos fine-tune không đưa vào production/demo chính.
  File fine-tune vẫn để đối chiếu, không xoá.


## 10. Chính sách ngắt nghỉ (27/10/2026)

- Dữ liệu sạch → **model tự ngắt nghỉ là mặc định** (`pause_mode="model"`).
- Nghỉ cố định là opt-in: API `pause_mode="fixed"`, CLI `--fixed-pauses`, HTTP payload
  `"pause_mode":"fixed"`; `--steady` chỉ là alias cũ (ẩn), mặc định tắt.
- Fixed chặn pause model (gate 1.01), chèn 0,25 s sau phẩy và 0,55 s sau chấm/hỏi/than.
- Không đổi hành vi mặc định của P2/ONNX cũ; N0 mặc định model-pause.

## 11. Releases (27/10/2026)

- **Prod candidate nội bộ**: `n0-ngochuyen-prod-v1`
  https://github.com/dvchd/ViFastTts/releases/tag/n0-ngochuyen-prod-v1
  (`n0_ngochuyen_prod_v1.zip`, sha256 `3c7673c9…94ea8`).
- **Research**: `n0-ngochuyen-research-v1`
  https://github.com/dvchd/ViFastTts/releases/tag/n0-ngochuyen-research-v1
  (`n0_ngochuyen_research_v1.zip`, sha256 `b0c7add9…ee077`).
- Cả hai gồm acoustic 60k, config/stats, Vocos pretrained, 10 demo; research thêm
  `TRAINING.md`/`REPORT.md`. **Không** kèm data gốc; **không** kèm Vocos fine-tune.
- **Research/non-commercial — không production thương mại**, dataset CC-BY-NC-4.0.
- Đã xoá toàn bộ release audio test cũ; chỉ còn 2 release trên.
- Đã tải lại asset, kiểm sha256, giải nén chạy `inference.py` CPU thành công.

## 12. Xác nhận tai trên 10 câu mới (27/10/2026)

- Người dùng: **cả 10/10 câu bản Vocos mặc định ít rè hơn** bản fine-tune.
- `fresh04` (chữ **“ấm”**) ở bản mặc định vẫn hơi rè cục bộ; fine-tune rè cả âm lẫn nền.
- Đã thử `sharpen_alpha` 0 / 0,75 / 1,0 / 1,5 trên đúng câu + cụm chứa “ấm”:
  `https://instant-weblogs-reductions-separated.trycloudflare.com/fresh04_alpha/`
  Đo nhanh: alpha 1,5 có HNR cao nhất, glottalization thấp nhất; alpha 0 không xoá rè.
- **Không đổi alpha toàn cục** vì 9/10 câu còn lại đang tốt; ghi “ấm” là hạn chế cục bộ
  đã biết trong model card. Fine-tune tiếp tục bị loại.
