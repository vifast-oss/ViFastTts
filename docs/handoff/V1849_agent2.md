# V18.49 — Agent 2: tái lập chunk + nghe mù PILOT vs CONTROL

> **Trạng thái: DỪNG — TAI KHÔNG PHÂN BIỆT.** Không train, không đổi production.
> **Commit gốc của vòng**: `74ed53c` · **Code cuối trước hồ sơ**: `9d917e7`
> · **Tệp đặc tả**: `V1849_agent0.md` + `DECISIONS.md` mục V18.49.
> Báo cáo này là commit hồ sơ.

## 0. Tóm tắt

| Mã | Kết quả | Trạng thái |
|---|---|---|
| V1849.A0 | Chấp nhận V18.48; production P2 | **XONG** |
| V1849.A1 | Ghi lỗi thiết kế A0 thứ hai; cổng chất lượng từ nay đo chính ở **chunk**, TF chỉ chẩn đoán | **XONG** |
| V1849.A2 | **ĐẠT** — ΔBAK chunk **+0,1121** CI [0,0569; 0,1715]; ΔCR **+0,0841** CI [0,0776; 0,0878] | **XONG** (`9e9df51`) |
| V1849.A3 | **TAI KHÔNG PHÂN BIỆT** — PILOT 1 · CONTROL 0 · hòa 15; phiên hợp lệ | **XONG** |
| V1849.A4 | Chỉ A2 đạt; A3 không PILOT thắng ⇒ **không đổi production, không thành ứng viên** | **DỪNG** |

- **A2 tái lập mạnh** trên 40 câu mới: BAK chunk tăng +0,1121, CR tăng +0,0841.
- Kết quả **cao hơn kỳ vọng đăng ký +0,03…+0,06**; cổng chỉ yêu cầu CI>0, nên vẫn ĐẠT.
- **Chưa đổi production**; cần A3 PILOT thắng + V18.50 regression/duyệt.

## 1. A2 — tái lập chunk trên 40 câu mới

Checkpoint dùng lại đúng V18.48, không train:

| Nhánh | path | SHA256 | step | contrast_weight |
|---|---|---|---:|---:|
| PILOT | `runs/v1848_pilot/last.pt` | `3f5239e7…` | 2000 | 1,0338 |
| CONTROL | `runs/v1848_control/last.pt` | `5b435d20…` | 2000 | 0,0 |

40 câu held-out dài mới, chưa dùng V18.43–V18.48 (8 video; 5 câu/video tối đa).
CLI chunk mode mặc định, −16 LUFS.

| Chỉ số | CONTROL | PILOT |
|---|---:|---:|
| BAK chunk | 3,787704 | **3,899798** |
| CR trung vị (TF) | 0,739901 | **0,826345** |

- **ΔBAK chunk = +0,112094**, CI95 **[0,0569; 0,1715]**.
- **ΔCR trung vị = +0,084124**, CI95 **[0,0776; 0,0878]**.
- Kỳ vọng đăng ký trước +0,03…+0,06; thực tế **cao hơn**, nhưng cổng chỉ là CI>0.
- **Verdict: ĐẠT — tái lập chunk + cơ chế CR.**
- Cảnh báo: hiệu ứng lớn hơn kỳ vọng có thể do bộ câu mới; không suy rộng; tai vẫn là bằng chứng cuối.

## 2. A3 — nghe mù PILOT vs CONTROL

- 16 câu chọn ngẫu nhiên seed 1849 từ 40 câu A2, ghi trước khi dựng (không xem BAK).
- 28 lượt: 16 PILOT vs CONTROL + 4 dương (CONTROL vs CONTROL+nhiễu trắng SNR 30 dB)
  + 4 âm (CONTROL vs CONTROL) + 4 lặp đảo A/B.
- −16 LUFS, kiểm peak, vị trí/thứ tự ngẫu nhiên, ẩn tên; key ngoài thư mục phục vụ.
- **Link nghe**: https://automotive-helpful-chances-governmental.trycloudflare.com/
- Trang có nút **"Tải CSV"** (`v1849_a3_answers.csv`). Chấm:

```bash
.venv/bin/python tools/v1849_a3_score.py <đường_dẫn_csv>
```

