# ViFastTts — hướng dẫn cho agent

> TTS tiếng Việt **non-autoregressive, tất định**, chạy trên **Mac mini M6** (train MPS,
> inference ONNX CPU). Đọc file này trước khi sửa code; thiết kế + số đo nằm trong `docs/`.

## 1. Tài liệu nguồn (đọc theo thứ tự)

0. **`docs/README.md` — mục lục toàn bộ tài liệu** (hiện hành / tham chiếu / archive). Đọc trước
   khi tìm bất kỳ tài liệu nào; tài liệu cũ nằm ở `docs/archive/`, không dùng để quyết định.
1. `docs/ACOUSTIC_V2.md` — **thiết kế chốt + nhật ký số đo thực thi** acoustic v2 (§0–§51;
   §30–§51: chọn epoch/val theo số đo · b8 (small đạt ngưỡng) · base 40k · L1≠tai người ·
   rè ngã/nặng · pause/steady · data v3.1). Mâu thuẫn → mục mới hơn thắng.
2. **`docs/EVAL_TOOLS.md` — danh mục MỌI thước đo** (trong train + offline), lệnh chạy, bộ số mốc để so,
   quy trình "chấm một checkpoint" + **bẫy thống kê/điểm mù**. Đọc trước khi kết luận bất cứ điều gì.
3. `docs/B0_BASELINE.md` — baseline B0 (mốc cũ): mel hữu thanh ~9,6–9,8 dB; free CER 0,54.
4. `docs/handoff/TRANG_THAI.md` — trạng thái tổng; `docs/DATASET_V2.md` + `docs/TTS_ARCHITECTURE_RESEARCH.md` — nền.

**Nguyên tắc vàng: không nâng cấp gì trước khi có thước đo (và phải kiểm thước trên dữ liệu THẬT
trước khi dùng nó để quyết định — bài học §34.3→§36.4); mọi đề xuất phải kèm số đo + cổng.**

## 2. Môi trường & lệnh

- Python: `.venv/bin/python` (3.12.15 · torch 2.14.1 · pyworld · onnxruntime · typer · ruff).
- **Chạy lệnh từ repo root** (working dir `/Users/.../ViFastTts`).
- Lint (phải sạch): `.venv/bin/ruff check .` → tự sửa `--fix`.
- Test (phải pass 100%, **2.575 test pass / 24 skip**, ~40 s): `.venv/bin/python -m pytest -q`.
- CLI: `.venv/bin/vifasttts <command>` (`cache-features`, `train`, `export`, `synthesize-onnx`…).
- Push cần: `git -c credential.helper='!gh auth git-credential' push` (dòng
  `fatal: failed to store: -61` là vô hại, push vẫn thành công).

## 3. Bố cục

- `src/vifasttts/frontend/` — text → âm tiết; `segments.py` (role/weights, ưu tiên B2, mask F0 Addendum 6).
- `src/vifasttts/data/` — manifest, features (mel/f0/vuv/energy), cache, dataset, phonation, `v2_targets.py`.
- `src/vifasttts/models/` — `vifasttts.py` (v1), `slot_ops.py` (đóng băng R4), conformer, vocos, istftnet.
- `src/vifasttts/runtime/`, `export.py`, `train.py`, `cli.py`.
- `tools/` — script đo nghiên cứu (mỗi R/T một tool, ghi JSON vào `artifacts/`); `tests/` — unit test.
- `data/codelung/`, `cache/`, `runs/`, `artifacts/` — **local, KHÔNG commit** (đã gitignore).

## 4. Dữ liệu & cache (local)

- Manifest train/val: `data/codelung/{train,val}_clean_v2_dur_seg.jsonl` (row **segment**),
  bản `..._slot4.jsonl` thêm `seg_durations [N,4]` theo thứ tự **O, M, N, C**; holdout:
  `holdout_clean_v2_dur[_slot4].jsonl`. Row segment có `frame_range` (toạ độ clip cha) + `durations` + `gaps`.
- `seg_durations` thuộc **manifest** (không phải cache); checkpoint phải ghi `seg_method` /
  `seg_method_version` / `seg_weights_hash`.
- Cache: `cache/codelung_v2/` — khoá `feature_cache_key` = sha1(audio+mtime + block `mel`,
  `f0`, `phonation`, `sample_rate`). **Đổi các block đó = đổi toàn bộ khoá** → dùng config riêng,
  KHÔNG sửa `configs/small_codelung.yaml` (B0) khi thêm phonation — bản v2 là
  `configs/small_codelung_v2.yaml` (phonation enabled).
- Kênh cache v3: `mel, energy, f0, vuv, hnr, glottalization, jitter` (R6 — §20).

## 5. Quy ước kỹ thuật bắt buộc

