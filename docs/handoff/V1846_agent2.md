# V18.46 — Agent 2: bộ câu dài, cơ chế dải thấp, đường chunk

> **Trạng thái: DỪNG — ĐÓNG BĂNG CHẤT LƯỢNG ACOUSTIC** (theo V1846.A6).
> Không train, không đổi production; production giữ **P2**. ONNX vẫn đóng băng.
> **Commit gốc của vòng**: `2306062` · **Code cuối trước hồ sơ**: `90ceda1`
> · **Tệp đặc tả**: `V1846_agent0.md` + `DECISIONS.md` mục V18.46.
> Báo cáo này là commit hồ sơ.

## 0. Tóm tắt

| Mã | Kết quả | Trạng thái |
|---|---|---|
| V1846.A0 | Luật không amend/force-push; vòng này dùng toàn commit mới | **XONG** |
| V1846.A2 | **Δac = 0,149456 < 0,15** (thiếu **0,000544**); `C_lo` recovery 0,943, CI [0,7502; 1,1083] | **ĐÓNG `C_lo`** (`7f181fa`) |
| V1846.A3 | ρ độ dài = **0,0788**, CI [−0,1135; 0,2676] | **không liên quan** (`1b2462f`) |
| V1846.A4 | **Mượt tần số CHÍNH** (R_f −1,9694; R_m −0,5353); Δac 120 câu 0,1518 | **thông tin, không mở cổng** (`75399ea`, `67e2401`) |
| V1846.A5 | BAK(C) − BAK(P) = **+0,0328**, CI [−0,0260; 0,0919] | **không đủ bằng chứng chunk gây rè** (`90ceda1`) |
| V1846.A6 | (1) A2 trượt; (2) A4 có cơ chế nhưng (1) hỏng; (3) chưa duyệt ngân sách | **ĐÓNG BĂNG CHẤT LƯỢNG ACOUSTIC** |

- **Không train, không probe.**
- `C_lo` và toàn bộ hướng "rè do acoustic dải thấp" **đóng** theo luật A2.
- Đường chunk **không** bị kết luận là nguồn rè thêm.
- Chất lượng acoustic **đóng băng**: chỉ sửa regression, giữ P2.

## 1. A2 — 40 câu dài

40 câu held-out mới: 9 video, tối đa 5 câu/video, mỗi câu ≥3 s và ≥12 âm tiết; danh sách ghi
trước vocode trong `DECISIONS.md` (`9ea41c5`).

| Tầng | BAK trung bình |
|---|---:|
| B (mel gốc) | 4,019541 |
| C (P2 TF) | 3,870085 |
| `C_all` | 4,019541 |
| `C_none` | 3,870085 |
| `C_lo` | 4,011014 |
| `C_hi` | 3,892574 |

- **Δac = 0,149456** — dưới 0,15 đúng **0,000544** (sát ngưỡng).
- `Recovery(C_lo)` = **0,9430**, CI95 **[0,7502; 1,1083]**, cận dưới >0,3.
- `Recovery(C_hi)` = 0,1505; tổng `lo+hi` = **1,0934** ∈ [0,5; 1,5].
- Đối chứng `C_all`/`C_none` khớp tuyệt đối.
- **Verdict theo luật: ĐÓNG `C_lo`** vì Δac < 0,15. Đây là **trượt sát ngưỡng**, không phải bị bác bỏ;
  báo A0, nhưng không thử bộ câu khác.

## 2. A4 — cơ chế dải thấp (120 câu)

Cửa sổ làm mượt trục tần số chọn **trước khi chấm BAK**: **3**; độ tương phản C mục tiêu 1,054477,
đạt 0,972691, sai số tương đối **7,76 %** >5 % ⇒ đánh dấu **"xấp xỉ"** (`67e2401`).

| Biến thể | BAK trung bình | Recovery |
|---|---:|---:|
| B | 3,985092 | — |
| C | 3,833280 | — |
| `C_lo` (B thô ≤4 kHz) | 3,981631 | **0,9772** |
| `C_lo_f` (B mượt tần số) | 3,534306 | **−1,9694** |
| `C_lo_m` (C + lệch mức) | 3,752008 | **−0,5353** |

- Δac 120 câu = **0,151812**.
- Luật: `R_f ≤ 0,3×R_lo` ⇒ mượt tần số **CHÍNH**: **đúng** (−1,97 ≤ 0,293).
  `R_m ≥ 0,7×R_lo` ⇒ lệch mức **CHÍNH**: **sai** (−0,535 < 0,684).
