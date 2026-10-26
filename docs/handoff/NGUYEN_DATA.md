# N0 — dữ liệu & huấn luyện small trên `ngochuyen_voice`

> **Trạng thái hiện hành**: xem `docs/handoff/TRANG_THAI.md`.
> Tệp này là hồ sơ dữ liệu/kế hoạch của đợt **N0** (dataset mới), không thay V18.52.
> **Không đổi production, không đụng ONNX.** Dataset CC-BY-NC-4.0 → chỉ dùng nội bộ/nghiên cứu.

## 1. Nguồn

- HF: `pnnbao-ump/ngochuyen_voice`, revision `1ebbfbd1fb828dfd41bff8b1645ad9e56cfc614a`.
- 7.540 clip WAV 24 kHz mono PCM16; 3,27 GB parquet; **21,569 h**.
- Trường: `audio`, `transcription`, `file_name`. Không có speaker ID; một giọng nữ.
- License **CC-BY-NC-4.0** (phi thương mại). Không dùng cho production thương mại.

## 2. Audit dữ liệu (đo trên 7.540 clip)

| Chỉ số | min / p1 / median / p99 / max |
|---|---|
| duration (s) | 2,02 / 2,69 / 9,78 / 19,57 / 20,00 |
| speech rate (syl/s) | 2,15 / 3,14 / 4,25 / 5,07 / 5,56 |
| peak | 0,51 / 0,57 / 0,66 / 0,76 / 0,84 |
| silence ratio | 0,078 / 0,110 / 0,204 / 0,346 / 0,473 |
| lead silence (s) | 0,02 / 0,04 / 0,08 / 0,14 / 0,16 |
| tail silence (s) | 0,20 / 0,22 / 0,48 / 0,54 / 0,56 |

- **Không clip** (clip_ratio = 0 toàn bộ); DC ≈ 0; không có file lỗi.
- 23 clip trùng audio; 8 clip trùng text; 490 clip có ít nhất 1 âm tiết frontend fallback
  (chủ yếu tên tiếng Anh/thương hiệu); 32 clip mã trộn chữ+số; 1 clip tốc độ bất thường.
- Sửa trước khi parse: ngày `d/m/yyyy` → `ngày d tháng m năm yyyy`; `d/m` → ngày/tháng;
  số 0 đứng đầu (`02` → `2`); `->` → `đến`; khoảng số `2020-2021` → `2020 đến 2021`.
  (Frontend gốc đọc `02` thành “không hai”, `06/5` thành “sáu phần năm” — đã đo.)

## 3. Lọc + split (đăng ký trước)

Giữ khi: parse **VALID 100%**, không mã trộn chữ+số, 2–20 s, tốc độ 2,5–6,0 syl/s,
peak <0,95, không trùng audio/text. Chia **90/5/5** theo hash text (seed 42), không rò rỉ câu trùng.

| split | clip | giờ | âm tiết |
|---|---:|---:|---:|
| train | 6.291 | 17,894 | 275.641 |
| val | 349 | 1,014 | 15.679 |
| holdout | 349 | 0,985 | 15.091 |
| **giữ** | **6.989** | **19,893** | **306.411** |

Loại: 487 parse không sạch · 32 mã trộn · 23 audio trùng · 8 text trùng · 1 tốc độ.

## 4. Alignment + segment

- MFA 2.2.17 (env riêng `~/mfa_env`), acoustic `vietnamese_mfa`, dictionary gốc + G2P
  `vietnamese_mfa_g2p` cho 1.044 OOV (2.835 pronunciations); 8 từ hiếm bổ sung tay.
- Align `--single_speaker --beam 100 --retry_beam 400`, 6 job.
- `mfa_to_durations` → `durations/gaps/lead/pauses`; cắt 3–10 s tại pause, `max_gap 60`,
  `tail_cap 67`, sàn 0,25 s; `seg_durations` hybrid như v32.
