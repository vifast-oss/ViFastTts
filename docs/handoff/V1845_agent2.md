# V18.45 — Agent 2: xác nhận C_lo, tách over-smoothing, đo cao độ

> **Trạng thái: DỪNG, CHỜ ĐỌC.** Không train, không đổi production.
> **Commit gốc của vòng**: `244c40e` · **Code cuối trước hồ sơ**: `66f2ac2`
> · **Tệp đặc tả**: `V1845_agent0.md` + `DECISIONS.md` mục V18.45.
> Báo cáo này là commit hồ sơ.

## 0. Tóm tắt

| Mã | Kết quả | Trạng thái |
|---|---|---|
| V1845.A4 | **KHÔNG XÁC NHẬN ĐƯỢC**: Δac bộ mới **0,0568 < 0,15**; `C_lo` recovery 1,08 nhưng CI95 [−0,77; 2,90] | **TRƯỢT** (`9e03ed6`) |
| V1845.A5 | Cửa sổ **5**; `Recovery(C_lo)` 0,994, `C_lo_s` 0,785; tỉ lệ **0,789** ⇒ **KHÔNG phải over-smoothing** | **TRƯỢT (điều kiện 3)** (`f5bd672`, `1fbd269`) |
| V1845.A6 | F0 lỗi **0 %**; ρ RMSE **0,021** [−0,221; 0,259]; vuv **0,054** [−0,192; 0,294]; std **0,088** [−0,145; 0,313] ⇒ **không chỉ số nào liên quan** | **KHÔNG ĐẠT** (`66f2ac2`) |
| V1845.A7 | Cổng train: (1) A5 V18.44 đạt; (2) A4 trượt; (3) A5/A6 trượt; (4) chưa duyệt ngân sách | **ĐÓNG** |

- **Không mở V18.45-train.** Cả ba nút (2)(3)(4) đều chưa đạt.
- `C_lo` là giả thuyết **không được xác nhận** trên bộ mới; kết quả cũ 0,97 không tái lập.
- Không dùng UTMOS ở bất kỳ kết luận nào.

## 1. A4 — xác nhận `C_lo` trên 40 câu mới

40 câu held-out mới, khác 40 câu A4 V18.43; đã ghi danh sách vào `DECISIONS.md` trước khi vocode.
Bộ thực tế: 9 video, 35 parent; 4 câu/video + 4 bổ sung; có nhiều segment ngắn (1–3 âm tiết).

### 1.1 Đối chứng

| Đối chứng | BAK | Tham chiếu | Lệch |
|---|---:|---:|---:|
| `C_all` | 3,945826 | B 3,945826 | 0,000000 |
| `C_none` | 3,889036 | C 3,889036 | 0,000000 |

- Đối chứng **đạt tuyệt đối**; pipeline vocode/normalize nhất quán.

### 1.2 Kết quả

| Biến thể | BAK trung bình |
|---|---:|
| B (mel gốc) | 3,945826 |
| C (P2 TF) | 3,889036 |
| `C_lo` (≤4 kHz lấy B) | 3,950585 |
| `C_hi` (>4 kHz lấy B) | 3,853576 |

- **Δac = 0,056790** — dưới ngưỡng 0,15 rất xa.
- `Recovery(C_lo)` = **1,0838**, CI95 **[−0,7704; 2,8991]**; `Recovery(C_hi)` = **−0,6244**,
  CI95 [−8,8654; 7,4976].
- Tổng `lo + hi` = **0,4594** (ngoài [0,5; 1,5]).
- Median hiệu `BAK(C_lo) − BAK(C)` theo câu = **0,0541**.
- **Verdict: KHÔNG XÁC NHẬN ĐƯỢC — Δac < 0,15** (đúng luật: báo, không phải lạ).
- Diễn giải: bộ mới **không có khoảng cách acoustic đủ lớn**; `C_lo` vượt cả B nhưng CI quá rộng,
  không thể dùng để xác nhận. Kết quả 0,97 trên bộ cũ **không tái lập**.

## 2. A5 — tách over-smoothing

### 2.1 Cửa sổ chọn trước khi chấm BAK

- 80 câu (40 cũ + 40 mới); chỉ dùng GV, **chưa chấm BAK**.
- Mục tiêu GV ratio: `<1k` **0,8332**, `1–4k` **0,8656**.
- Cửa sổ lẻ được chọn: **5**; đạt `<1k` **0,8171**, `1–4k` **0,8519**; max diff **0,0161** ≤ 0,03
  ⇒ không xấp xỉ. Đã ghi vào `DECISIONS.md` và commit **trước** khi chấm BAK (`1fbd269`).

### 2.2 Kết quả 80 câu