- **Frame**: hop 256 @ 24 kHz; `T = 1 + len(wav)//hop`; mel 100 log-magnitude (hợp đồng Vocos).
- **F4**: mask hữu thanh luôn dùng `vuv > 0,5` — KHÔNG dùng `f0 > 0` (f0 đã nội suy qua vô thanh).
- **F0 mask (Addendum 6)**: slot O chỉ tính F0 loss khi `onset ∈ F0_VOICED_ONSETS` ∧ ratio ≥ 0,5;
  M/C ratio ≥ 0,5; N luôn (trọng số = tỷ lệ hữu thanh). Hằng số ở `frontend/segments.py`.
- **DCT**: `dct4_frames`/`idct4_frames` (trực giao, pos = (t+0,5)/n). Model dùng hệ số hình dạng
  `s_k = c_k/√n` (`slot_ops.build_f0_contour`; `s0 == mean`).
- **Chia slot B2**: `models/slot_ops.distribute_slots` ↔ `frontend/segments.distribute_frames`
  (cùng thuật toán, ưu tiên **N, O, C, M**). Bất biến: inactive = 0 · active ≥ 1 nếu đủ frame · Σ = d_syl.
- **ONNX**: opset 18, `dynamo=False`; **giữ nguyên tên + thứ tự output cũ**, chỉ **thêm output mới vào cuối**;
  `speed` là input float32 shape `[1]`; op trong graph phải export được (không vòng lặp động / argsort).
- **`arch`** trong checkpoint: `"v1_syl"` (mặc định khi thiếu) | `"v2_slot5"`; factory đọc `arch`;
  không load chéo bằng `strict=False` ngầm — chỉ warm-start có chủ đích (§11 ACOUSTIC_V2).
- `MAX_POSITIONS = 4096` frame (≈43,7 s @ hop 256) — chia câu trước model.
- **Batch > 1**: dùng `SameNBatchSampler` (gộp cùng N; `collate_slot_batch` không pad N). Batch tối ưu
  phải **ĐO** — trên M6: batch 1 = 0,229 s/mẫu · **8 = 0,0375** · 16 = 0,047 (không suy diễn; xem §29).
- **Trước mọi thay đổi train**: probe 60–100 bước (loss ổn định? s/bước? RAM MPS?) + nhớ LR phụ thuộc
  `max_steps` (đặt max_steps nhỏ → cosine hết sớm → LR ở sàn).
- Comment/docstring **tiếng Việt**, ngắn, nêu lý do.

## 6. Quy trình làm việc & commit

- Mọi thay đổi: chạy `ruff check .` + `pytest -q` trước khi commit; commit dạng
  `v2(<task>): <kết quả ngắn>`; kết thúc bằng push (lệnh ở §2).
- Một R/T xong phải có: **số đo + so mốc** (B0 hoặc số cũ) + cổng đạt/không + file thay đổi
  → ghi vào `docs/ACOUSTIC_V2.md` (số liệu trong doc; JSON thô ở `artifacts/` — local).
- **Không commit** `data/`, `cache/`, `runs/`, `artifacts/`.
- **Script sinh demo/thí nghiệm phải được promote vào `tools/` hoặc `src/` TRƯỚC khi dùng** (bài học sh25:
  bản đầu chỉ là script tạm, mất code, phải dựng lại — 14/10). Riêng làm nét mel = `runtime.postprocess.sharpen_mel`.
- **Demo audio**: *không* commit vào lịch sử repo; khi user cần nghe từ xa → đẩy bằng
  **GitHub Release asset** (vd `gh release create demo-audio-<ngày> artifacts/demo/*.wav`),
  xoá sạch về sau bằng `gh release delete <tag> --yes` (không cần force-push).
  **Upload xong PHẢI kiểm chứng** (đã từng "nói upload" mà quên chạy): `gh release view <tag>
  --json assets` + tải thử `curl -sL -o /dev/null -w '%{http_code} %{size_download}' <url>`.
  Link tải trực tiếp cho user: `https://github.com/dvchd/ViFastTts/releases/download/<tag>/<file>`.
  Nhãn file ghi rõ model + biến thể (`v2b8_sh15_*` = model b8, làm nét α=1,5) + cập nhật phần
  **notes** của release thành mục lục mỗi khi thêm bản mới.
- **Mỗi lần phát hành release mới** (tag/asset GitHub): bắt buộc cập nhật đồng thời
  `deploy/vifasttts_demo/static/index.html` (web Python) và `huggingface/space-static/index.html`
  (HF Space) sang tag mới; nếu đổi demo code thì deploy cả `deploy/vifasttts_demo/`.
  Deploy web qua `ssh root@jp` → `lxc exec hoctuthien-vps` (staging `/opt/vifasttts`,
  `docker compose up -d --build`); upload Space bằng `huggingface_hub` (token trong
  `~/.cache/huggingface`). **Sau khi deploy phải kiểm chứng**: tải thử từng link release
  trên cả `https://vifasttts.hoctuthien.com/` và Space, không chỉ nói đã cập nhật.
