# V18.50 — Agent 2: trang đánh dấu rè cục bộ (chờ CSV)

> **Trạng thái: DỪNG — CHỜ NGƯỜI NGHE.** Không train, không đổi production.
> **Commit gốc của vòng**: `3dc3ae2` · **Code cuối trước hồ sơ**: `8ba7b71`
> · **Tệp đặc tả**: `V1850_agent0.md` + `DECISIONS.md` mục V18.50 + V1850b/c.
> Báo cáo này là commit hồ sơ.

## 0. Tóm tắt

| Mã | Kết quả | Trạng thái |
|---|---|---|
| V1850.A0/A1 | Đóng dòng L_con/rè nền; mở dòng **rè cục bộ theo âm tiết** | **XONG** |
| V1850.A2 | **86 mục**: 20 câu × A/B/P2/PILOT + 3 lặp + 3 cấy click; ô mismatch | **XONG — chờ nghe** |
| V1850.A3 | Chờ CSV để tính `r(A/B/P2/PILOT)` | **CHỜ** |
| V1850.A4 | Bảng đặc trưng A/B/P2 + creak, **chưa nối nhãn** | **ĐÃ CHUẨN BỊ** |
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

## 2. A3/A4 — chờ CSV

- A3: `r(X)` cho X∈{A,B,P2,PILOT}, bootstrap câu 10.000; luật V1850b.2
  (đặc điểm giọng / vocoder / acoustic / hỗn hợp); `r(PILOT)−r(P2)` tham khảo.
- A4: bảng đặc trưng **20 câu / 765 âm tiết** đã dựng, gồm:
  HNR, flatness 2–8 kHz, contrast, F0 jump, duration, vị trí chunk, coda tắc, thanh, OOV;
  **creak** trên A/B/P2 (3 kênh `eval_creak`: hnr, glottalization, jitter; z-score toàn bộ).
- **Chưa nối nhãn**; chỉ chấm sau khi có CSV và kiểm phiên hợp lệ.
- Mismatch xử lý: A/B bị tick ⇒ loại câu khỏi A3/A4; P2/PILOT bị tick ⇒ báo "model đọc sai chữ",
  loại bản đó khỏi rate tương ứng.

## 3. TỰ QUYẾT KHÁC ĐẶC TẢ

1. **Bảng A4 `creak`** dùng z-score 3 kênh trên toàn bộ A/B/P2 (HNR đảo dấu);
   đây là diễn giải cụ thể của "điểm creak theo eval_creak", chưa có công thức duy nhất trong repo.
2. **Mismatch**: A/B tick ⇒ loại câu; P2/PILOT tick ⇒ báo và loại bản đó khỏi rate (không loại cả câu).
3. **Page 86 mục** thay bản 66 cũ theo V1850b; link cũ đã bỏ.
4. `V1851` (ASR audit) chỉ ghi đăng ký, **chưa chạy**.

## 4. Git log vòng này

```
c4edbe6 đăng ký trước V1850 (20 câu)
0e312c6 sửa đăng ký V1850b — thêm A gốc 86 mục; luật A/B/P2/PILOT; creak
536fb2b V1850c — mismatch + CSV; ghi V18.51 (chưa chạy)
0d92dc1 Jaccard rỗng = 1
23cbe75 ghi link nghe 86 mục
8ba7b71 bảng đặc trưng A/B/P2 + creak; A4 scorer
```

## 5. Test & trạng thái

- `pytest -q -rs`: **2.552 passed, 23 skipped** (ONNX đóng băng).
- `ruff check .`: sạch.
- **Trạng thái: DỪNG — CHỜ NGƯỜI NGHE.**