- Manifest: `data/ngochuyen/manifests/{train,val,holdout}_dur_seg_slot4.jsonl`.

**Kết quả S1 (đã đo):** MFA giữ **6.989/6.989** clip, 0 drop; cắt thành
**9.546 train / 537 val / 527 holdout segment** (17,796 / 1,009 / 0,980 h).
`seg_durations`: 0 fail bất biến; 367/275.640 âm tiết fallback rule (0,13%); tail gap ≤60 frame.
Mel stats 800 clip / 623.606 frame; f0 stats R5b 2.500 segment (log-F0 mean 5,390 ≈ 219 Hz).
**Lỗi đã sửa trong chain:** `compute_f0_stats.py` sinh schema DCT cũ (thiếu `shape_mean`) →
train dừng; đã thay bằng `r5b_segment_stats.py` (schema `r5b-v2`) trước khi train.

## 5. Train (đăng ký trước)

- Kiến trúc **v2_slot5 small** (6,1M: dim 64 · hidden 192 · 4 encoder · 2 decoder), giữ nguyên
  recipe b8: batch 8, LR 2e-4 cosine 60.000 bước, phase A 2.000, patience 0.
- Cache v3 riêng `cache/ngochuyen_v2`; stats mel/f0 tính trên train.
- Chọn checkpoint cuối theo **L1 + độ nét + thanh + rè + CER + tai**, không chỉ L1.
- Không train adversarial, không đổi kiến trúc trong đợt này.

**Cổng tối thiểu**
1. Train hội tụ: val mel L1 giảm ≥15% so bước 1.000; không NaN/abort.
2. Checkpoint cuối có `val_rough` và `tone_ruler` không tệ hơn checkpoint giữa đáng kể.
3. Nghe mù 40 câu holdout: bản mới thắng **P2 zero-shot** trên cùng câu (ưu tiên tự nhiên/ít rè).
4. Không tăng rè so với chính nó ở các câu có coda tắc/thanh nặng (đo `eval_creak`).

## 6. Không làm

- Không ghi đè `data/codelung/`, cache cũ, runs cũ, ONNX/production.
- Không dùng UTMOS; không mở lại cổng C_lo/L_con.

## 7. Kết quả acoustic 60k (27/10/2026)

- Checkpoint: `runs/acoustic_ngochuyen/best.pt`, **step 60.000**,
  sha256 `d1b21642…f640070`; arch `v2_slot5`; train từ đầu (không warm-start).
- History: `val_mel_voiced` **0,26340**, `val_rough` **0,7624**; plateau từ ~44k (0,266).
- **Val 300 clip** (tf_seg): mel L1 z **0,2954** · raw 0,4585 · **4,0 dB** · VUV 0,987 ·
  duration MAE 1,33 frame · F0 median 67–156 cents (SAC xấu nhất 156).
- **Holdout 300 clip** (không dùng train/val): mel z **0,2980** · raw 0,4626 · **4,0 dB** ·
  VUV 0,987 · duration MAE 1,37 frame; **khớp val** ⇒ không thấy overfit theo clip.
- **Free-run 80 holdout** (Vocos pretrained): mel **16,57 dB** · length ratio **0,999** ·
  VUV 0,9887 · duration MAE 1,39 frame · pause F1 **0,8247** · RTF 0,003.
- **P2 zero-shot cùng 80 câu**: mel **28,31 dB** · length 0,960 · duration MAE 3,52 frame ·
  pause F1 **0,5098** ⇒ model mới giảm mel 11,7 dB, nhịp tốt hơn rõ.
- **Thanh điệu** (thước R5b train riêng trên giọng mới): thật **0,9835** · copy-synthesis
  **0,9784** · free-run **0,9743** (80 clip, 2.362 âm tiết) ⇒ mất 0,0092 tuyệt đối so thật.
- **Rè** (80 clip, CPU): NGÃ ΔHNR +1,86 dB · Δjitter −0,0106; NẶNG +0,30 dB · +0,0143;
  không thấy tăng rè theo thanh nặng.

