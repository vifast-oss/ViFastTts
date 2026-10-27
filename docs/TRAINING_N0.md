# N0 — tổng hợp quá trình training & chọn lượng dữ liệu

> Tài liệu này tóm tắt đợt **N0** (dataset `ngochuyen_voice`, model small 6,1M).
> Số đo thật trên Mac mini M6 32GB; số của base/large là **ước lượng** từ repo, không phải
> kết quả N0. Dataset CC-BY-NC-4.0 — research/non-commercial.

## 1. Pipeline đã chạy

| Bước | Việc | Thời gian / kết quả |
|---|---|---|
| 1 | Tải 8 parquet (3,27 GB) | ~7 phút |
| 2 | Giải nén WAV + audit 7.540 clip | ~2–3 phút; 21,57 h |
| 3 | Lọc text/số/ngày, dedupe, split 90/5/5 | còn 6.989 clip · 19,89 h (17,89 / 1,01 / 0,99 h) |
| 4 | MFA align 6.989 clip (`vietnamese_mfa` + G2P 1.044 OOV) | **408 s**; 6.989/6.989 TextGrid, 0 thiếu |
| 5 | Cắt segment 3–10 s, `seg_durations` | 9.546 train / 537 val / 527 holdout; 0 fail bất biến |
| 6 | Mel/F0 stats + cache v3 | ~8 phút cache train; ~1 phút val/holdout; stats ~5 phút |
| 7 | Train acoustic small 60k | **~5 h 46 phút** (0,346 s/bước, batch 8, MPS) |
| 8 | Eval val/holdout/tone/creak | ~15 phút |
| 9 | Vocos fine-tune 10k | ~1 h 50 phút (0,65 s/bước, MPS) — **đã loại vì rè** |
| — | Tổng pipeline (không tính tải) | **~8 giờ** |

Train 60k với 9.546 segment, batch 8 ≈ 1.193 bước/epoch ⇒ **~50 epoch**. Cache feature là bắt buộc;
không cache dataloader từng rất chậm (xem `docs/archive/training/TRAINING_RUN_CODELUNG.md`).

## 2. Small 6,1M cần bao nhiêu dữ liệu?

Kết quả N0: 17,89 h train sạch, một giọng, 60k bước → val/holdout 4,0 dB, nghe như thật.
Khuyến nghị thực dụng:

| Mục đích | Dữ liệu sạch (sau lọc) | Ghi chú |
|---|---:|---|
| Prototype / demo giọng | **3–6 h** | đủ để biết giọng, nhưng prosody/âm cuối dễ yếu |
| Bản dùng được | **10–15 h** | nên 40k–50k bước; kiểm tai + holdout |
| **Sweet spot single-speaker** | **15–20 h** | N0 17,9 h; 60k bước; ưu tiên sạch hơn nhiều giờ |
| Thêm dữ liệu | 25–30 h | lợi ích giảm rõ; chỉ tăng nếu val/holdout còn cải thiện |
| Multi-speaker | **30–50 h+** | cần nhiều speaker/ngữ cảnh, không chỉ tổng giờ |

**Đọc bảng cho đúng**:

- **3–7 h** = mức **tối thiểu để có demo/giọng rõ**, không phải “đủ để tốt nhất”. Nếu chỉ có
  5–7 h, vẫn train được small, nhưng nên 20k–30k bước, không nên 60k (sẽ lặp dữ liệu quá nhiều).
- **10–15 h** = bản dùng được, cần nghe + holdout.
- **15–20 h** = **sweet spot** cho single-speaker small; N0 17,9 h.
- **25–30 h+** = lợi ích giảm; chỉ tăng nếu val/holdout còn cải thiện.

Các mốc này là **kinh nghiệm + số N0**, chưa phải ablation 5/10/20 h trên cùng giọng. Muốn chốt
chính xác cho dự án, chạy 3 nhánh dữ liệu 5/10/18 h, cùng seed/bước tương đối, đo holdout + tai.

**Kết luận**: small single-speaker **15–20 h sạch là điểm hợp lý**; 5–7 h chỉ nên coi là bản
demo. Nếu có 30 h, đừng mặc định tăng bước gấp đôi — đo trước.

## 3. Base 16,4M / large 32M

Base trong repo: `component_dim 96 · hidden 256 · 6 encoder · 4 decoder` ≈ **16,4M tham số**.
Large ≈ 32M.

| Model | Dữ liệu nên có (khuyến nghị) | Bước gợi ý | Thời gian M6 (ước lượng) | Khi nào dùng |
|---|---:|---:|---:|---|
| small 6,1M | 10–20 h | 40k–60k | ~4–6 h (batch 8) | mặc định, dữ liệu vừa |
| **base 16,4M** | **30–50 h** | 40k–80k | **~10–20 h** (batch 6–8) | có ≥30 h sạch, cần thêm chất lượng |
| large 32M | 50–100 h | 80k–150k | 2+ ngày | chỉ khi dữ liệu/ngân sách đủ |

