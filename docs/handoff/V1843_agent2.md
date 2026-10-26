# V18.43 — Agent 2: đo trước khi quyết định (A2/A3/A4/A6/A7 + A1c)

> **Trạng thái: DỪNG, CHỜ ĐỌC.** Không train, không đổi production.
> **Commit gốc của vòng**: `7cd61ef` · **Code cuối trước hồ sơ**: `1be3cf6`
> · **Tệp đặc tả**: `V1842_agent0.md` (V18.42 + V18.42b).
> Báo cáo này là commit hồ sơ; HEAD sau commit là commit hồ sơ theo V11S.A3.

## 0. Tóm tắt

| Mã | Kết quả | Trạng thái |
|---|---|---|
| A7 | Hồ sơ 3 tệp, archive PROJECT_STATUS, đóng mã V11, phân loại 19 khoảng trống | **XONG** (`208b0c2`) |
| A3 | ONNX **TRƯỢT**: short p95 1,2188× (>1,2), cold 0,632 (>0,5), size 0,318 (>0,3); chỉ RSS 0,456 đạt | **TRƯỢT — đề nghị đóng nhánh** (`2e28c55`) |
| A6 | PyTorch/ONNX CPU **bit-exact**; fast 3 câu 5,1 s; full 20 câu có BAK/UTMOS | **XONG** (`13c3ef6`) |
| A1c | Parity đầy đủ **12/12** với `ONNX-EXC-001`, 0 lỗi ngoài ngoại lệ | **XONG** (`72dc937`, `1be3cf6`) |
| A2 | **Đối chứng âm hỏng** (seed UTMOS lệch 0,073; CI không chứa 0) ⇒ không kết luận, giữ chunk | **DỪNG, BÁO** (`49bb2e7`) |
| A4 | **Acoustic là nguồn chính**: Δac **0,2481**, Δvoc **−0,0214**; mel/parity đầu vào đạt | **TIẾP** (`f78e042`) |

- **Không chuyển ONNX production.** A3 trượt theo luật đã đăng ký; A1c chỉ chứng minh *đúng số học*, không chứng minh *có lợi*.
- **Hợp đồng sản phẩm vẫn là chunk mode** (A2 không kết luận được vì phép đo hỏng).
- **Chất lượng**: A4 chỉ ra acoustic, không phải vocoder/dữ liệu; chưa train, chờ A0 + ngân sách.

## 1. A7 — hồ sơ

- `docs/handoff/TRANG_THAI.md` giữ vai trò **nguồn sự thật duy nhất**; tiêu đề đổi thành
  "TRẠNG THÁI (STATUS)".
- Thêm `docs/handoff/DECISIONS.md` (V1842.A1–A8 + V1842b.1–b.6, chỉ ghi thêm) và
  `docs/handoff/EXCEPTIONS.md` (ONNX-EXC-001 + khối JSON máy đọc).
- `AGENTS.md` §1/§8 cập nhật: ba tệp ba vai; không tạo `STATUS.md` song song.
- `docs/PROJECT_STATUS.md` (13/10) → `docs/archive/PROJECT_STATUS_2026-10-13.md`, đầu tệp ghi
  "LỊCH SỬ"; các liên kết ngoài archive đã trỏ về `TRANG_THAI.md`.
- Mã V11 còn treo: đóng/chuyển backlog đủ 11 mục; V11.B9 (SẮC-tắc) chuyển backlog chất lượng.
- Nhánh dữ liệu v3/v34: ghi "đã thử, không thắng, đóng".
- 19 khoảng trống dossier §7: P0 = #2 (RAM/cold/latency — A3 lấp trong vòng này), #8 (mel_hash — đã lấp),
  #9 (vocoder production — đã lấp); còn lại P1. Không còn P0 mở.

## 2. A3 — benchmark ONNX vs PyTorch

Máy: Mac mini M6, macOS 27.0.1, Python 3.12.15, torch 2.14.1, onnxruntime 1.31.0, numpy 1.26.4.
CPU 2 thread (`torch.set_num_threads(2)`, `VIFASTT_INTRA_THREADS=2`, `OMP/MKL=2`), chunk mode,
`target_lufs=-16`, warmup 3, 20 lần/câu, 5 câu/loại. Máy chạy một mình; đã dừng server demo 8788.

