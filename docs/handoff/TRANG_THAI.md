# TRẠNG THÁI (STATUS) — nguồn sự thật duy nhất

> **Vòng hiện hành:** N0 + Q (27/10/2026) · **Tệp đặc tả:** `docs/Q_ONSET.md` +
> `docs/handoff/N0_DEPLOY.md` · **Commit code:** `78b429a` · **Trạng thái:** **LIVE (Q-init)** —
> chờ chọn Q-init hay fine-tune 3k.
>
> Tài liệu cũ: `docs/archive/handoff/TRANG_THAI_2026-10-27_pre_N0_live.md` (lịch sử, không hiệu lực).
> Mục lục tài liệu: `docs/README.md`. Nhật ký quyết định: `DECISIONS.md`; ngoại lệ: `EXCEPTIONS.md`.

## 0. Năm dòng cho người không kỹ thuật

1. Web **https://vifasttts.hoctuthien.com/** đang chạy model N0 Ngọc Huyền bằng ONNX CPU.
2. Bản đang chạy là **Q-init**: thêm âm đầu `Q` cho chữ `qu` nhưng `Q` được khởi tạo bằng `K`,
   nên giọng Bắc giữ nguyên từng mẫu âm thanh so với N0 cũ.
3. Bản **fine-tune Q 3k** đã train xong, hay hơn rất nhẹ về độ nét nhưng **chưa được chọn**;
   đang có 2 file nghe thử trong release tạm.
4. Demo có **cách đọc tự thêm**, từ điển **203 quy tắc tinh gọn** + fallback tiếng Anh,
   ví dụ STEM (hoá học/toán/vật lý/LaTeX),
   góp ý/báo lỗi và thống kê; nội dung góp ý còn khoá vì chưa đặt `ADMIN_PASSWORD`.
5. Test **2.743 pass / 24 skip**, `ruff` sạch; tài liệu cũ đã gom vào `docs/archive/`.

## 1. Đang chạy production

| Hạng mục | Giá trị |
| --- | --- |
| URL | https://vifasttts.hoctuthien.com/ |
| Health | `{"ok":true,"sample_rate":24000,"arch":"v2_slot5","onset_has_q":true,"alpha":1.5,"pause":"model"}` |
| Acoustic | N0 Ngọc Huyền **Q-init**; `runs/acoustic_ngochuyen_q/init_q.pt` sha256 `3c330cfcec9ad2…` |
| ONNX live | `artifacts/onnx/n0_q/acoustic.onnx` sha256 `16e66b70b9c49c…`; vocoder `b3eb09cf5c3baa…` |
| Release asset | `n0_onnx_fp32_q.zip` sha256 `ef35567c4433cf…` (trong release `n0-ngochuyen-prod-v1`) |
| Vocoder | Vocos pretrained `charactr/vocos-mel-24khz` (MIT), **không** fine-tune |
| Mặc định | alpha 1,5 · pause do model tự quyết · fixed pause tắt |
| Dữ liệu | `ngochuyen_voice` CC-BY-NC-4.0 · 19,89 h sạch · research/non-commercial |

**Vì sao Q-init:** Q là token thứ 25 ở cuối vocab; `Q = K` giữ output **bit-exact** với N0 Bắc cũ
(đã kiểm mel/durations/f0 trên câu có `quốc/quê/qua/quyển/quân`). Không có adapter Q→K runtime:
checkpoint/ONNX cũ thiếu `onset_has_q=true` bị từ chối rõ ràng.

## 2. Bản ứng viên (chưa live)

| Hạng mục | Giá trị |
| --- | --- |
| Checkpoint | `runs/acoustic_ngochuyen_q/best.pt` sha256 `30dc4164246115…` |
| ONNX | `artifacts/onnx/n0_q_ft/acoustic.onnx` sha256 `394fa657fc6e52…` |
| Val mel hữu thanh | **0,26320** @3k (N0 cũ 0,26340) |
| Val rough | **0,76318** @3k (N0 cũ 0,7624) |
| Release nghe thử | `q-preview-2026-10-27`: `init.wav` (Q-init) + `finetune.wav` (3k) |

Fine-tune **không thắng rõ cả mel và rough**; Q-init là bản an toàn đang live. Chỉ đổi khi
người dùng nghe và chọn; nếu đổi phải cập nhật ONNX/release/HF/`healthz` và ghi lại hash.

## 3. Release & Hugging Face

- `n0-ngochuyen-prod-v1` — prod candidate nội bộ, có `n0_onnx_fp32.zip` (N0 cũ) và
  **`n0_onnx_fp32_q.zip`** (Q-init, đang live).
- `n0-ngochuyen-research-v1` — research, dùng ONNX N0 cũ; không có Q.
- `q-preview-2026-10-27` — **preview tạm**, chỉ 2 WAV; xoá sau khi chọn xong.
- `n0-demo-samples-v1` — 3 WAV mẫu nghe sẵn cho VPS (pre-release; `fetch_demo_samples.sh`).
- Hugging Face model: https://huggingface.co/dvchd/vifasttts-ngochuyen-small (ONNX Q đã cập nhật).
- Static Space: https://huggingface.co/spaces/dvchd/vifasttts-ngochuyen-demo

