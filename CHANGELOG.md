# Changelog

## 2026-10-30 — v0.3.5

- **Sửa đóng gói Windows desktop**: `package-windows.ps1` thiếu tham số `$WebDir`
  nên gói desktop Windows v0.3.4 rơi mất `web/` (chỉ 8 file, 92 MB) trong khi gói
  CLI/server có web (40 file, 119 MB). Thêm `[string]$WebDir` + `[CmdletBinding()]`
  và chặn build nếu thiếu `web/index.html`.
- **CI guard**: kiểm tra `web/index.html` trong cả gói desktop và CLI trên
  macOS/Linux/Windows trước khi upload artifact.
- **Liên kết hai chiều ViFastKey ↔ ViFastTts**: mục **Sản phẩm** lớn giới thiệu cả hai
  sản phẩm; form **Góp ý** chuyển từ `/demo` sang landing để hiển thị công khai;
  ViFastKey hiển thị góp ý thành mục thay vì popup.
- **Thống kê web**: landing có mục **Thống kê** (`/api/stats`) và đếm lượt bấm nút tải
  theo nền tảng (`POST /api/download`); demo cũng ghi nhận lượt bấm tải.
- Version: **0.3.5**; Android `versionCode 13`, iOS build 9.

## 2026-10-30 — v0.3.4

- **Web Python + Space**: trang chủ mới dạng landing page — nghe thử nhanh, giới thiệu
  model, tab **tải xuống + hướng dẫn cài chi tiết từng nền tảng** (Windows/macOS/Linux/
  Android/iOS/Chrome/CLI/Web), mục model bundle, API/Python và FAQ. Demo đầy đủ chuyển
  sang `/demo` (Space: `demo.html`); hai bản HTML đồng bộ bằng
  `tools/sync_space_static.py`.
- Thêm **icon ⓘ giải thích Resolve OOV** ở mọi UI: web Python, Space, web Vite,
  extension, Android (mở dialog), iOS (info.circle + alert), desktop (hover), TUI (`ⓘ`).
- Giữ nguyên help panel "Giải thích các cài đặt" của v0.3.3.
- Version: **0.3.4**; Android `versionCode 12`, iOS build 8.

## 2026-10-30 — v0.3.3

- **Giải thích cài đặt trong mọi UI**: web Python, HF Space, web Vite, extension,
  Android, iOS, desktop và TUI đều có mục giải thích tốc độ, alpha, pause, peak,
  stream, max chunk, phương ngữ, **Resolve OOV**, từ điển/cách đọc, Local/Remote, RTF.
- **Resolve OOV**: giải thích rõ OOV là token lạ; bật để tra từ điển/đánh vần tên chữ cái
  (VNG → “vê en giê”), tắt để giữ fallback. Python web/Space có checkbox OOV thật và
  server Python đã nhận `resolve_oov` cho cả full/stream.
- **Space parity**: thêm phương ngữ, max ký tự/chunk, Resolve OOV và help panel.
- Android có nút **Giải thích các cài đặt** + ghi chú OOV; iOS có caption từng mục +
  DisclosureGroup; TUI có overlay `?`; desktop có mục gập.
- Version: **0.3.3**; Android `versionCode 11`, iOS build 7.

## 2026-10-30 — v0.3.2

- **Web Python + Space**: thêm lịch sử gần đây (localStorage, tối đa 8 câu, có RTF/audio),
  nút **Dừng** cho full/stream, chia sẻ WAV bằng Web Share API, phím **Esc** để huỷ.
- **Peak normalize + stream**: mọi UI tự bỏ qua peak khi stream (checkbox/toggle bị khoá,
  có ghi chú); tránh lỗi 422 và làm rõ peak cần đỉnh toàn file.
- **Python stream**: không giữ `_lock` toàn cục cho stream nữa; ORT session chạy song song
  được, và client ngắt generator không còn làm kẹt lock khiến request sau treo.
- **iOS**: huỷ tải model giữa chừng (nút Huỷ + tiến độ %/MB), nút tải model khi chưa có model,
  stream tự bỏ peak normalize.
- **TUI**: model browser dùng chung `ModelBrowserState` với desktop/CLI (bớt logic trùng).
- Version: Rust/Android/iOS/web/extension **0.3.2**; Android `versionCode 10`, iOS build 6.

## 2026-10-27

- Từ commit `60b5cf9`: thêm âm đầu **Q** cho chữ `qu` (onset thứ 25, ở cuối vocab;
  ID cũ 0–23 không đổi). Đây là chuẩn bị đa phương ngữ; N0 Bắc dùng Q-init (Q = K, bit-exact), fine-tune 3k là candidate.
- Checkpoint/ONNX trước commit này chưa có Q, `qu = K`, chỉ train giọng Bắc.
  Từ 28/10/2026 bỏ cờ `onset_has_q`, thay bằng `vocab_version` + `vocab_hash`; không có adapter Q→K.
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
- Test hiện tại: **2.909 pass / 24 skip**, `ruff` sạch; parser audit **49.104 tổ hợp, 0 lỗi**.
- TODO: nếu train một model chung nhiều vùng, bắt buộc thêm dialect/speaker embedding;
  train riêng từng vùng thì không cần.
- Từ điển override rút **570 → 204 mục**: bỏ alias ASR/tiền tố rác (`dipsic`→DeepSeek,
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
- Email: đọc được local part lạ thay vì bỏ mất (`khongdich@gmail.com`); thêm
  `khongdich → không dịch`, test hồi quy.
- Duyệt thêm các đề xuất đọc hợp lệ: `hotline`, `cover`, `coffee shop`, `feed`, `burger`,
  `cappuccino`, `Band`, `Kumarun`; loại `croissant`, `social media`, `workshop`, `backpack`,
  `smartphone` vì cách đọc sai/không phù hợp.
- Thêm `smartphone → sờ mát phôn`; sửa đề xuất tương ứng từ `sờ mát phone` và duyệt.
- Base N0 40k: kết quả teacher-forced + A/B + nhận xét tai người; tiếp tục 40k → 60k
  bằng cosine mới, chưa production.
- Base N0 60k xong: val plateau (40k 0,2493 → 60k 0,2476), benchmark 200 cho thấy
  base60 không vượt base40 rõ; chưa đổi production, chờ A/B 50–100 câu.