| Loại câu | PT p95 (s) | ONNX p95 (s) | Tỷ lệ p95 | CV lặp lại | Kết |
|---|---:|---:|---:|---:|---|
| Ngắn (~8 âm tiết) | 0,3101 | 0,3780 | **1,2188** | 0,9 % | **TRƯỢT** |
| Vừa (~40) | 1,0391 | 1,1035 | 1,0619 | 0,8 % | đạt |
| Dài (~250) | 15,9110 | 15,9514 | 1,0025 | 12,5 % (pooled) | đạt |

| Tiêu chí phụ | PyTorch | ONNX | Tỷ lệ | Ngưỡng | Kết |
|---|---:|---:|---:|---:|---|
| Cold start (p50, 5 lần) | 0,980 s | 0,620 s | **0,632** | ≤0,5 | **TRƯỢT** |
| Peak RSS (p50, 5 lần) | 501,3 MB | 228,4 MB | **0,456** | ≤0,6 | **ĐẠT** |
| Dung lượng cài (venv sạch) | 0,759 GB / 31 gói | 0,241 GB / 22 gói | **0,318** | ≤0,3 | **TRƯỢT** |
| `.[onnx]` có kéo torch? | — | **Không** | — | phải không | ĐẠT |

- **Kết luận A3: TRƯỢT.** Chỉ peak RSS đạt; p95 ngắn vượt 1,6 điểm %; cold vượt 26 %; dung lượng vượt 6 %.
- **Đề nghị theo V1842.A3**: đóng nhánh ONNX (đóng băng artifact + hash, giữ parity ở trạng thái skip có lý do,
  bỏ khỏi lộ trình), **trừ khi** người dùng xác nhận có nhu cầu triển khai không PyTorch.
- Hash kiểm trước khi bấm giờ: model khớp `configs/onnx_candidate_v1841.json`; output WAV khớp hash parity
  (`cab907…`), nên phép đo đúng artifact.
- PyTorch MPS tham chiếu (không dùng quyết định): ngắn 0,244/0,285 s; vừa 0,921/0,994 s; dài 12,004/15,488 s (p50/p95).

## 3. A6 — golden set & tất định

- **Tất định** (`artifacts/bench/v1843_golden/determinism.json`):
  - PyTorch CPU: bit-exact cả **2 lần trong cùng tiến trình** và **2 tiến trình riêng** (mel + wav).
  - ONNX CPU: bit-exact cả hai cách.
  - MPS: cũng bit-exact trong phép thử này; vẫn **không** đưa vào fast test (chỉ tolerance theo luật).
- **Fast test**: 3 câu (OOV, số/viết tắt, nhiều dấu câu), CPU, chunk mode, hash mel + wav cho PyTorch CPU
  và ONNX CPU. `pytest` đo **5,1 s**; dưới trần 30 s.
- **Baseline fast** ở `eval/golden/v1843/` (JSON 3,2 KB + NPZ 1,8 MB) — không đặt trong `eval/baselines/`
  vì `.gitignore` chỉ cho tệp mốc gọn.
- **Full baseline** 20 câu (`v1843_golden_full.json`), marker `slow`, chạy tay:

| Biến thể | BAK trung bình | UTMOS trung bình (5 seed) |
|---|---:|---:|
| PyTorch chunk | 4,0198 | 1,5441 |
| PyTorch sentence | 4,0025 | 1,5577 |
| ONNX chunk | 4,0199 | 1,5442 |

- Baseline ghi kèm phiên bản torch/ORT/numpy/OS; lệch phiên bản ⇒ test FAIL với thông báo cập nhật baseline.
- Test mới: `tests/test_golden_v1843.py` (1 pass) + `tests/test_onnx_exceptions.py` (4 pass).

## 4. A1c — ngoại lệ ONNX-EXC-001

- `EXCEPTIONS.md` có khối JSON máy đọc; `tools/v1840_onnx_parity.py` đọc và chỉ áp ngoại lệ khi đúng
  input + tầng + mode + provider + hash model.
