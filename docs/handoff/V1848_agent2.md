# V18.48 — Agent 2: pilot L_con (mượt tần số)

> **Trạng thái: DỪNG — ĐÓNG BĂNG LẠI.** Không đổi production; P2 vẫn là production.
> **Commit gốc của vòng**: `5598514` · **Code cuối trước hồ sơ**: `338bd47`
> · **Tệp đặc tả**: `V1848_agent0.md` + `DECISIONS.md` mục V18.48.
> Báo cáo này là commit hồ sơ.

## 0. Tóm tắt

| Mã | Kết quả | Trạng thái |
|---|---|---|
| V1848.A1 | `L_con` + 5 unit test; `finetune_adv --contrast-weight` | **XONG** (`8a0ec8a`) |
| V1848.A3 | Probe 100; chọn **w = 1,0338** (L_con 22,5 % tổng loss), commit trước pilot | **XONG** (`8f25e85`) |
| V1848.A2 | PILOT + CONTROL, mỗi 2.000 bước, cùng seed/config | **XONG** (`runs/v1848_{pilot,control}`) |
| V1848.A4 | ΔBAK TF **+0,0229**, CI [−0,0198; 0,0600] ⇒ **không đạt cổng 1** | **KHÔNG KẾT LUẬN** (`338bd47`) |
| V1848.A5 | Chunk **+0,0537**, CI [0,0143; 0,0939]; L1 +0,14 %; không lạ | **báo cáo, không phải cổng** |
| V1848.A6 | Không mở: A4 không đạt | **ĐÓNG BĂNG LẠI** |

- `L_con` **làm đúng việc của nó**: CR tăng rõ (PILOT 0,828 vs CONTROL 0,738).
- Nhưng **BAK TF không tăng đủ** (CI chứa 0) ⇒ theo luật: **không kết luận, đóng băng, không thử w khác**.
- Chunk BAK tăng +0,0537 (CI dưới >0) là tín hiệu phụ **đáng chú ý**, nhưng **không** thay cổng A4.
- Không đổi production; không dựng trang nghe mù.

## 1. A1 — L_con

`src/vifasttts/models/contrast_loss.py`:
- `spectral_contrast(X)` = trung bình theo bin của `max−min` trong cửa sổ 5 bin, dải ≤4 kHz.
- `contrast_loss(P,T,voice)` = trung bình `|contrast_f(P)−contrast_f(T)|` trên frame hữu thanh.
- Dùng `max/min` trực tiếp (subgradient); **không** dùng logsumexp vì probe gradient ổn định.

Unit test `tests/test_contrast_loss.py` — **5 pass**:
- P = T ⇒ 0.
- P = T làm mượt tần số ⇒ >0.
- Gradient hữu hạn.
- Voice rỗng ⇒ 0, finite.
- Shape/finite của contrast.

`tools/finetune_adv.py` thêm `--contrast-weight`, cột `contrast` trong `train_log.csv`, loss cộng vào tổng G.

## 2. A3 — probe và w

- Probe 100 bước, `--contrast-weight 0.1`, `d_warmup=10`, seed 42, từ P2 EMA.
- 50 bước cuối: `rec` **1,52105** · `contrast` **0,39354** · `adv` **−0,39904** · `adv_eff` **0,3**.
- Chọn **w = 1,0338** để `w·contrast / (rec + eff·adv + w·contrast)` = **22,5 %**.
- Đã commit w **trước** pilot (`8f25e85`); không đổi sau kết quả.

## 3. A2 — PILOT vs CONTROL

Cùng P2 EMA, cùng seed 42, cùng dữ liệu/thứ tự batch/lr/adversarial/EMA; chỉ khác `--contrast-weight`.
Đánh giá bằng **EMA** tại bước 2.000.