| Biến thể | BAK trung bình | Recovery |
|---|---:|---:|
| B | 3,967868 | — |
| C | 3,815444 | — |
| `C_lo` (B thô ≤4 kHz) | 3,966940 | **0,9939** |
| `C_lo_s` (B làm mượt, cửa sổ 5) | 3,935022 | **0,7845** |

- **Δac (80 câu) = 0,152424** — vừa trên 0,15.
- **Tỉ lệ `Recovery(C_lo_s) / Recovery(C_lo)` = 0,7893**.
- Luật: ≤0,3 ⇒ over-smoothing chính; ≥0,7 ⇒ không phải; ở giữa ⇒ hỗn hợp.
  **0,7893 ≥ 0,7 ⇒ KHÔNG PHẢI over-smoothing** (cách biên hỗn hợp 0,089).
- Nghĩa là làm mượt thời gian chỉ làm mất ~21 % mức hồi phục; phần lớn thiếu hụt dải thấp
  **không phải** do mất chi tiết thời gian.
- Không có hiện tượng `C_lo_s > C_lo + 0,1`.

## 3. A6 — cao độ (chỉ định hướng)

80 câu; F0 trích thành công **80/80** (failure 0 %). Frame hữu thanh chung để tính RMSE/std.

| Chỉ số | ρ Spearman với `BAK(B)−BAK(C)` | CI95 | Liên quan? |
|---|---:|---|---|
| RMSE F0 C vs A (cent) | 0,0213 | [−0,2212; 0,2594] | Không |
| Tỉ lệ sai vuv | 0,0538 | [−0,1924; 0,2936] | Không |
| Tỉ số std F0 C/A | 0,0876 | [−0,1454; 0,3127] | Không |

- Không chỉ số nào đạt ρ ≥ 0,4 và CI không chứa 0 ⇒ **cao độ không liên quan** đến hiệu BAK
  trong bộ 80 câu này.
- Đây chỉ là đo phụ, không phải cổng chính; nhưng nó cũng không mở được điều kiện 3 của A7.

## 4. A7 — cổng train

| Điều kiện | Kết quả |
|---|---|
| (1) A5 V18.44 XÁC NHẬN | ✅ đạt |
| (2) V1845.A4 ĐẠT | ❌ Δac 0,0568 < 0,15 |
| (3) A5 over-smoothing/hỗn hợp **hoặc** A6 cao độ liên quan | ❌ A5 "không phải"; A6 không liên quan |
| (4) Người dùng duyệt ngân sách | ❌ chưa |

⇒ **Không train, không probe.** Kiến trúc V18.45 không được chốt.

## 5. TỰ QUYẾT KHÁC ĐẶC TẢ

1. **Sửa danh sách 40 câu mới trước khi vocode**: bản nháp đầu (đã commit `997a82a`) không khớp
   file chọn thực tế (`VeU_85bZlrY_0003__s01` không có trong holdout). Đã thay bằng danh sách chọn
   thật (9 video, 35 parent) **trước khi chạy A4**; không có audio nào được chấm bằng danh sách nháp.
   Commit đăng ký đã được amend; báo cáo ghi rõ.
2. **A4 bộ mới** dùng 4 câu/video + 4 bổ sung, không stratify độ dài; nhiều segment 1–3 âm tiết.
   Đây là lựa chọn hợp lệ nhưng có thể là lý do Δac nhỏ; ghi nhận, không đổi sau khi thấy số.
3. **A5 Δac 80 câu = 0,1524** chỉ vừa trên 0,15; tỉ lệ 0,7893 chỉ vừa trên 0,7. Cả hai **sát biên**;
   không đổi ngưỡng, chỉ báo để A0 biết.
4. **A6** dùng `extract_features` của repo (pyworld) trên 24 kHz; 0 lỗi; không thay bộ trích.
5. **Không dùng UTMOS**; không đụng ONNX; không train.

## 6. Việc tiếp

1. **A0 quyết `C_lo`**: với A4 mới Δac 0,057 và CI rộng, giả thuyết `C_lo` **không được xác nhận**.
   Đề nghị đóng `C_lo` trừ khi có bộ mới với Δac ≥ 0,15 và chọn câu độc lập.
2. **A5/A6 nói**: không phải over-smoothing thời gian, không phải cao độ. Nếu vẫn muốn tìm nguồn,
   hướng còn lại là **phổ/buzz trong dải thấp** hoặc **đường chunk/fade/loudness**; phải đăng ký phép đo mới.
3. **Không train**; V18.45-train vẫn đóng. Ngân sách chưa duyệt.
4. ONNX giữ đóng băng.

## 7. Test & trạng thái

- `pytest -q -rs`: **2.547 passed, 23 skipped** (ONNX đóng băng), ~42 s.
- `ruff check .`: sạch.
- **Trạng thái: DỪNG, CHỜ ĐỌC.** A4/A5/A6 đều không mở được cổng train.