- Chạy parity đầy đủ trong thư mục riêng `artifacts/bench/v1843_a1c_parity/` (không ghi đè artifact lịch sử v18.40):

| Hạng mục | Kết quả |
|---|---|
| Acoustic | **36/36** |
| Vocoder | **12/12** (1 ngoại lệ có định danh) |
| End-to-end chunk | **12/12** |
| Frontend | **12/12** |
| Ngoại lệ áp dụng | **ONNX-EXC-001** |
| Lỗi spectrum ngoài ngoại lệ | **0** |
| Tất định | cả hai runtime |

- Test âm: cùng row nhưng id khác vẫn **FAIL**; đổi hash model thì ngoại lệ **không** áp dụng.
- **Lưu ý**: `ready_to_switch_onnx=True` chỉ nói *đúng số học*; A3 trượt nói *không có lợi vận hành*.

## 5. A2 — chunk vs sentence

30 câu có dấu câu (drift_texts), P2 PyTorch, −16 LUFS, UTMOS 5 seed [0..4], bootstrap ghép cặp 10.000.

| Chỉ số | Giá trị | CI95 | Diễn giải |
|---|---:|---|---|
| ΔUTMOS (sentence − chunk) | **−0,0666** | [−0,1269, −0,0056] | sentence **kém** hơn theo UTMOS |
| ΔBAK | **+0,0989** | [+0,0754, +0,1242] | sentence **ít rè** hơn theo BAK |
| Đối chứng âm (cùng audio chunk, seed 5–9 vs 0–4) | **+0,0729** | [+0,0177, +0,1274] | **KHÔNG chứa 0** |

- **Đối chứng âm hỏng**: nhiễu seed UTMOS (0,073) cùng cỡ với hiệu ứng cần đo. Theo luật A2:
  **PHÉP ĐO HỎNG — dừng, báo, không kết luận**.
- Hợp đồng sản phẩm **giữ chunk**. Không dùng kết quả này để chọn sentence.
- Ghi nhận "lạ có ích": BAK nói sentence ít rè hơn rõ, UTMOS nói kém hơn; nhưng phép đo không hợp lệ,
  nên **không** hành động. Nếu cần phân xử, phải làm lại với nhiều seed hơn/thiết kế khác và đăng ký trước.

## 6. A4 — nguồn rè

40 câu holdout (8 video), 4 tầng: A = wav gốc; B = Vocos(mel gốc); C = Vocos(mel P2, TF thời lượng gốc);
C' = Vocos(mel g1_1k, cùng cách). Tất cả −16 LUFS.

### 6.1 Kiểm tra đầu vào (bắt buộc)

- **Mel config khớp Vocos**: sr 24.000 · n_fft 1.024 · hop 256 · 100 bin · f_min 0 · f_max 12.000 ·
  log-magnitude · norm none · clamp 1e-7. ONNX metadata khớp sau khi ép kiểu. **ĐẠT**.
- **Tool C không-TF khớp CLI**: 3 câu, `max_abs = 0,0`, `rmse = 0,0`, RMS ratio 1,0. **ĐẠT**.

### 6.2 Kết quả

| Tầng | BAK trung bình | Nhiễu lặng trung vị (dB) | Flatness 2–8k trung vị |
|---|---:|---:|---:|
| A (gốc) | 3,9685 | −59,79 | 0,4558 |
| B (Vocos + mel gốc) | 3,9899 | −58,97 | 0,4604 |
| C (P2 + TF) | **3,7419** | −63,52 | **0,5189** |
| C' (g1_1k + TF) | 3,7318 | −62,96 | 0,4932 |

- **Δvoc = BAK(A) − BAK(B) = −0,0214** (vocoder không làm xấu BAK; B còn nhỉnh hơn A).
- **Δac = BAK(B) − BAK(C) = +0,2481** (acoustic làm xấu BAK rõ).
- **Nhánh: acoustic** (Δac ≥ 0,15 và ≥ 2×Δvoc). Không sát ngưỡng (±0,03), không phi đơn điệu.
- Chỉ số phụ: nhiễu lặng A→B **+0,031 dB**, B→C **−1,982 dB**; flatness A→B **+1,21 %**, B→C **+12,87 %**
  (dưới 20 %). Vì nhánh đã là acoustic, chỉ số phụ không dùng để đổi nhánh.