- Luật: hợp lệ khi dương ≥3/4, âm ≥3/4, lặp ≥3/4. **PILOT thắng** khi binomial một phía
  p<0,05 trên lượt không hòa, tối thiểu 10 lượt. <10 lượt không hòa ⇒ "tai không phân biệt".
  CONTROL thắng rõ ⇒ **ĐÓNG L_con**.
- **Kết quả CSV** (28/28, lưu `artifacts/bench/v1849_a3/answers.csv`, score `score.json`):

| Hạng mục | Kết quả | Luật | Kết |
|---|---|---|---|
| 16 lượt PILOT vs CONTROL | **PILOT 1 · CONTROL 0 · hòa 15**; non-tie **1**; p_pilot 0,5 | ≥10 non-tie, p<0,05 | **tai không phân biệt** |
| 4 đối chứng dương | **3/4** chọn bản sạch | ≥3/4 | đạt (sát biên) |
| 4 đối chứng âm | **4/4** "không phân biệt" | ≥3/4 | đạt |
| 4 lượt lặp | **4/4** nhất quán | ≥3/4 | đạt |

- **Phiên hợp lệ**, nhưng chỉ **1 lượt không hòa** ⇒ theo luật: **"TAI KHÔNG PHÂN BIỆT"**, không kết luận PILOT thắng.
- Không có CONTROL thắng rõ, nên **không đóng L_con**; nhưng PILOT **không thành ứng viên production** vì thiếu bằng chứng tai.
- Giới hạn: một người nghe; 15/16 "không phân biệt" phù hợp với hiệu ứng nhỏ (~0,1 BAK) dưới ngưỡng nghe.

## 3. A4 — kết hợp

- A2 **ĐẠT**; A3 **"tai không phân biệt"** ⇒ chỉ một trong hai đạt.
- Theo V1849.A4: **không đổi production, không thành ứng viên**, báo A0; **không đóng L_con**
  (vì A3 không CONTROL thắng rõ), nhưng không mở V18.50.
- Giữ P2; ONNX đóng băng.
- Nếu A3 PILOT thắng: **ỨNG VIÊN**; V18.50 làm regression golden set + OOV/số/dấu câu,
  rồi người dùng duyệt đổi production sang PILOT 2k.
- Nếu chỉ một trong hai đạt: không đổi production, báo A0.
- Nếu cả hai không đạt: đóng L_con, đóng băng chất lượng acoustic, kết thúc dòng chẩn đoán rè.
- **Không đổi production trong vòng này** dù cả hai đạt.

## 4. TỰ QUYẾT KHÁC ĐẶC TẢ

1. **A2 sinh audio chunk trước, chấm BAK sau khi trang A3 đã sống** — đúng yêu cầu thứ tự.
2. **Kiểm provenance** bằng SHA256 + step=2000 + `contrast_weight` 1,0338/0,0; không train lại.
3. **A3 key** lưu ngoài thư mục phục vụ; dùng scorer riêng, không đổi nhãn PILOT/CONTROL.
4. **Hiệu ứng lớn hơn kỳ vọng**: báo rõ, không đổi ngưỡng, không suy rộng.
5. Không dùng UTMOS; không động ONNX; không đổi production.

## 5. Git log vòng này

```
3010df3 đăng ký trước V1849 + 40 câu mới + 16 câu nghe
9e9df51 A2 tái lập chunk — ΔBAK +0,1121; ΔCR +0,0841; ĐẠT
9d917e7 A3 trang nghe mù 28 lượt + scorer
```

## 6. Việc tiếp

1. **Dừng**: tai không phân biệt; PILOT không thành ứng viên production.
2. Không đổi production; P2 giữ nguyên; không mở V18.50.
3. Không đóng L_con (CONTROL không thắng rõ), nhưng không thử thêm trong dòng này.
4. Nếu A0 muốn tiếp: cần giả thuyết/thiết kế tai mới (nhiều người nghe, câu dễ phân biệt hơn)
   + đăng ký trước; không dùng lại kết quả này.

## 7. Test & trạng thái

- `pytest -q -rs`: **2.552 passed, 23 skipped** (ONNX đóng băng).
- `ruff check .`: sạch.
- **Trạng thái: DỪNG — TAI KHÔNG PHÂN BIỆT.**
