# TRẠNG THÁI (STATUS) — nguồn sự thật duy nhất

> **Vòng hiện hành:** N0 + Q (27/10/2026) · **Tệp đặc tả:** `docs/Q_ONSET.md` +
> `docs/handoff/N0_DEPLOY.md` · **Commit code:** `8e78541` · **Trạng thái:** **LIVE (Q-init)** —
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
4. Demo có **cách đọc tự thêm**, từ điển **229 quy tắc tinh gọn** + fallback tiếng Anh,
   ví dụ STEM (hoá học/toán/vật lý/LaTeX),
   góp ý/báo lỗi và thống kê; nội dung góp ý còn khoá vì chưa đặt `ADMIN_PASSWORD`.
5. Test **2.941 pass / 24 skip**, `ruff` sạch; tài liệu cũ đã gom vào `docs/archive/`.

## 1. Đang chạy production

| Hạng mục | Giá trị |
| --- | --- |
| URL | https://vifasttts.hoctuthien.com/ |
| Health | `{"ok":true,"sample_rate":24000,"arch":"v2_slot5","vocab_version":"vi-q25-v1","vocab_hash":"…","alpha":1.5,"pause":"model"}` |
| Acoustic | N0 Ngọc Huyền **Q-init**; `runs/acoustic_ngochuyen_q/init_q.pt` sha256 `3c330cfcec9ad2…` |
| ONNX live | `artifacts/onnx/n0_q/acoustic.onnx` sha256 `df61599a15984dcc…`; vocoder `b3eb09cf5c3baa…` |
| Model bundle | [`.vfa`/`.vfts`](https://huggingface.co/dvchd/vifasttts-ngochuyen-small/tree/main/bundles) · ONNX `onnx/acoustic.onnx` sha256 `df61599a…` |
| Vocoder | Vocos pretrained `charactr/vocos-mel-24khz` (MIT), **không** fine-tune |
| Mặc định | alpha 1,5 · pause do model tự quyết · fixed pause tắt |
| Dữ liệu | `ngochuyen_voice` CC-BY-NC-4.0 · 19,89 h sạch · research/non-commercial |

**Vì sao Q-init:** Q là token thứ 25 ở cuối vocab; `Q = K` giữ output **bit-exact** với N0 Bắc cũ
(đã kiểm mel/durations/f0 trên câu có `quốc/quê/qua/quyển/quân`). Không có adapter Q→K runtime:
checkpoint/ONNX cũ thiếu `vocab_hash` không còn được hỗ trợ.

## 2. Bản ứng viên (chưa live)

| Hạng mục | Giá trị |
| --- | --- |
| Checkpoint | `runs/acoustic_ngochuyen_q/best.pt` sha256 `30dc4164246115…` |
| ONNX | `artifacts/onnx/n0_q_ft/acoustic.onnx` sha256 `394fa657fc6e52…` |
| Val mel hữu thanh | **0,26320** @3k (N0 cũ 0,26340) |
| Val rough | **0,76318** @3k (N0 cũ 0,7624) |
| Nghe thử | Release cũ đã xoá; artifact Q-init/QFT giữ local và trên HF |

Fine-tune **không thắng rõ cả mel và rough**; Q-init là bản an toàn đang live. Chỉ đổi khi
người dùng nghe và chọn; nếu đổi phải cập nhật ONNX/release/HF/`healthz` và ghi lại hash.

## 3. Release & Hugging Face

- **GitHub Releases:** bản mới nhất **v0.3.1** (30/10/2026) — Android 0.3.0,
  iOS simulator stream local/remote, desktop/CLI 3 nền tảng, extension, web,
  `.vfa/.vfts`; kèm `SHA256SUMS.txt`. Bản **v0.2.0** vẫn giữ để đối chiếu.
  Web Python + HF Space đã cập nhật link v0.3.1 (v0.3.1 sửa stream iOS dài).
- Hugging Face small: https://huggingface.co/dvchd/vifasttts-ngochuyen-small (ONNX Q, `.vfa`/`.vfts`).
- Bundle: https://huggingface.co/dvchd/vifasttts-ngochuyen-small/tree/main/bundles
- Base 60k sau Q: https://huggingface.co/dvchd/vifasttts-ngochuyen-base
- 3 WAV mẫu: https://huggingface.co/dvchd/vifasttts-ngochuyen-small/tree/main/demo (`fetch_demo_samples.sh`).
- Static Space: https://huggingface.co/spaces/dvchd/vifasttts-ngochuyen-demo

## 4. Demo / feedback / custom reading

- Custom reading **tự lưu `localStorage` khi gõ**; gửi duyệt khi bấm **Tạo âm thanh** nếu
  checkbox bật; server chỉ lưu cặp `key = value` dạng pending, không lưu câu/IP.
- Quy tắc người dùng **ưu tiên trước** STEM và 229 quy tắc có sẵn; fallback tiếng Anh
  (CASE_INSENSITIVE_ENGLISH + acronym) vẫn áp dụng sau parser.
- Ngày 27/10 đã kiểm lại từ điển: bỏ alias ASR/tiền tố rác, bỏ key một chữ cái; thêm
  viết tắt Việt + tên công nghệ; chi tiết ở `docs/NORMALIZER.md` mục “Kiểm toán từ điển”.
- Đã duyệt **32** đề xuất đọc trong backend; **15** đề xuất sai/không phù hợp bị loại;
  **0 pending**. Sửa nhẹ `canxi cacbonat`/`hiđrocacbonat`; `protein` được thêm bản đúng
  vào từ điển (các đề xuất `prô tê in`, `rô tê in` bị loại).
- **Base N0 @60k đã xong**: 40k → 60k chỉ cải thiện val ~0,7%, đã bão hòa thực dụng.
  Benchmark 200: base60 mel z 0,2637 / dB 3,576 / CER 0,0843 / pause 0,831 / tone C 0,980;
  base40 nhỉnh CER, base60 nhỉnh mel/pause/tone. Chưa thay production; cần A/B 50–100 câu.
- **Benchmark N0:** bộ `bench200` đóng băng; internal small/base40 + tham chiếu ZeroTTS/
  VieNeu v3 Turbo đã chấm; chi tiết + license/online policy ở `docs/BENCHMARK_N0.md`.
- `GET /api/overrides` trả `builtin`, `approved`, `stem` (H2O/CO2/H2SO4, 1/2, m/s, km/h,
  `\frac{a}{b}`); đọc thực tế do normalizer sinh.
- **Web Python stream:** `POST /api/tts/stream` (NDJSON PCM16) dùng chung
  `vifasttts.runtime.tts_engine.OnnxTtsEngine`; `/api/config` trả defaults/capabilities;
  UI web/Space có checkbox **Stream**. Chi tiết `docs/PYTHON_ENGINE.md`.
- Feedback/báo lỗi có trong web và Space; admin `/admin` xem thống kê + hàng chờ.
  **Chưa đặt `ADMIN_PASSWORD`** ⇒ nội dung feedback và nút duyệt còn khoá.
- Giới hạn: **3000 ký tự** (env `MAX_CHARS`), 6 request/phút/IP, một request đồng thời;
  UI hiển thị thời gian xử lý / audio / RTF sau mỗi lần tạo. Mỗi lúc chỉ 1 request tổng hợp;
  request sau chờ tối đa 45 s rồi 503 (không có queue nền).
- Web VPS có **3 mẫu nghe sẵn** `/static/samples/fresh01|02|04.wav` (không gọi API);
  WAV lấy từ [HuggingFace demo](https://huggingface.co/dvchd/vifasttts-ngochuyen-small/tree/main/demo), không commit.

## 5. Test / tài liệu

- `pytest -q`: **2.941 passed, 24 skipped** (~40 s).
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