- **Cảnh báo**: BAK(C) xấu hơn nhưng nhiễu khoảng lặng B→C lại **giảm**; BAK có thể phản ứng với buzz/artifact
  ngoài khoảng lặng, không phải "rè nền" thuần. Cần đo thêm buzz/flatness theo slot trước khi train.
- C' (g1_1k) không tốt hơn C (BAK 3,7318 vs 3,7419), nhất quán với việc G1 chưa từng thắng.
- 5 câu nghe tham khảo: `artifacts/bench/v1843_a4/samples/index.html` (A/B/C; không dùng để quyết định).

## 7. TỰ QUYẾT KHÁC ĐẶC TẢ

1. **A3 chạy một mình**: đã `launchctl remove vifasttts.listen` + tắt `http.server 8788` trước khi đo;
   không chạy job nặng song song. Server demo **không tự bật lại** (nếu cần nghe, chạy lại
   `tools/serve_listen_demo.sh`).
2. **Sửa thước CV**: lần đo đầy đủ tính CV gộp 5 câu khác độ dài ⇒ 18–19 %, bị coi là "lạ" sai.
   Đã sửa sang **CV lặp lại trong từng câu** và đo lại short/mid; long giữ lần đo đầy đủ (CV pooled 12,5 %).
   Kết quả cuối dùng short/mid từ `result_shortmid.json`, long từ `result.json`.
3. **Vị trí baseline A6**: `eval/golden/v1843/` thay vì `eval/baselines/` vì `.gitignore` chỉ cho tệp mốc gọn;
   NPZ 1,8 MB cần thiết để áp tolerance.
4. **A1c chạy parity đầy đủ trong thư mục riêng** `artifacts/bench/v1843_a1c_parity/` để không ghi đè
   artifact lịch sử v18.40; thêm biến `V1840_OUT` cho tool.
5. **A2 đối chứng âm** dùng seed [5..9] so với [0..4] trên cùng audio chunk, đúng luật "hai bộ seed".
6. **A4 C'** dùng checkpoint `g1_1k` live (không EMA), đúng lịch sử sàng lọc; C dùng P2 EMA production.
7. **MPS bit-exact** trong phép thử A6 (không kỳ vọng); vẫn chỉ tolerance, không vào fast test.

## 8. Việc tiếp (đề nghị, chưa làm)

1. **A0 quyết ONNX**: A3 trượt ⇒ theo V1842.A3 **đóng nhánh ONNX** (đóng băng artifact/hash, parity skip có lý do,
   bỏ khỏi lộ trình), trừ khi người dùng xác nhận cần bản không PyTorch. Nếu cần, phải chấp nhận short chậm 1,22×
   và ghi rõ lý do.
2. **A2**: chỉ làm lại nếu vẫn cần phân xử chunk/sentence; tăng số seed UTMOS hoặc dùng thiết kế ít nhiễu hơn,
   đăng ký trước. Hiện hợp đồng = chunk.
3. **A4 → V18.45**: chỉ mở train acoustic khi (a) A0 duyệt, (b) người dùng duyệt ngân sách (~60k bước ≈ 7 h),
   (c) có giả thuyết cụ thể. Trước đó nên đo thêm buzz/flatness theo slot C để giải thích việc BAK xấu mà
   nhiễu lặng giảm.
4. **Không** mở lại GAN, dữ liệu v3/v34, P2 4k/6k nếu không có giả thuyết mới; A4 không chỉ ra vocoder/dữ liệu.

## 9. Test & trạng thái

- `pytest -q`: **2.570 passed**, 46 warning, ~49 s.
- `ruff check .`: sạch.
- Test mới: `tests/test_onnx_exceptions.py` (4), `tests/test_golden_v1843.py` (1).
- **Trạng thái: DỪNG, CHỜ ĐỌC.** Không train, không đổi production.
