# V18.50 — Agent 2: trang đánh dấu rè cục bộ (chờ CSV)

> **Trạng thái: DỪNG — PHIÊN KHÔNG HỢP LỆ.** Không train, không đổi production.
> **Commit gốc của vòng**: `3dc3ae2` · **Code cuối trước hồ sơ**: `8ba7b71`
> · **Tệp đặc tả**: `V1850_agent0.md` + `DECISIONS.md` mục V18.50 + V1850b/c.
> Báo cáo này là commit hồ sơ.

## 0. Tóm tắt

| Mã | Kết quả | Trạng thái |
|---|---|---|
| V1850.A0/A1 | Đóng dòng L_con/rè nền; mở dòng **rè cục bộ theo âm tiết** | **XONG** |
| V1850.A2 | **86 mục** đã dựng; phiên nghe **KHÔNG HỢP LỆ** (cấy 0/3) | **TRƯỢT VALIDITY** |
| V1850.A3 | Không kết luận — phiên không hợp lệ; chỉ 2 câu không mismatch | **KHÔNG KẾT LUẬN** |
| V1850.A4 | Bảng đặc trưng A/B/P2 + creak đã dựng; **không chấm** vì phiên invalid | **KHÔNG CHẤM** |
| V1850.A5 | Hướng xử lý | **CHƯA** |

- **Link nghe**: https://texture-start-mixing-advertiser.trycloudflare.com/
- Trang có **86 mục**; mỗi mục có audio + nút theo âm tiết + ô **"Văn bản không khớp âm thanh"**.
- **Không train, không đổi production.**

## 1. A2 — trang đánh dấu

- 20 câu held-out dài mới, chưa dùng V18.43–V18.49; 8 video; ≤4 câu/video.
- 80 mục chính: mỗi câu **A (wav gốc)**, **B (Vocos mel gốc)**, **P2 chunk**, **PILOT chunk**.
- 6 đối chứng: 3 lặp (cùng file, xuất hiện 2 lần) + 3 B cấy click/buzz 50 ms vào âm tiết biết trước.
- Xáo trộn seed 1850; −16 LUFS; key ngoài thư mục phục vụ.
- Vị trí cấy: câu `2b65WyiFC9k_0175__s01` âm 22; `EM_ObHWvd94_0243__s00` âm 21;
  `EUNlJU1BuzE_0196__s00` âm 26 (1-based).
- CSV: `item_id,syllables,mismatch` (syllables 1-based, `;`).
- Hướng dẫn trên trang: bấm âm tiết nghe rè/rít/vỡ; không chắc thì không bấm; tick mismatch nếu chữ không khớp.

## 2. Kết quả phiên nghe

### 2.1 Validity — KHÔNG HỢP LỆ

| Đối chứng | Kết quả | Luật | Kết |
|---|---|---|---|
| 3 mục cấy click | **0/3** đúng ±1 âm tiết | ≥2/3 | **trượt** |
| 3 mục lặp | **2/3** Jaccard ≥0,5 | ≥2/3 | đạt |
| Đủ 86 mục | 86/86 | đủ | đạt |

- Theo luật V1850.A2: **phiên không hợp lệ ⇒ làm lại khác ngày; không kết luận A3/A4.**
- Cấy click không được bấm đúng: có thể burst không đủ nổi/người nghe bận đánh dấu chỗ khác;
  không đổi ngưỡng sau khi thấy kết quả.

### 2.2 Mismatch — phát hiện lớn

| Bản | Số mục bị tick "không khớp" |
|---|---:|
| A (wav gốc) | **18/20 câu** |
| B (Vocos mel gốc) | **20/20 câu** |
| P2 | 1/21 |
| PILOT | 1/21 |

- **Chỉ 2/20 câu không bị tick mismatch ở A/B.** Tức phần lớn **audio gốc/GT đọc dư từ ở cuối**
  so với văn bản — không phải model tự thêm. P2/PILOT gần như khớp chữ (1 mismatch mỗi bên).
- Đây là bằng chứng trực tiếp cho **vấn đề nhãn/segment cuối clip**, đúng hướng V18.51 (ASR audit),
  chưa phải kết luận nhân quả. Giả thuyết "model lấy trung bình các từ dư cuối khi training" là hợp lý
  nhưng **chưa được kiểm**.
- Vì A/B mismatch quá nhiều, A3/A4 chỉ còn **2 câu dùng được**; mọi rate dưới đây chỉ để tham khảo,
  **không kết luận**.

### 2.3 A3/A4

- `r(A)=0`, `r(B)=0`, `r(P2)=9,33 %`, `r(PILOT)=9,33 %` trên 2 câu còn lại — **không dùng** vì phiên invalid
  và mẫu quá nhỏ.
- P2 có **116 lượt bấm** trên 20 câu; phân bố rải (22 lượt ở decile đầu, 16 ở cuối, còn lại giữa);
  **13 lượt ở âm tiết cuối**, 16 ở 3 âm tiết cuối — không chỉ tập trung cuối câu.
- A4 **không chấm** (phiên invalid). Bảng đặc trưng **20 câu / 765 âm tiết** đã dựng sẵn:
  HNR, flatness 2–8 kHz, contrast, F0 jump, duration, vị trí chunk, coda tắc, thanh, OOV;
  creak A/B/P2 (3 kênh `eval_creak`: hnr, glottalization, jitter; z-score toàn bộ).
- Mismatch xử lý: A/B tick ⇒ loại câu khỏi A3/A4; P2/PILOT tick ⇒ báo "model đọc sai chữ",
  loại bản đó khỏi rate tương ứng.

## 3. TỰ QUYẾT KHÁC ĐẶC TẢ

1. **Bảng A4 `creak`** dùng z-score 3 kênh trên toàn bộ A/B/P2 (HNR đảo dấu);
   đây là diễn giải cụ thể của "điểm creak theo eval_creak", chưa có công thức duy nhất trong repo.
2. **Mismatch**: A/B tick ⇒ loại câu; P2/PILOT tick ⇒ báo và loại bản đó khỏi rate (không loại cả câu).
3. **Page 86 mục** thay bản 66 cũ theo V1850b; link cũ đã bỏ.
4. **Scorer A3 chỉ kết luận khi validity đạt**; phiên này invalid nên `source` = không hợp lệ,
   không dùng rate để tuyên bố.
5. **A4 không chấm** vì A3 invalid; bảng đặc trưng vẫn giữ để dùng lại sau khi có phiên hợp lệ.
6. `V1851` (ASR audit) chỉ ghi đăng ký, **chưa chạy**; kết quả mismatch A/B 18/20 + 20/20 là lý do
   ưu tiên audit nhãn trước khi làm lại trang.

## 4. Git log vòng này

```
c4edbe6 đăng ký trước V1850 (20 câu)
0e312c6 sửa đăng ký V1850b — thêm A gốc 86 mục; luật A/B/P2/PILOT; creak
536fb2b V1850c — mismatch + CSV; ghi V18.51 (chưa chạy)
0d92dc1 Jaccard rỗng = 1
23cbe75 ghi link nghe 86 mục
8ba7b71 bảng đặc trưng A/B/P2 + creak; A4 scorer
109714f báo cáo trạng thái chờ nghe
```

## 5. Test & trạng thái

- `pytest -q -rs`: **2.552 passed, 23 skipped** (ONNX đóng băng).
- `ruff check .`: sạch.
- **Trạng thái: DỪNG — PHIÊN KHÔNG HỢP LỆ.**
