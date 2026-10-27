> **LỊCH SỬ — không còn hiệu lực (archive từ 27/10/2026).**
> Trạng thái hiện hành: `docs/handoff/TRANG_THAI.md`; mục lục: `docs/README.md`.
> Giữ để audit/tái lập, không dùng để quyết định.

# V18.51 — Agent 2: audit nhãn bằng ASR, truy nguyên mốc cuối

> **Trạng thái: DỪNG — A4 CHƯA CHẠY; A5 TRƯỢT TỰ ĐỘNG.** Không train, không đổi production.
> **Commit gốc của vòng**: `0fa26e2` · **Code cuối trước hồ sơ**: `b603baf`
> · **Tệp đặc tả**: `V1851_agent0.md` + `DECISIONS.md` mục V18.51.
> Báo cáo này là commit hồ sơ.

## 0. Tóm tắt

| Mã | Kết quả | Trạng thái |
|---|---|---|
| V1851.A1 | Key cấy khớp ASR trong **0–0,15 s**; người dùng không bấm đúng burst (i45 bấm cuối 8,84 s) | **Key không sai; phiên invalid do phản hồi** |
| V1851.A2 | 18/20 tai–ASR cùng kết luận; **0/18 câu** có dư cuối khớp đầu segment kế (CER≤0,3) | **Chưa đủ bằng chứng "lệch mốc cuối" theo cổng** |
| V1851.A3 | **9/20 câu** dư cuối >0,1 s; offset không theo độ dài (corr −0,027); code giữ đuôi trong `gaps[-1]` | **Cơ chế: đuôi audio nằm trong gap cuối** |
| V1851.A4 | Quét toàn bộ **chưa chạy** — 18,5 h audio, ước tính 3–4 h CPU | **CHƯA PHÂN LOẠI P0** |
| V1851.A5 | Sửa thử 40 clip: CER≤0,1 **0/40**; **16/40 mất âm cuối** | **TRƯỢT TỰ ĐỘNG — không áp** |
| V1851.A6 | Ghi hồ sơ số cũ "có thể nhiễm lệch mốc cắt" | **XONG** |

- **Không train, không đổi production.**
- A5 **không dựng link tai** vì tự động đã trượt rõ; không áp lên data.
- A4 chưa chạy: chưa thể kết luận P0 (≥10% clip dư cuối ≥2 âm tiết).

## 1. A1 — kiểm click cấy

| Mục | Câu | Target | Burst | ASR tại target | Người bấm | Kết |
|---|---:|---:|---:|---|---|---|
| i06 | `EUNlJU1BuzE_0196__s00` | 26 | 4,000 s | "ở" 4,18–4,46 | **không bấm** | không đánh giá được |
| i21 | `EM_ObHWvd94_0243__s00` | 21 | 4,629 s | "đang" 4,64–4,76 | **không bấm** | không đánh giá được |
| i45 | `2b65WyiFC9k_0175__s01` | 22 | 4,267 s | "kết" 4,42–4,62 | 39–42 (8,84 s) | bấm cuối, không gần burst |

- Key target khớp ASR (lệch ≤0,15 s) ⇒ **key cấy không sai**.
- Phiên invalid vì người dùng **không bấm burst** (2 mục không bấm; 1 mục bấm cuối câu).
- **Không đổi verdict V18.50.**

## 2. A2 — ASR 20 câu V18.50

ASR: `faster-whisper 1.2.1`, model `small`, int8, `language=vi`, word timestamps.

- 18/20 câu bị tick mismatch; **18/20 tai và ASR cùng kết luận** (90%).
- **0/18 câu** có dư cuối khớp 15 âm tiết đầu segment kế với CER ≤0,3.
- ASR có nhiều lỗi/không khớp chữ: CER 0,24–1,07; số từ ASR thường **ít hơn** nhãn (12/20),
  một số nhiều hơn. Vì vậy "dư cuối" theo ASR không đủ tin để kết luận lệch mốc.
- **Verdict A2: chưa đủ bằng chứng "LỆCH MỐC CUỐI" theo cổng đăng ký.** Tai–ASR đồng thuận
  ở mức "có vấn đề", nhưng không xác nhận được cơ chế cắt.

## 3. A3 — code + offset

### 3.1 Code

- `tools/mfa_to_durations.py::compute_durations`:
  - yêu cầu **số từ TextGrid == số âm tiết manifest**; nếu lệch thì **loại clip**.
  - `gaps[-1] = frames_total - ends[-1]`: **toàn bộ audio còn lại sau từ cuối** (kể cả tiếng nói
    không có trong nhãn) được gán vào **gap đuôi**.
- `tools/cut_segments.py`:
  - `frame_range = [spans[start][0], spans[end-1][1] + segment_gaps[-1]]`;
  - `tail_cap_frames=67` (≈0,71 s) chỉ cắt bớt gap đuôi ở segment cuối clip, **không kiểm** đó là
    lặng hay tiếng nói.