- **Kết luận A4: mượt tần số là chính; lệch mức không phải.**
- Diễn giải thận trọng: `C_lo_f` còn **xấu hơn C** (3,534 < 3,833), tức làm mượt B phá mất lợi ích;
  điều này phù hợp với "thiếu độ tương phản phổ dải thấp", nhưng **không** đo trực tiếp mức mượt của model.
- Vì A2 đã đóng `C_lo`, A4 chỉ là **thông tin cơ chế**, không mở cổng train.

## 3. A3 — độ dài câu

120 câu (80 cũ + 40 dài), Spearman giữa `BAK(B)−BAK(C)` và thời lượng câu:

- ρ = **0,0788**; CI95 **[−0,1135; 0,2676]**; không đạt ρ ≥0,3 + CI không chứa 0.
- Độ dài **không** giải thích chênh lệch Δac giữa các bộ.

## 4. A5 — đường chunk

40 câu dài; C = P2 TF, P = CLI chunk mode mặc định (dự đoán thời lượng, fade/ghép/LUFS), cả hai −16 LUFS.

- `BAK(C) − BAK(P)` = **+0,0328**; CI95 **[−0,0260; 0,0919]**.
- Không đạt ngưỡng "chunk gây rè thêm" (≥0,10 và cận dưới >0); không rơi vào "lạ" (≤−0,10).
- **Verdict: KHÔNG KẾT LUẬN — không đủ bằng chứng chunk gây rè.** Không mở vòng sửa chunk.

## 5. A6 — cổng train / đóng băng

| Điều kiện | Kết quả |
|---|---|
| (1) A2 ĐẠT | ❌ Δac 0,149456 < 0,15 |
| (2) A4 có ≥1 cơ chế CHÍNH | ✅ mượt tần số (nhưng (1) đã hỏng) |
| (3) Duyệt ngân sách | ❌ chưa |

- Theo V1846.A6: **A2 trượt + A5 không đạt ⇒ ĐÓNG BĂNG CHẤT LƯỢNG ACOUSTIC**,
  chỉ sửa regression, giữ P2.
- Không train, không probe; không mở vòng sửa chunk.

## 6. TỰ QUYẾT KHÁC ĐẶC TẢ

1. **A2 chọn 4 câu/video + 4 câu dài nhất còn lại**, tất cả 9 video, tối đa 5/video; chỉ theo độ dài/video,
   không xem BAK. Danh sách ghi trước vocode (`9ea41c5`).
2. **A2 sát ngưỡng 0,000544**: giữ nguyên luật, đóng `C_lo`; báo A0 để biết, không thử bộ khác.
3. **A4 cửa sổ 3 xấp xỉ 7,76 %** (>5 %): dùng cửa sổ gần nhất, đánh dấu "xấp xỉ" đúng luật.
4. **A4 `C_lo_f` thấp hơn C**: báo như hiện tượng, không đổi nhãn cơ chế; nhãn "mượt tần số chính"
   là theo luật đăng ký trước.
5. **A5** dùng `Synthesizer.synthesize` (CLI chunk mode), `target_lufs=-16`, `max_chars=400`;
   không tự thêm hậu xử lý.
6. **Không amend/force-push** trong vòng này; toàn bộ commit mới.

## 7. Git log vòng này

```
9ea41c5 v2(v18.46): đăng ký trước V1846 + 40 câu dài; luật không amend
7f181fa v2(v18.46): A2 bộ dài — Δac 0,149456 < 0,15; đóng C_lo (sát ngưỡng 0,0005)
67e2401 v2(v18.46): A4 chốt cửa sổ tần số 3 (xấp xỉ 7,76%) trước khi chấm BAK
75399ea v2(v18.46): A4 cơ chế — mượt tần số chính (R_f -1,97; R_m -0,535); Δac 0,1518
1b2462f v2(v18.46): A3 độ dài — ρ 0,079, không liên quan
90ceda1 v2(v18.46): A5 chunk vs TF — +0,033, CI chứa 0; không thêm rè
```

## 8. Việc tiếp

1. **Đóng băng chất lượng acoustic**: chỉ sửa regression, giữ P2; không train.
2. `C_lo` đã đóng; không thử thêm bộ câu.
3. A4 ghi nhận "mượt tần số" là cơ chế tiềm năng nhưng **không hành động** khi đóng băng.
4. A5 không đủ bằng chứng chunk gây rè; không mở vòng sửa chunk.
5. Muốn mở lại: cần cơ chế mới + đăng ký trước + duyệt ngân sách; không dùng lại kết quả A2 sát ngưỡng.

## 9. Test & trạng thái

- `pytest -q -rs`: **2.547 passed, 23 skipped** (ONNX đóng băng).
- `ruff check .`: sạch.
- **Trạng thái: DỪNG — ĐÓNG BĂNG CHẤT LƯỢNG ACOUSTIC.**
