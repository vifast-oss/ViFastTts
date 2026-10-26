# V18.52 — Agent 2: bộ dò đuôi không ASR (chờ CSV)

> **Trạng thái: DỪNG — CHỜ NGƯỜI NGHE.** Không train, không đổi production, không ghi đè dữ liệu.
> **Commit gốc của vòng**: `e915b11` · **Code cuối trước hồ sơ**: (đang cập nhật)
> · **Tệp đặc tả**: `V1852_agent0.md` + `DECISIONS.md` mục V18.52.
> Báo cáo này là commit hồ sơ.

## 0. Tóm tắt

| Mã | Kết quả | Trạng thái |
|---|---|---|
| V1852.A1 | Bộ dò đuôi: hữu thanh ≥0,12 s + đỉnh RMS ≥−15 dB; 3 unit test pass | **XONG** |
| V1852.A2 | 40 segment (20+/20−/10 sát ngưỡng) + 8 đối chứng; trang 48 mục | **CHỜ NGHE** |
| V1852.A3 | Quét toàn bộ đang chạy nền, **chưa tổng hợp** | **ĐANG CHẠY** |
| V1852.A4 | Manifest loại bỏ | **CHƯA** |

- **Link nghe**: https://centers-alt-higher-leaders.trycloudflare.com/
- Trang phát **1 s trước + vùng đuôi**, vạch đỏ = chỗ bắt đầu đuôi.
- Câu hỏi: **“Sau vạch có tiếng nói không?”** → Có / Không / Không chắc.
- **Không train, không đổi production.**

## 1. Bộ dò A1

`src/vifasttts/data/tail_detect.py`:
- Vùng đuôi = từ `lead + Σdurations + Σgaps[:-1]` đến hết segment.
- Hữu thanh: pyworld harvest + stonemask, F0>0.
- RMS 50 ms; đỉnh đuôi so **trung vị RMS frame hữu thanh của segment**.
- **Dương** khi hữu thanh đuôi ≥0,12 s **và** gain ≥−15 dB.
- Unit test: đuôi lặng ⇒ âm; đuôi chèn tiếng nói ⇒ dương; `tail_start_frame` đúng. **3 pass.**

## 2. A2 — chọn 40 + đối chứng

- Quét 2.000 segment đầu: **877 dương (43,9%)** — rất cao, cần hiệu chỉnh tai.
- Chọn 20 dương + 20 âm, trong đó 10 ca sát ngưỡng (5+/5−), seed 1852; không nghe trước.
- 4 đối chứng dương: chèn 0,4 s tiếng nói từ clip khác vào đuôi.
- 4 đối chứng âm: đuôi thay bằng lặng số 0.
- Trang 48 mục, xáo seed 1852; key ngoài thư mục phục vụ.
- CSV: `item_id,answer` (co / khong / khong_chac).
- Luật: dương ≥3/4 "Có", âm ≥3/4 "Không"; bộ dò ĐẠT khi trên lượt không "Không chắc":
  độ khớp ≥85% **và** precision lớp dương ≥0,8.

## 3. A3 — toàn bộ

- Đang chạy `tools/v1852_tail_scan.py` trên train + held-out (20.837 segment) ở nền,
  ghi `artifacts/bench/v1852_tail/scan_full.jsonl`.
- **Chưa tổng hợp/báo tỉ lệ** theo V18.52.B3; chỉ tổng hợp nếu A2 ĐẠT.
- Ước tính ~56 phút (2.000 segment đầu mất 5,4 phút).

## 4. TỰ QUYẾT KHÁC ĐẶC TẢ

1. **40 segment lấy từ 2.000 segment quét đầu** (train + holdout), không chỉ holdout;
   V18.52.A2 không giới hạn split. Đã ghi danh sách trong DECISIONS.
2. **Đối chứng dương** dùng 0,4 s đầu vùng đuôi của clip nguồn (clip nguồn là ca dương),
   không chọn theo BAK.
3. **Quét toàn bộ đang chạy trước khi A2 ĐẠT** nhưng **không tổng hợp**; nếu A2 trượt sẽ bỏ.
4. Không dùng ASR/CER; không cắt audio; không đổi dữ liệu.

## 5. Git log vòng này

```
30f6939 đăng ký trước V1852 + luật bộ dò
(đang cập nhật) bộ dò + unit test + trang A2
```

## 6. Test & trạng thái

- `pytest -q tests/test_tail_detect.py`: **3 passed**.
- Toàn bộ suite chưa chạy lại trong lúc scan nền; sẽ chạy sau.
- **Trạng thái: DỪNG — CHỜ NGƯỜI NGHE.**