- **Sau mỗi lần deploy Python web** (kể cả không phát hành release): bắt buộc upload lại
  `huggingface/space-static/` lên HF Space, rồi kiểm tra `raw/main/index.html` + URL static;
  không được chỉ deploy VPS rồi báo xong. Space và web phải cùng version/tính năng.
- Báo cáo trung thực: nêu cả trường hợp trượt cổng + cảnh báo rõ.
- Quy trình 3 vai: Agent 0 (kiến trúc, ra addendum khi số đo khác kỳ vọng) · Agent 1 (soát code) ·
  Agent 2 (chạy trên M6). Sub-agent khi được giao việc **không tự commit** — trả file + cách chạy cho phiên chính.

## 7. Hiện trạng (27/10/2026)

> Chi tiết + việc còn lại: `docs/handoff/TRANG_THAI.md`. Mục lục tài liệu: `docs/README.md`.

- **Live:** `https://vifasttts.hoctuthien.com/` — ONNX FP32, `arch=v2_slot5`,
  `vocab_version=vi-q25-v1` / `vocab_hash`, alpha 1,5, `pause_mode=model`; model **N0 Ngọc Huyền Q-init** (`Q` = `K`,
  bit-exact với N0 Bắc cũ). Checkpoint nguồn `runs/acoustic_ngochuyen_q/init_q.pt`
  (sha256 `3c330cfc…`); ONNX live `artifacts/onnx/n0_q/acoustic.onnx` (sha256 `df61599a…`).
- **Q:** onset thứ 25 ở cuối vocab; cờ `onset_has_q` đã bỏ 28/10/2026, thay bằng
  `vocab_version` + `vocab_hash`; **không có adapter Q→K**. Fine-tune Q 3k (`runs/acoustic_ngochuyen_q/best.pt`) đã train/export
  nhưng **chưa live**; release nghe thử cũ đã xoá, artifact base/bundle nằm trên HuggingFace.
- **Demo:** custom reading local-first (gửi duyệt khi bật checkbox), 570 quy tắc có sẵn,
  mục STEM (hoá học/toán/vật lý/LaTeX), feedback/báo lỗi, admin thống kê. Feedback content
  còn khoá đến khi đặt `ADMIN_PASSWORD`.
- **Test:** 2.575 pass / 24 skip; `ruff` sạch. Parser audit: 49.104 tổ hợp, 0 lỗi.
- **Tài liệu:** tài liệu cũ đã gom vào `docs/archive/`; `TRANG_THAI.md` là nguồn trạng thái duy nhất.
- **Chốt kỹ thuật giữ nguyên:** chọn checkpoint cuối = **L1 + độ nét + thanh + rè + CER + tai**,
  KHÔNG chỉ L1; patience **0** cho cosine dài; batch 8 + `SameNBatchSampler`; batch 8 là mức tối ưu
  đã đo trên M6. Baseline codelung v2 (B0/b8/base 40k) giữ trong `docs/ACOUSTIC_V2.md` + `EVAL_TOOLS.md`.
- **Bẫy MPS đã gặp (đừng quên)**: SDPA+dropout cần grad; `ConvPredictor` backward N=1 abort → lọc
  `min_syllables=2` khi train; mọi test N=1-backward **không** được chạy trên MPS (giết tiến trình pytest);
  watchdog phải đặt **cả** HIGH+**LOW** watermark; `torch.onnx.export` v2 cần `no_grad` + submodule wrapper.
- **Bẫy quy trình**: upload demo phải **test tải**; đo bằng **hàm chuẩn của repo** (tự chế transform từng
  sai chuẩn hoá — §33.2); thước yếu che mất kết luận (§34.3 → §36.4).

## 8. Quy trình vòng (áp dụng từ vòng 08)

- **Chia vai theo loại câu hỏi**: câu trả lời được bằng **đo** ("số này từ đâu", "dữ liệu có lệch không")
  ⇒ **Agent 2 chạy và trả lời bằng số**; **Agent 1 chỉ kiểm độc lập diff sau mỗi commit** (vai trò bắt
  lỗi thật: probe no-op, lệnh train từ số 0, sha256 ghim sai, tệp thô lọt git).