## 4. Demo / feedback / custom reading

- Custom reading **tự lưu `localStorage` khi gõ**; gửi duyệt khi bấm **Tạo âm thanh** nếu
  checkbox bật; server chỉ lưu cặp `key = value` dạng pending, không lưu câu/IP.
- Quy tắc người dùng **ưu tiên trước** STEM và 203 quy tắc có sẵn; fallback tiếng Anh
  (CASE_INSENSITIVE_ENGLISH + acronym) vẫn áp dụng sau parser.
- Ngày 27/10 đã kiểm lại từ điển: bỏ alias ASR/tiền tố rác, bỏ key một chữ cái; thêm
  viết tắt Việt + tên công nghệ; chi tiết ở `docs/NORMALIZER.md` mục “Kiểm toán từ điển”.
- Đã duyệt **31** đề xuất đọc trong backend; **16** đề xuất sai/không phù hợp bị loại;
  **0 pending**. Sửa nhẹ `canxi cacbonat`/`hiđrocacbonat`; `protein` được thêm bản đúng
  vào từ điển (các đề xuất `prô tê in`, `rô tê in` bị loại).
- `GET /api/overrides` trả `builtin`, `approved`, `stem` (H2O/CO2/H2SO4, 1/2, m/s, km/h,
  `\frac{a}{b}`); đọc thực tế do normalizer sinh.
- Feedback/báo lỗi có trong web và Space; admin `/admin` xem thống kê + hàng chờ.
  **Chưa đặt `ADMIN_PASSWORD`** ⇒ nội dung feedback và nút duyệt còn khoá.
- Giới hạn: **3000 ký tự** (env `MAX_CHARS`), 6 request/phút/IP, một request đồng thời;
  UI hiển thị thời gian xử lý / audio / RTF sau mỗi lần tạo. Mỗi lúc chỉ 1 request tổng hợp;
  request sau chờ tối đa 45 s rồi 503 (không có queue nền).
- Web VPS có **3 mẫu nghe sẵn** `/static/samples/fresh01|02|04.wav` (không gọi API);
  WAV lấy từ release `n0-demo-samples-v1`, không commit.

## 5. Test / tài liệu

- `pytest -q`: **2.743 passed, 24 skipped** (~40 s).
- `ruff check .`: sạch.
- Parser audit: **49.104 tổ hợp, 0 vấn đề**; wordlist 39K: 6.617/6.633 parse OK.
- Tài liệu hiện hành: `docs/README.md`; lịch sử: `docs/archive/README.md`.
- `docs/handoff/` chỉ còn `TRANG_THAI`, `DECISIONS`, `EXCEPTIONS`, `N0_DEPLOY`, `N0_RELEASE`,
  `N0_agent2`, `NGUYEN_DATA`; các báo cáo vòng cũ đã chuyển vào `docs/archive/handoff/`.

## 6. Việc tiếp theo (theo thứ tự)

1. **Chọn model live:** giữ Q-init (an toàn) hoặc deploy fine-tune 3k. Nếu deploy: export/verify,
   cập nhật `N0_DEPLOY`, release, HF, `healthz`; nếu giữ: xoá release preview.
2. **Đặt `ADMIN_PASSWORD`** nếu muốn đọc/gửi duyệt feedback và suggestion.
3. Test `scripts/run_ngochuyen_demo.ps1` trên Windows thật (chưa có máy).
4. Duyệt các suggestion custom reading đang chờ (sau khi có mật khẩu).
5. Nếu cần mở rộng: đọc `docs/ACOUSTIC_V2.md` §51 và `docs/EVAL_TOOLS.md` trước khi đề xuất train.

## 7. Lịch sử ngắn (không dùng để quyết định)

- **B0** (13/10): baseline acoustic v1, mel hữu thanh 9,6–9,8 dB, CER 0,54.
- **v2/b8/base 40k** (14–20/10): chuỗi acoustic v2 trên codelung; b8 và base 40k là mốc đo,
  không phải model Ngọc Huyền.
- **N0** (26–27/10): dataset `ngochuyen_voice`, small 6,1M 60k, holdout 4,0 dB,
  free-run 16,57 dB, ONNX live.
- **Q** (27/10): thêm Q, Q-init live, fine-tune 3k candidate.
- Chi tiết lịch sử: `docs/archive/handoff/TRANG_THAI_2026-10-27_pre_N0_live.md` và
  `docs/archive/README.md`.

## 8. Quy ước

- Chỉ tệp này được ghi **trạng thái hiện hành**; `DECISIONS.md` chỉ ghi thêm quyết định;
  `EXCEPTIONS.md` chỉ ghi ngoại lệ có phạm vi.
- Mọi thay đổi production phải kèm: hash model/ONNX, `healthz`/smoke test, release/HF nếu có,
  và một dòng cập nhật ở đây.
- Tài liệu hết hiệu lực chuyển vào `docs/archive/`, không xoá.