- Base với **15–20 h** như N0: **train được** nhưng chỉ là mức tối thiểu, **không tận dụng hết
  capacity**; dễ overfit và có thể không hơn small sau khi tinh chỉnh. Chỉ nên làm A/B sau khi
  small đã ổn, và tốt nhất có **30–50 h**.
- “Cùng kiến trúc” không có nghĩa cùng số giờ: khác ngôn ngữ, số speaker, domain, nhiễu, tốc độ
  nói, chất lượng alignment đều đổi. Dùng số giờ như **ngân sách ban đầu**, rồi đo learning curve
  trên chính dữ liệu; đừng suy từ model/ngôn ngữ khác.
- Ước lượng base 30–42 h cho 120k bước trên 44 h (batch 6–8) lấy từ
  `docs/TRAINING_ESTIMATES.md`; với 30–50 h và 40k–80k bước, dự trù **10–20 h** acoustic
  trên M6, chưa kể eval/vocoder.
- Large chỉ nên tính khi có ≥50–100 h và chấp nhận ≥2 ngày.

### 3.1 Thí nghiệm base N0 (27/10/2026, đang chạy)

- Config `configs/base_ngochuyen.yaml`: **cùng 17,8 h train/cache/recipe N0 small**,
  chỉ đổi dung lượng sang base **96/256/6 encoder/4 decoder** (~17,1M; 16,4M không tính postnet).
- 40.000 bước (~33,5 epoch), batch 8, cosine 40k, val 300 clip, **không** early stop;
  chọn `best` + `last` rồi chấm mel/rough/tone/CER/rè/tai.
- Probe 100 bước: **0,397 s/bước · MPS 9,1 GB**; ước tính 40k ≈ **4,5–5 h**.
- Chỉ là **thí nghiệm dung lượng**, không thay production; kết quả ghi sau khi chấm.

## 4. Mặc định suy luận N0

- **Vocos pretrained mặc định** (không fine-tune; fine-tune bị loại vì rè).
- **`sharpen_alpha = 1,5`** cho N0 (config `inference.sharpen_alpha`); người nghe chọn.
- **`pause_mode = "model"`** — model tự ngắt nghỉ; fixed pause là opt-in
  (`--fixed-pauses` / `pause_mode="fixed"`), mặc định tắt.
- Nếu dùng repo CLI: `--sharpen-alpha` không truyền sẽ lấy config N0 = 1,5.

## 5. Bài học

1. Dữ liệu sạch + MFA đúng quan trọng hơn tăng tham số: small 6,1M đã đạt 4,0 dB trên giọng mới.
2. Vocos fine-tune không tự động tốt hơn; phải nghe và đo jitter/glottalization.
3. Với single-speaker, 15–20 h là đủ; base cần 30–50 h mới đáng.
4. Luôn giữ holdout theo hash text và kiểm 5-gram trùng khi thử câu mới.


## 6. Công thức bước ↔ thời gian ↔ epoch

- `steps/epoch ≈ N_segment_train / batch_size` (với `SameNBatchSampler`, xấp xỉ).
- `thời gian ≈ steps × s/bước`; N0: 9.546 segment, batch 8 → **1.193 bước/epoch**;
  60k bước ≈ **50 epoch**; 0,346 s/bước → **5,77 h**.
- 5–7 h dữ liệu (khoảng 2.500–3.500 segment): 20k–30k bước ≈ 1,9–2,9 h; 60k sẽ là 130–190 epoch
  (quá nhiều lần lặp).
- 10 h (~5.000 segment): 40k bước ≈ 64 epoch · 3,8 h.
- 18 h (N0): 60k bước ≈ 50 epoch · 5,8 h.
- Base 16,4M: s/bước thực tế/ước lượng **0,9–1,25 s** (batch 6–8) ⇒ 40k bước ~10–14 h,
  60k ~15–21 h, 120k ~30–42 h (khớp `TRAINING_ESTIMATES.md`).

Không có con số “đúng” nếu không cố định: chất lượng dữ liệu, số speaker, độ dài segment, batch,
cache, early-stop và mục tiêu metric. Luôn ghi rõ **giờ sau lọc**, **số bước**, **batch**, **thời
gian thực** khi báo cáo.

## 7. RTF thực tế của service (27/10/2026)

Đo trên VPS Nhật, container ONNX CPU, HTTP loopback, 5 câu, không tính mạng từ trình duyệt:

- Tổng audio: **22,44 s**
- Tổng thời gian xử lý: **1,01 s**
- **RTF = 0,045** (khoảng 22 lần nhanh hơn thời gian thực)
- Từng câu: 0,032–0,092; câu đầu 0,092 do warm-up.

Đây là end-to-end (frontend + acoustic + Vocos + postprocess), không phải chỉ acoustic.


## 8. Windows

Demo ONNX có script PowerShell: `scripts/run_ngochuyen_demo.ps1` (xem README mục 0).
Training đầy đủ nên chạy trên Linux/macOS hoặc WSL; nếu dùng Windows native:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev,audio,train,onnx]"
```

MFA/aligner và một số tool dòng lệnh có thể cần WSL/conda; phần train PyTorch chạy native được.