- **Sub-agent khi cần góc nhìn khác họ** (từ vòng 11; dùng khi Agent 0 hết hạn mức hoặc cần phản biện
  đa chiều): phiên chính tự phóng sub-agent để phản biện/nghiên cứu; **ít nhất 1 sub-agent chạy model
  KHÁC HỌ với phiên chính** — mặc định **`opencode-go/muse-spark-1.3-contributor`** (Muse Spark 1.3
  Contributor). Sub-agent **chỉ đọc, KHÔNG sửa tệp repo**; mỗi nhiệm vụ ghi rõ phạm vi + câu hỏi + định
  dạng trả lời; không để 2 sub-agent trùng phạm vi; kết quả tóm tắt vào `docs/handoff/V<NN>_agent2.md`
  (mục **"PHẢN BIỆN NGOÀI"**) kèm model **+ giá** đã dùng.
- **Chi phí sub-agent — CHỈ model rẻ** (bổ sung 16/10, sau bài học gọi nhầm `gemini-4-argon-contributor`
  **$4/$20 mỗi M token** cho một nhiệm vụ nghiên cứu): trần giá **input ≤ $0,2/M token**; ưu tiên
  `muse-spark-1.3-contributor` ($0,1/$0,2) hoặc cùng nhóm rẻ (`claude-haiku-5-5`, `gpt-6-luna`,
  `mimo-v2.5`, các model `*-free`). **Không tự gọi dòng premium** (`gemini-4-argon` $4/$20 · `kimi-k3`
  $3/$15 · `grok-4.7`/`qwen3.8-max` $2/$6 · `glm-5.3` · `step-5-preview` · `kimi-k2.7-code` ·
  `hy4-preview` · `deepseek-v4-pro` · `qwen3.7-plus` · `minimax-m3`…) — chỉ dùng khi **người dùng yêu
  cầu đích danh**. Trước khi phóng sub-agent: **tra giá bằng công cụ `models`**; không rõ giá → dùng
  mặc định `muse-spark`.
- **Tệp quyết định nằm trong repo**: `docs/handoff/V<NN>_agent0.md` — Agent 2 lưu nguyên văn quyết định
  (kèm mã câu hỏi `V<NN>.B<k>` / `V<NN>.C<k>`), rồi báo commit hash. Agent 1 được nhắn đúng hash đó.
- **Mỗi vòng chỉ một tệp còn hiệu lực** + `docs/handoff/TRANG_THAI.md` là **nguồn duy nhất** (Agent 2
  cập nhật mỗi vòng). **Đầu tệp TRANG_THAI luôn ghi**: vòng hiện hành · tệp đặc tả · **commit gốc của vòng**
  (trước khi sửa) · **commit code cuối** (commit cuối TRƯỚC commit hồ sơ; HEAD luôn là commit hồ sơ —
  quy ước V11S.A3) · **trạng thái** (ĐANG LÀM / DỪNG, CHỜ ĐỌC) — Agent 1 tự tìm vòng để đọc
  từ đây, **không cần hash gửi kèm**.
- **Ba tệp hồ sơ, ba vai khác nhau** (V1842b.1): `TRANG_THAI.md` = trạng thái hiện hành (duy nhất);
  `DECISIONS.md` = nhật ký quyết định **chỉ ghi thêm**, theo mã (`V<NN>.A<k>` / `V<NN>b.<k>`);
  `EXCEPTIONS.md` = ngoại lệ **có phạm vi** đã được A0 chấp nhận. Hai tệp sau **không** ghi trạng thái
  hiện hành; mọi câu về trạng thái phải trỏ về `TRANG_THAI.md`. Không tạo `STATUS.md` song song.
- **Agent 1 chỉ đọc, KHÔNG ghi tệp vào repo** (không có `V0x_agent1.md`); báo cáo đọc của Agent 1 do người
  dùng chuyển cho Agent 0. Agent 2 ghi `docs/handoff/V<NN>_agent2.md` (báo cáo + mục TỰ QUYẾT KHÁC ĐẶC TẢ).
- **Đầu tệp chuẩn**: `VÒNG <NN> | Commit gốc: <hash> | Thay thế: …` + dòng `Agent 2 THỰC THI: Phần B |
  Agent 1 ĐỌC: Phần C | Người dùng: Phần D`.
- **Quyết định trước 3 nhánh** cho mỗi bước có rủi ro: đạt ⇒ làm X · trượt ⇒ dừng+báo · **kết quả lạ**
  ⇒ dừng+báo (kèm định nghĩa "lạ so với cặp đối chứng nào").
- **Mẫu báo cáo Agent 2**: commit · kết quả test · bảng số **theo đúng mã câu hỏi** · mục
  **"TỰ QUYẾT KHÁC ĐẶC TẢ"** (mọi thay đổi ngoài đặc tả, kể cả đổi bên đối chứng) · trạng thái **DỪNG/TIẾP**.
