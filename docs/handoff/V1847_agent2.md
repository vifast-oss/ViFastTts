# V18.47 — Agent 2: đo trực tiếp độ tương phản phổ ≤4 kHz

> **Trạng thái: DỪNG — CHỜ NGƯỜI DÙNG DUYỆT PILOT.** Không train, không đổi production.
> **Commit gốc của vòng**: `7d39ae2` · **Code cuối trước hồ sơ**: `da95507`
> · **Tệp đặc tả**: `V1847_agent0.md` + `DECISIONS.md` mục V18.47.
> Báo cáo này là commit hồ sơ.

## 0. Tóm tắt

| Mã | Kết quả | Trạng thái |
|---|---|---|
| V1847.A0 | Chấp nhận V18.46: `C_lo` đóng, chất lượng acoustic đóng băng, giữ P2 | **XONG** |
| V1847.A1 | Ghi hồ sơ: cổng Δac ≥0,15 của V1846 là **lỗi thiết kế của A0**; từ nay dùng CI hiệu ứng; số V1846.A2 không mở lại gì | **XONG** |
| V1847.A2 | **ĐẠT** — CR trung vị **0,7067** (CI [0,6899; 0,7324]); ρ **0,4096** (CI [0,1202; 0,6407]) | **XONG** (`da95507`) |
| V1847.A3 | Pilot 2.000 bước | **CHƯA CHẠY — chờ duyệt** |

- **Không chạy pilot**, đúng luật V1847.B bước 4.
- Không đổi production; P2 vẫn là production; ONNX vẫn đóng băng.
- Kết quả A2 **không** dùng để mở lại `C_lo` hay số V1846.A2.

## 1. A2 — CR độ tương phản phổ ≤4 kHz

40 câu held-out dài mới, chưa dùng V18.43–V18.46; 9 video; 3,2–10,4 s; ≥12 âm tiết.
Danh sách ghi trước khi đo trong `DECISIONS.md` (`5cb6b8f`).

Định nghĩa (giống V1846.A4):
`contrast = trung bình (max − min) log-mel trong cửa sổ 5 bin, chỉ frame hữu thanh, dải ≤4 kHz`;
`CR = contrast(C) / contrast(B)`, C = P2 teacher-forcing, B = mel gốc.

| Chỉ số | Giá trị |
|---|---:|
| Số câu | 40 |
| CR nhỏ nhất / trung vị / lớn nhất | 0,596 / **0,7067** / 0,783 |
| Số câu CR < 1 | **40/40** |
| CI95 trung vị CR | **[0,6899; 0,7324]** |
| `BAK(B) − BAK(C)` trung bình / trung vị | 0,107 / 0,082 |
| Spearman `(1−CR)` vs `BAK(B)−BAK(C)` | **0,4096** |
| CI95 Spearman | **[0,1202; 0,6407]** |

- **Điều kiện (a): ĐẠT** — trung vị CR 0,7067 ≤0,95; CI95 trung vị [0,6899; 0,7324] <1.
- **Điều kiện (b): ĐẠT** — ρ 0,4096 ≥0,3; CI95 không chứa 0.
- **Verdict: ĐẠT — P2 mượt tần số dải thấp và mức mượt giải thích một phần khoảng cách BAK.**
- Diễn giải: P2 giữ độ tương phản phổ dải ≤4 kHz chỉ còn **~71 %** so với mel gốc;
  mức thiếu tương phản tương quan dương mức trung bình với khoảng cách BAK.
- Giới hạn: mel 100 bin có độ phân giải hạn chế ở dải thấp; ρ 0,41 là tương quan **vừa**,
  không phải nguyên nhân duy nhất; BAK mới khớp tai trên câu cực đoan.

## 2. A3 — pilot (chưa chạy)

Theo V1847.B bước 4: **A2 ĐẠT ⇒ dừng, chờ người dùng duyệt**. Không chạy probe/pilot trong vòng này.

Thiết kế đã đăng ký khi được duyệt:
- Probe **100 bước**; nếu loss NaN/RAM vượt máy thì dừng.
- Pilot **2.000 bước** từ **P2 EMA**, chỉ thêm loss độ tương phản phổ ≤4 kHz (khớp contrast cửa sổ 5 bin
  giữa mel dự đoán và mel gốc); trọng số chọn qua probe để loss mới **≤30 %** tổng loss, ghi trước pilot.
- Mọi thứ khác giữ P2.
- Cổng pilot: trên 40 câu A2, BAK TF tăng **≥0,05** so P2, **cận dưới CI95 >0**, và CR trung vị tăng.
- Đạt **chưa** đổi production: cần nghe mù + regression; chạy dài (trần 60.000) cần duyệt riêng.
- Pilot BAK giảm, cận trên CI <0 ⇒ đóng hướng mượt tần số, giữ đóng băng.

## 3. TỰ QUYẾT KHÁC ĐẶC TẢ

- Không có thay đổi ngoài đặc tả. 40 câu được chọn đúng tiêu chí (≥3 s, ≥12 âm tiết, tối đa 5/video,
  chưa dùng V18.43–V18.46), không xem BAK.
- A2 dùng đúng định nghĩa contrast của V1846.A4; không đổi ngưỡng sau khi thấy số.
- Không dùng UTMOS; không cấy ghép frame; không đổi production; không động ONNX.
- Không chạy pilot dù A2 ĐẠT, vì chưa có duyệt của người dùng.

## 4. Git log vòng này

```
5cb6b8f v2(v18.47): đăng ký trước V1847 + 40 câu dài mới; đo CR ≤4 kHz
da95507 v2(v18.47): A2 CR ≤4 kHz — trung vị 0,7067; ρ 0,4096; ĐẠT, chờ duyệt pilot
```

## 5. Việc tiếp

1. **Người dùng quyết có duyệt pilot 2.000 bước** (~15 phút) hay không.
2. Nếu duyệt: chạy probe 100 → chốt trọng số loss ≤30 % → pilot 2.000 → chấm BAK TF + CR trên 40 câu A2.
3. Nếu không duyệt: giữ đóng băng chất lượng, P2; không train.
4. Dù kết quả pilot ra sao: chưa đổi production; muốn đổi phải nghe mù + regression + duyệt riêng.

## 6. Test & trạng thái

- `pytest -q -rs`: **2.547 passed, 23 skipped** (ONNX đóng băng).
- `ruff check .`: sạch.
- **Trạng thái: DỪNG — CHỜ DUYỆT PILOT.**
