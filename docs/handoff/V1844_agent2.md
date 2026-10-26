# V18.44 — Agent 2: đóng băng ONNX, hiệu chuẩn giám khảo, cấy ghép oracle, nghe mù

> **Trạng thái: DỪNG, CHỜ ĐỌC + CHỜ NGHE A5.** Không train, không đổi production.
> **Commit gốc của vòng**: `5405188` · **Code cuối trước hồ sơ**: `161a599`
> · **Tệp đặc tả**: `V1844_agent0.md` + `DECISIONS.md` mục V18.44.
> Báo cáo này là commit hồ sơ.

## 0. Tóm tắt

| Mã | Kết quả | Trạng thái |
|---|---|---|
| V1844.A1 | ONNX **đóng băng**; 23 test ONNX **skip có lý do**; suite 2.547 pass / 23 skip | **XONG** (`dc4398a`) |
| V1844.A1b | Sửa lý do trượt A3: **chỉ** p95 short 1,2188×; RSS 0,456× đã đạt vế "ít nhất một"; CV short 0,9 % / mid 0,8 % / long 12,5 % | **XONG** (`3e1ae46`) |
| V1844.A2 | Hợp đồng **chốt = chunk**; không làm lại A2 | **XONG** (`3e1ae46`) |
| V1844.A3 | Bootstrap hai tầng vẫn lệch: CI **[0,0035; 0,1429]** không chứa 0 ⇒ **UTMOS bị loại khỏi luật quyết định**; BAK tất định | **XONG** (`441b1de`) |
| V1844.A4 | **Đóng lead g1_1k** | **XONG** (`3e1ae46`) |
| V1844.A6 | Đối chứng C_all/C_none **đạt tuyệt đối**; nhưng tổng Recovery frame **−0,85** ⇒ **LẠ, DỪNG** | **XONG** (`09cb383`) |
| V1844.A5 | 28 lượt nghe mù đã dựng + link; **chờ CSV** để chấm | **CHỜ NGƯỜI NGHE** (`161a599`) |
| V1844.A7 | Cổng V18.45 **chưa mở** (A5 chưa có; A6 lạ; chưa duyệt ngân sách) | **ĐÓNG** |

## 1. A1 — đóng băng ONNX

- Đã đánh dấu skip với lý do **"V1844.A1 đóng băng ONNX"** cho:
  - `tests/test_onnx_frontend.py` (9)
  - `tests/test_onnx_runtime.py` (2)
  - `tests/test_onnx_exceptions.py` (4)
  - `tests/test_export_v2.py` (7)
  - `tests/test_v2_slot5.py::test_v2_onnx_export_va_parity` (1)
  - phần ONNX trong `tests/test_golden_v1843.py`: **bỏ**, chỉ kiểm PyTorch; test ghi `onnx_skipped`.
- **Không xoá** code/artefact/hash; `ONNX-EXC-001` chuyển "đình chỉ cùng nhánh".
- Suite: **2.547 passed, 23 skipped** — mọi skip có lý do, không skip im lặng.
- PyTorch golden fast vẫn chạy: 3 câu, dưới 30 s.

## 2. A1b — sửa lý do trượt A3 + CV

- Lý do trượt A3 **duy nhất**: p95 câu ngắn **1,2188× > 1,2×**.
- Vế "ít nhất một trong" **đã đạt** nhờ peak RSS **0,456× ≤ 0,6×**.
- Cold start **0,632×** và dung lượng **0,318×** chỉ là thông tin, **không phải** lý do trượt.
- CV latency lấy từ dữ liệu đã đo, không đo lại:

| Bucket | CV lặp lại | Nguồn |
|---|---:|---|
| short | **0,9 %** | `result_shortmid.json` (per-sentence) |
| mid | **0,8 %** | `result_shortmid.json` (per-sentence) |
| long | **12,5 %** | `result.json` (pooled; lần đo đầy đủ) |

- Short <15 % ⇒ **không đổi nhãn "trượt"**. ONNX vẫn đóng băng theo A1.

## 3. A3 — hiệu chuẩn giám khảo

### 3.1 Bootstrap hai tầng trên đối chứng âm A2