- Hệ quả: nếu MFA gán phần nói dư vào SIL/`gaps[-1]` thay vì tạo word mới, **audio segment chứa từ
  không có trong text**; model học mel ở các frame gap đó. Đây là cơ chế **offset đuôi**, không phải
  drift theo thời gian.

### 3.2 Số đo trên 20 câu

- **9/20 câu** có `ASR last word end − label last syllable end > 0,1 s`.
- Tail extra: mean **0,177 s**, median **0,034 s**, std **0,305 s**; corr với độ dài audio **−0,027**
  ⇒ không phải drift, phù hợp **offset đuôi**.
- Ví dụ tái hiện:
  - `BD83pScFukQ_0093__s00`: label end 8,085 s, ASR last end 8,700 s ⇒ dư **0,615 s**.
  - `EUNlJU1BuzE_0300__s00`: 9,397 vs 10,000 ⇒ dư **0,603 s**.
  - `EM_ObHWvd94_0243__s00`: 8,597 vs 9,200 ⇒ dư **0,603 s**.
- Các mức dư này nằm trong trần `tail_cap_frames=67` (0,71 s) ⇒ khớp cơ chế code.

## 4. A4 — quét toàn bộ: CHƯA CHẠY

- Tổng audio: train **16,06 h** + holdout **2,48 h** = **18,54 h**; 20.837 segment.
- ASR `small` int8 trên M6 đo được ~5× realtime với beam 5; ước tính **3–4 h CPU** cho toàn bộ
  (chưa kể I/O/align).
- Trong lượt này **chưa chạy**; **chưa phân loại P0**. Đây là việc còn thiếu của V18.51.
- Nếu chạy, sẽ báo: số clip dư cuối ≥2 âm tiết / tổng; nếu ≥10% ⇒ **P0**, chặn mọi vòng acoustic.

## 5. A5 — sửa thử 40 clip

- Cắt tại `frame_range[0] + label_last_end + 0,05 s`; tạo bản trong thư mục riêng,
  **không ghi đè** dữ liệu gốc.
- Tự động:
  - CER ASR vs nhãn **≤0,1: 0/40** (0%).
  - **16/40 clip mất âm tiết cuối** (ASR không thấy âm cuối nhãn).
  - 34/40 không còn dư cuối.
- **Verdict: TRƯỢT TỰ ĐỘNG** — cắt tại mốc nhãn +0,05 s làm cụt âm cuối ở 40% clip.
  **Không dựng link tai, không áp lên data.**
- Nguyên nhân có thể: MFA `durations` cuối bị co / mốc cuối nhãn chưa đúng; cần align lại trước khi cắt.

## 6. A6 — hồ sơ

- Các số V18.43–V18.49 dùng mel/thời lượng gốc trên held-out (Δac, C_lo, CR, BAK TF) được đánh dấu
  **"có thể nhiễm lệch mốc cắt"**; so sánh chunk ít bị hơn. **Không mở lại cổng cũ.**
- Dòng rè cục bộ V18.50 tạm dừng; chỉ làm lại trên held-out đã sửa.

## 7. TỰ QUYẾT KHÁC ĐẶC TẢ

1. **A1 không có timestamp click thật** (trang chỉ ghi chỉ số âm tiết); mình ánh xạ chỉ số → ASR word
   timestamp. Ghi rõ đây là xấp xỉ, không phải click time gốc.
2. **A2 dùng ASR `small`**, không PhoWhisper-large; lý do: có sẵn, chạy CPU, 1,9 s/9,4 s. Đã ghi model.
3. **A5 tự động trượt** nên không gửi link tai; không đổi ngưỡng.
4. **A4 chưa chạy**; không phân loại P0. Cần 3–4 h CPU; xin ý kiến trước khi chạy dài.
5. Không train/production/ONNX/UTMOS.

## 8. Git log vòng này

```
329be2c đăng ký trước V1851 + 40 clip + đệm 0,05 s
b603baf A1/A2 ASR 20 câu; A3 code+offset; A5 sửa thử 40 clip (trượt auto)
```

## 9. Việc tiếp

1. **A4**: chạy quét toàn bộ (3–4 h) hoặc mẫu phân tầng ≥15% nếu A0 đổi luật; hiện **chưa có P0**.
2. **A5**: không áp bản sửa hiện tại; cần align lại mốc cuối (có thể dùng timestamp ASR + kiểm tai)
   trước khi thử lại.
3. **Không train**; P2 giữ nguyên; chờ A0 quyết sau A4/A5.

## 10. Test & trạng thái

- `pytest -q -rs`: **2.552 passed, 23 skipped** (ONNX đóng băng).
- `ruff check .`: sạch.
- **Trạng thái: DỪNG — A4 CHƯA CHẠY; A5 TRƯỢT TỰ ĐỘNG.**