**Demo A/B** (24 câu holdout, audio thật + model mới + P2 zero-shot, Vocos pretrained):
`artifacts/listen_ngochuyen/ab/index.html` · key `artifacts/ngochuyen/ab_key.json`.

**Vocos fine-tune** trên 17,9 h giọng mới (10k bước, MPS, `runs/vocoder_ngochuyen/last.pt`):
copy-synthesis 100 holdout clip **mel L1 0,1167** so pretrained **0,1432** (−18,5%);
F0 85,2 vs 88,9 cents; VUV 0,0223 vs 0,0206; clipping ~0. Thanh điệu free-run với Vocos
fine-tune **0,9749** (A 0,9835 · B 0,9784). **Không dùng fine-tune** (nghe còn rè); demo
chính dùng Vocos pretrained mặc định; **không đổi production/ONNX**.

**Nghe**:
- A/B mù (thật · mới · P2; Vocos pretrained): `/ab/index.html`
- Model mới + Vocos pretrained: `/new/index.html`
- Model mới + Vocos fine-tune 10k: `/new_vocos/index.html`
- P2 zero-shot: `/p2/index.html`
- Link public: `https://instant-weblogs-reductions-separated.trycloudflare.com/`


## 8. Tai người — A/B (27/10/2026)

- 24/24 câu: **model mới thắng 24, P2 zero-shot 0, hòa 0** (CSV người dùng).
- A/B dùng **Vocos pretrained mặc định**, không dùng Vocos fine-tune.
- Nhận xét: đọc như thật, không rè, không nhiễu.
- **Quyết định tạm**: giữ Vocos mặc định; Vocos fine-tune 10k chỉ để nghe riêng, chưa chốt.

## 9. Câu mới ngoài train — chốt Vocos (27/10/2026)

- 10 câu tự soạn, 5-gram trùng với train/val/holdout = **0**.
- Nghe: **Vocos fine-tune 10k còn rè**; bản pretrained mặc định sạch hơn.
- Đo 10 câu: jitter mean 0,0664 (fine-tune) vs **0,0630** (mặc định);
  glottalization 0,00486 vs **0,00227**; HNR 0,755 vs 0,763.
- **Chốt: dùng Vocos pretrained mặc định**; fine-tune chỉ giữ để đối chiếu.


## 10. Chính sách ngắt nghỉ — mặc định model tự nghỉ (27/10/2026)

- Dữ liệu N0 sạch, model tự đặt pause đúng; **mặc định `pause_mode="model"`**.
- Nghỉ cố định **chỉ bật khi yêu cầu**:
  - API: `Synthesizer.synthesize(..., pause_mode="fixed")` hoặc module `synthesize(..., pause_mode="fixed")`;
  - CLI: `--fixed-pauses` cho `synthesize`, `synthesize-onnx`, `synthesize-batch`;
  - HTTP: `{"pause_mode":"fixed", ...}`.
- `--steady` giữ làm alias cũ nhưng ẩn; mặc định vẫn tắt.
- Khi fixed: chặn pause model (`gate 1.01`), chèn phẩy 0,25 s · chấm/hỏi/than 0,55 s
  (chỉnh `--pause-comma/--pause-period/--pause-default`).
- Test: `tests/test_steady_mode.py` kiểm mặc định model, fixed opt-in, invalid mode;
  `tests/test_server.py` kiểm payload mặc định/fixed.

## 11. Xác nhận 10 câu mới (27/10/2026)

- **10/10** câu: Vocos pretrained mặc định ít rè hơn fine-tune.
- `fresh04` chữ **“ấm”**: bản mặc định hơi rè cục bộ; fine-tune rè âm + nền.
- Đã thử alpha 0/0,75/1,0/1,5; không thấy alpha thấp xoá rè; giữ 1,5 toàn cục.
- Kết luận: Vocos pretrained mặc định; fine-tune chỉ đối chiếu.