Dữ liệu: 30 câu A2, mỗi câu 5 seed [0..4] và 5 seed [5..9] trên **cùng audio chunk**.
Bootstrap 10.000 lần; tầng 1 lấy lại câu, tầng 2 lấy lại seed trong từng nhóm A/B.

| Phương pháp | Mean | CI95 | Chứa 0? |
|---|---:|---|---|
| CI cũ A2 (paired trên trung bình seed) | +0,0729 | [0,0177, 0,1275] | Không |
| **Hai tầng (câu + seed)** | **+0,0729** | **[0,0035, 0,1429]** | **Không** |

- **Kết luận A3(a): TRƯỢT.** Phương sai seed là thật, không phải lỗi CI cũ. Theo luật:
  **UTMOS bị loại khỏi luật quyết định; chỉ còn BAK + tai**.
- Đánh dấu **g1_1k +0,096** và **P2 4k −0,070** là **"chưa phân giải được"** (nằm trong vùng nhiễu seed).

### 3.2 BAK tất định

- Chấm BAK **hai lần** trên 10 file `C` của A4: **10/10 bằng tuyệt đối**, max diff **0,0**.
- Không có dấu hiệu BAK phụ thuộc trạng thái/thứ tự.

## 4. A6 — cấy ghép oracle

40 câu A4, mel B (gốc) / C (P2 TF), thay từng phần rồi vocode + BAK.

### 4.1 Đối chứng (chạy trước)

| Đối chứng | BAK | Tham chiếu A4 | Lệch |
|---|---:|---:|---:|
| `C_all` (thay toàn bộ) | 3,989907 | B = 3,9899 | 0,0000 |
| `C_none` (không thay) | 3,741853 | C = 3,7419 | 0,0000 |
| Δac | 0,2481 | 0,2481 | 0,0000 |

- **Đạt tuyệt đối**; C_all = B, C_none = C.

### 4.2 Recovery

| Biến thể | Mean Recovery | Median per-row | % câu ≥0,5 |
|---|---:|---:|---:|
| `C_nuc` (nucleus) | −0,1055 | 0,054 | 10 % |
| `C_onc` (onset+coda) | **−0,7179** | −0,564 | 10 % |
| `C_sil` (lặng) | −0,0275 | −0,084 | 30 % |
| `C_hi` (>4 kHz) | −0,1887 | 0,078 | 28 % |
| `C_lo` (≤4 kHz) | **+0,9733** | 0,469 | 50 % |

- Tổng bù trừ: `nuc + onc + sil` = **−0,8509** (ngoài [0,5; 1,5]); `hi + lo` = **0,7846** (trong khoảng).
- **Kết luận A6: LẠ — DỪNG, BÁO.** Không được chọn `C_lo` dù mean 0,97, vì tổng frame ngoài khoảng
  và median per-row chỉ 0,469 (50 % câu ≥0,5) — mean bị kéo bởi outlier.
- `C_onc` âm mạnh (−0,72) cho thấy **ghép frame onset/coda với mel gốc làm BAK xấu hơn C**;
  đây là dấu hiệu artefact chỗ nối hoặc BAK không tuyến tính, không phải "onset/coda là nguồn rè".
- `C_sil` gần 0 ⇒ khoảng lặng **không** phải nguồn BAK.
- **GV ratio** trung bình: `<1k` 0,8159 · `1–4k` 0,8320 · `>4k` 0,7568.
  `over_smoothing_supported=True` theo chữ luật (có dải <0,8 và main `C_lo`), nhưng dải <0,8 là `>4k`
  còn main là `≤4k` — **bằng chứng over-smoothing yếu/không khớp dải**, chỉ ghi nhận.
- **F0 teacher-forcing**: model `forward` **không nhận f0 đầu vào** (F0 do variance head dự đoán)
  ⇒ bỏ `C_f0`, đã ghi rõ.
- Dải tần: 66 bin ≤4 kHz (center 23,4–3968 Hz), 34 bin >4 kHz (4088,5–11644 Hz).

## 5. A5 — nghe mù B vs C

