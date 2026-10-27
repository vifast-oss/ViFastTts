# Changelog

## 2026-10-27

- Từ commit `60b5cf9`: thêm âm đầu **Q** cho chữ `qu` (onset thứ 25, ở cuối vocab;
  ID cũ 0–23 không đổi). Đây là chuẩn bị đa phương ngữ; N0 Bắc dùng Q-init (Q = K, bit-exact), fine-tune 3k là candidate.
- Checkpoint/ONNX trước commit này chưa có Q, `qu = K`, chỉ train giọng Bắc.
  Model cũ thiếu cờ `onset_has_q=true` bị từ chối rõ ràng; không có adapter Q→K.
- `D/GI/R/V` vẫn là 4 token riêng; lý do là một số thổ ngữ Bắc Trung Bộ còn phân biệt
  (Trung bộ chính và Nam gộp D/GI; Nam đọc R khác D/GI).
- Sửa override cụm/domain: key có dấu chấm/space được áp trước tách token
  (`khongdich.com = không dịch chấm com`).
- `GET /api/overrides` + nút “Xem từ điển & STEM”: hiển thị cả ví dụ quy tắc STEM nội bộ
  (hoá học/toán/vật lý/LaTeX), kèm ghi chú quy tắc người dùng được ưu tiên.
- Thêm ví dụ rule hoá học/toán/LaTeX/vật lý trong UI; textarea 3 dòng đủ cao;
  cho phép ký tự `>`/`<` trong rule literal (vẫn escape khi hiển thị admin).
- Gọn UI “Cách đọc từ”: hướng dẫn dài chuyển vào icon ⓘ cạnh nhãn (giống “Nghỉ cố định”),
  giữ textarea + chip ví dụ; giảm chiều cao panel tùy chọn nâng cao.
- Bỏ nút **Lưu quy tắc** (đã tự lưu khi gõ) và **Xoá quy tắc** (xoá trực tiếp trong textarea);
  quy tắc vẫn gửi duyệt khi bấm **Tạo âm thanh** nếu checkbox bật.
- VPS demo có **3 mẫu nghe sẵn** phát trực tiếp (không gọi API); WAV ở release
  `n0-demo-samples-v1`, tải bằng `scripts/fetch_demo_samples.sh` (không commit).
- Nâng giới hạn demo lên **3000 ký tự** mặc định (`MAX_CHARS`; UI đọc `/api/config`),
  chunk nội bộ 300 ký tự; response `/api/tts` trả `X-Processing-Seconds`, `X-Audio-Seconds`,
  `X-RTF` và UI hiển thị thời gian xử lý / audio / RTF sau mỗi lần tạo.
- UI hiển thị đồng hồ **Đang tạo… Xs** trong lúc chờ để biết request vẫn chạy; không stream audio.
- Override cụm/domain tự gửi duyệt khi tạo âm thanh (nếu checkbox bật), không cần bấm Lưu trước.
- Bố cục lại giao diện: 3 cột trên desktop, tùy chọn nâng cao và góp ý hiện ngay;
  nghỉ cố định chuyển vào tùy chọn nâng cao, kèm tooltip giải thích.
- Thêm validator cảnh báo W sau phụ âm môi, allowlist `resources/loanword_labial_w.txt`
  (`buýt`, `voan`, `boa`).
- Quickstart: `fetch_ngochuyen_models.sh`/`run_ngochuyen_demo.sh` dùng thư mục `artifacts/onnx/n0_q`;
  PowerShell dùng đúng sha256 của gói Q (trước đó URL Q nhưng hash N0 cũ).
- Tài liệu: thêm `docs/README.md` (mục lục hiện hành/tham chiếu/lịch sử), viết lại
  `docs/handoff/TRANG_THAI.md` theo trạng thái live; chuyển thiết kế gốc, kế hoạch/review cũ,
  run @codelung và báo cáo V08–V18.52 vào `docs/archive/` (không xoá).
- Test hiện tại: **2.743 pass / 24 skip**, `ruff` sạch; parser audit **49.104 tổ hợp, 0 lỗi**.
- TODO: nếu train một model chung nhiều vùng, bắt buộc thêm dialect/speaker embedding;
  train riêng từng vùng thì không cần.
- Từ điển override rút **570 → 201 mục**: bỏ alias ASR/tiền tố rác (`dipsic`→DeepSeek,
  `dipick`, `dipix`, `analyer`, `antropic`...), bỏ key một chữ cái; thêm viết tắt Việt
  (`UBND`, `HĐND`, `TP.HCM`, `BHXH`, `BHYT`, `CCCD`, `GDP`, `CPI`, `FDI`, `VND`, `USD`...)
  và tên công nghệ phổ biến; sửa `bug`/`download`/`upload`/`windows`/`tensorflow`.
- Demo áp được override cụm có dấu chấm/khoảng trắng trước tokenizer; test mới
  `tests/test_overrides_tech.py`.
- Bổ sung viết tắt địa danh/doanh nghiệp/giáo dục theo góp ý người dùng: `HN`, `BD`, `ĐN`,
  `QL`, `CĐ`, `GD&ĐT`, `HS-SV`, `TBYT`, `BV`, `TNHH`, `CP`, `DN`, `DNTN`, `CK`, `VAT`,
  `ĐKKD`, `BĐS`, `Ngân hàng TMCP`, `VP`, `B công an`, `TƯ`; lưu ý `ĐN`/`CK` đa nghĩa.
- Lưu quy tắc local bền hơn: lưu thêm khi `change`/`pagehide`/tab ẩn; fallback
  `localStorage → sessionStorage`; báo lỗi nếu trình duyệt chặn cả hai.
- Duyệt 22/32 đề xuất cách đọc (10 loại): giữ STEM/hoá học/tên hợp lệ; loại các bản sai
  `VPS`, `\frac{a}{b} → a trên c`, `H2 + O2 → H2O` đọc sai, `protein`/`Gregor`/`Zizzi's`;
  sửa `canxi cacbonat`/`hiđrocacbonat`; thêm `protein` bản đúng.
