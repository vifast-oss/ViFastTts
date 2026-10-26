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
- Manifest: `data/ngochuyen/manifests/{train,val,holdout}_clean_v2_dur_seg_slot4.jsonl`.

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