- 16 câu chọn theo `|BAK(B) − BAK(C)|` lớn nhất; danh sách đã ghi vào `DECISIONS.md` **trước** khi dựng trang.
- 28 lượt: **16 B vs C** + **4 dương** (B vs B+trắng SNR 30 dB) + **4 âm** (C vs C) + **4 lặp** (đảo A/B).
- Chuẩn −16 LUFS; peak <1; vị trí/thứ tự ngẫu nhiên seed 1844; ẩn tên; key nằm ngoài thư mục phục vụ.
- **Link nghe**: https://reasonably-recipients-selective-solutions.trycloudflare.com/
  (quick tunnel; nếu hết hạn, chạy lại server + tunnel trên `artifacts/listen_v1844_a5/`).
- Trang có nút **"Tải CSV"** (`v1844_a5_answers.csv`). Chấm bằng:

```bash
.venv/bin/python tools/v1844_a5_score.py <đường_dẫn_csv>
```

- **Chưa có CSV ⇒ chưa kết luận.** Luật: hợp lệ khi dương ≥3/4, âm ≥3/4, lặp ≥3/4;
  B thắng khi binomial một phía p<0,05, ≥10 lượt không hòa (16 lượt cần ≥12).
- Nếu phiên không hợp lệ: làm lại ngày khác. Nếu B không thắng: **không train theo BAK**,
  báo A0; có thể rè người dùng nghe nằm ở chunk/fade/loudness.

## 6. A7 — cổng V18.45

Chưa mở, vì:
1. A5 chưa có CSV/kết luận.
2. A6 **lạ**, không có thành phần chính sạch.
3. Ngân sách train chưa được người dùng duyệt.

Ngân sách khi mở (nếu đủ): probe 100 bước → pilot 2.000 bước (~15 phút) có cổng BAK TF
đặt trước → tối đa 60.000 bước (~7 giờ). Giả thuyết/kiến trúc V18.45 do A0 chốt sau A5+A6.

## 7. TỰ QUYẾT KHÁC ĐẶC TẢ

1. **Phạm vi skip A1**: mình skip toàn bộ module ONNX frontend/runtime/exceptions/export_v2 +
   test ONNX parity trong `test_v2_slot5` + phần ONNX của golden; không skip các test export ONNX
   không liên quan parity (postnet/quantization/neural_smoke) vì chúng không phải "test parity ONNX".
   Nếu A0 muốn skip rộng hơn, báo để chỉnh.
2. **A1b long CV**: long chỉ có CV pooled 12,5 % từ lần đo đầy đủ; không đo lại (đúng luật "từ dữ liệu đã đo").
3. **A3 hai tầng**: resample seed **độc lập** trong từng nhóm A/B của mỗi câu; đây là cách bảo toàn
   phương sai seed. CI cũ được tái lập đúng [0,0177; 0,1275].
4. **A6 đối chứng**: ngoài C_all/C_none, mình kiểm chéo mean BAK với A4 (B/C) để bắt lỗi vocode/normalize;
   lệch 0,0000.
5. **A6 per-row**: báo thêm median và % câu ≥0,5 vì mean bị outlier chi phối; không đổi verdict theo luật.
6. **A5 dương**: sau khi thêm nhiễu trắng SNR 30 dB, chuẩn lại −16 LUFS nên SNR xấp xỉ 30 dB.
7. **A5 key**: lưu ngoài thư mục phục vụ (`artifacts/bench/v1844_a5/key.json`) để không lộ đáp án.
8. **A5 link**: dùng http.server + cloudflared quick tunnel, không dùng `serve_listen_demo.sh`
   (script đó tự chọn port 8788 và có thể đụng server cũ).

## 8. Việc tiếp

1. **Người dùng nghe A5** và gửi CSV; mình chấm theo luật. Kết quả quyết định V18.45 có mở hay không.
2. **A0 đọc A6**: kết quả "lạ" do tổng frame; cần quyết định có thiết kế lại cấy ghép (ví dụ ghép theo
   cửa sổ có overlap) hay dừng hướng BAK.
3. **Không train** cho đến khi A5 xác nhận + A6 có thành phần chính + duyệt ngân sách.
4. ONNX giữ đóng băng; mở lại phải chạy parity + A3 từ đầu với hash mới.

## 9. Test & trạng thái

- `pytest -q -rs`: **2.547 passed, 23 skipped** (mọi skip: "V1844.A1 đóng băng ONNX"), ~42 s.
- `ruff check .`: sạch.
- **Trạng thái: DỪNG, CHỜ ĐỌC + CHỜ NGHE A5.**