| Chỉ số | P2 | CONTROL | PILOT |
|---|---:|---:|---:|
| BAK TF | 3,925038 | 3,937453 | **3,960303** |
| BAK chunk | — | 3,793433 | **3,847113** |
| CR trung vị | 0,706650 | 0,738337 | **0,827801** |
| L1 mel TF | — | 0,810911 | 0,812037 |

- `CONTROL` so P2: BAK TF +0,0124 (<0,05) ⇒ không có hiện tượng "train thêm tự cải thiện".
- `PILOT` so `CONTROL`:
  - **ΔBAK TF = +0,02285**, CI95 **[−0,0198; 0,0600]**.
  - **ΔCR trung vị = +0,08946**, CI95 **[0,0775; 0,0929]**.
  - **ΔBAK chunk = +0,05368**, CI95 **[0,0143; 0,0939]**.
  - L1 mel tương đối **+0,14 %**.

## 4. A4/A5 — cổng

| Cổng | Kết quả |
|---|---|
| (1) ΔBAK TF ≥0,05 và CI dưới >0 | ❌ +0,0229; CI [−0,0198; 0,0600] |
| (2) CR PILOT > CONTROL, CI hiệu >0 | ✅ +0,0895; CI [0,0775; 0,0929] |
| (3) CR PILOT ≤1,05 | ✅ 0,8278 |
| **A4** | **KHÔNG ĐẠT** |
| A5 lạ? | Không: chunk tăng, L1 +0,14 %, CR ≤1,05, CONTROL không tự tăng |

- Theo V1848.A4: CI chứa 0 ⇒ **không kết luận, đóng băng lại, không tự thử w khác**.
- Chunk +0,0537 có ý nghĩa thống kê nhưng **không phải cổng**; không được dùng để đổi production.
- Quan sát: `L_con` tăng CR đúng hướng nhưng BAK TF không tăng đủ; có thể 2.000 bước chưa đủ,
  hoặc BAK TF không nhạy với thay đổi CR trong vùng này. Không có kết luận nhân quả.

## 5. TỰ QUYẾT KHÁC ĐẶC TẢ

1. **Probe dùng `d_warmup=10`** thay vì 300 của P2, để 100 bước có cập nhật G và kiểm gradient L_con.
   Pilot/Control dùng `d_warmup=300` đúng P2. Ghi rõ vì probe không phải "training config P2".
2. **w chọn theo tổng loss có cả adversarial** (không chỉ rec): w=1,0338 cho 22,5 %.
   Nếu chỉ tính rec, w sẽ khác; đã dùng đúng chữ "tổng loss".
3. **L1 mel** báo theo mel z-score, tương đối PILOT/CONTROL; không phải L1 dB.
4. **A5 chunk dương** được báo như tín hiệu phụ; không dùng để mở cổng hay đổi production.
5. Không chạy w thứ hai; không dựng trang nghe mù (A4 không đạt).

## 6. Git log vòng này

```
7504ffd đăng ký trước V1848
8f25e85 chốt w=1,0338 (L_con 22,5%) trước pilot
8a0ec8a L_con + test; finetune_adv --contrast-weight
338bd47 chấm PILOT vs CONTROL — A4 không kết luận; A5 chunk +0,054
```

## 7. Việc tiếp

1. **Giữ đóng băng chất lượng**, production P2; không train thêm, không thử w khác.
2. Chunk +0,0537 là tín hiệu phụ; nếu A0 muốn theo, phải đăng ký vòng mới (nghe mù/regression) —
   không tự mở.
3. Muốn thử lại L_con: cần giả thuyết mới + w mới đăng ký trước + duyệt ngân sách; không dùng lại
   kết quả này để tuyên bố.
4. ONNX vẫn đóng băng.

## 8. Test & trạng thái

- `pytest -q -rs`: **2.552 passed, 23 skipped** (5 test L_con mới; ONNX đóng băng).
- `ruff check .`: sạch.
- **Trạng thái: DỪNG — ĐÓNG BĂNG LẠI.**
