# ViFastTts — Text-to-Speech tiếng Việt

**TTS tiếng Việt mã nguồn mở: nhỏ, nhanh, tự train được.** Toolkit nghiên cứu + triển khai
TTS **một giọng**, hiểu văn bản tiếng Việt, sinh giọng 24 kHz và xuất ONNX chạy CPU.
Mỗi checkpoint là một người nói, một phương ngữ — không cần `speaker_id`, `dialect_id`
hay audio mẫu.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-0f766e)](https://www.python.org/)
[![ONNX](https://img.shields.io/badge/runtime-ONNX%20CPU-0f766e)](docs/DEPLOYMENT.md)
[![Code MIT](https://img.shields.io/badge/code-MIT-18212b)](LICENSE)
[![Model research](https://img.shields.io/badge/model-research%20%2F%20non--commercial-b45309)](docs/NGOC_HUYEN.md)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97-Hugging%20Face-yellow)](https://huggingface.co/dvchd/vifasttts-ngochuyen-small)

## 0. Chạy demo Ngọc Huyền trong 2 phút

```bash
git clone https://github.com/dvchd/ViFastTts.git
cd ViFastTts
./scripts/run_ngochuyen_demo.sh
# Windows PowerShell:
# powershell -ExecutionPolicy Bypass -File .\scripts\run_ngochuyen_demo.ps1
# mở http://127.0.0.1:8090
```

Script tự tải ONNX FP32 (có kiểm sha256), tạo `.venv-demo`, cài `onnxruntime + fastapi + uvicorn`
và chạy web demo — **không cần torch**. Cần Python ≥ 3.11.

- **Demo online:** https://vifasttts.hoctuthien.com/
- **Hugging Face model:** https://huggingface.co/dvchd/vifasttts-ngochuyen-small
- **Space demo miễn phí:** https://huggingface.co/spaces/dvchd/vifasttts-ngochuyen-demo
- **Model/card:** `docs/NGOC_HUYEN.md`
- **Release:** [prod candidate](https://github.com/dvchd/ViFastTts/releases/tag/n0-ngochuyen-prod-v1) ·
  [research](https://github.com/dvchd/ViFastTts/releases/tag/n0-ngochuyen-research-v1)

### Chọn đúng luồng

**A. Người dùng model (không train, không cần torch):** chạy script ở trên, mở web, hoặc gọi
`synthesize-onnx`; dùng checkpoint/ONNX có sẵn. Không cần MFA, không cần dữ liệu.

**B. Người train model:** cài `.[dev,audio,train,onnx]`, chuẩn bị audio + transcript, chạy MFA,
cache, train, eval, export. Bắt đầu ở `docs/TRAINING_N0.md` (N0) hoặc `docs/TRAINING.md` (tổng quát).

> **Giấy phép model mẫu:** dataset `pnnbao-ump/ngochuyen_voice` là **CC BY-NC 4.0**.
> Model Ngọc Huyền chỉ dùng **nghiên cứu/phi thương mại**; không dùng giả giọng, lừa đảo
> hoặc production thương mại. Code repo là MIT.

![Luồng model N0](https://github.com/dvchd/ViFastTts/releases/download/n0-ngochuyen-research-v1/vifasttts_model_flow.png)

> **Đọc nhanh:** muốn hiểu kiến trúc → mục 2–3; muốn train lại → `docs/TRAINING_N0.md`;
> muốn triển khai → `docs/N0_DEPLOY.md`.

## 1. Dự án làm gì?

Ba khối chính, ghép lại thành một câu TTS hoàn chỉnh:

```text
Văn bản  ──▶  FRONTEND (tiếng Việt)  ──▶  MODEL (mel + thời lượng)  ──▶  VOCODER  ──▶  WAV
```

| Khối | Nhiệm vụ | Điểm mạnh |
| --- | --- | --- |
| **Frontend** | Chuẩn hoá số/ngày/giờ/đơn vị, tách âm tiết, chuyển thành **7 ID/âm tiết** | Phủ toàn bộ tiếng Việt chuẩn, không UNK; 3 vùng miền Bắc/Trung/Nam |
| **Model acoustic** | Từ 7 ID → dự đoán mel + thời lượng + f0/vuv/energy | Non-autoregressive, chạy tất định, xuất ONNX được |
| **Vocoder** | Từ mel → sóng 24 kHz | iSTFTNet nhẹ, có vòng huấn luyện GAN tham chiếu |

**Khác biệt cốt lõi:** thay vì đưa chuỗi ký tự hay BPE vào model, dự án mô tả mỗi âm tiết
bằng 5 thành phần ngôn ngữ học `âm đầu + âm đệm + âm chính + âm cuối + thanh điệu`
(cộng dấu câu/chấm câu — xem mục 7). Nhờ vậy: phát âm ổn định, dấu thanh không bao giờ sai
vị trí, và không có "từ lạ" với tiếng Việt chuẩn.

## 2. Trạng thái hiện tại (số liệu thật)

| Hạng mục | Kết quả |
| --- | --- |
| Bộ test | **2.565 test pass / 23 skip**; `ruff` sạch |
| Parser âm tiết | Vét cạn **49.166 tổ hợp = 0 lỗi**; 39K từ thật: 6.617/6.633 parse OK |
| Kho âm tiết | 24 âm đầu · 2 âm đệm · 15 âm chính · 11 âm cuối · 6 thanh → **264 vần**, **28.800 âm tiết trừu tượng** |
| Model | Acoustic small **6,1M** (N0) / base **16,4M**; Vocos pretrained **13,5M** |
| Sinh giọng | Web demo + `vifasttts synthesize` end-to-end (WAV 16-bit, 24 kHz); văn bản dài tự chia câu |
| Runtime ONNX | `vifasttts synthesize-onnx` chạy acoustic + vocoder ONNX, iSTFT numpy (không cần PyTorch) |
| Dịch vụ | FastAPI demo (`deploy/vifasttts_demo`, ONNX) · `vifasttts serve` · `synthesize-batch` · streaming |
| Xuất ONNX | fp32 / fp16 / int8, batch và độ dài **động** (đã kiểm bằng onnxruntime) |
| Huấn luyện | Train acoustic + train vocoder (GAN tham chiếu) + cache feature |
| Dữ liệu YouTube | `vifasttts youtube-fetch`: tải audio + phụ đề kênh của bạn → clip 24 kHz mono + manifest + SRT mở + dataset card (CC BY 4.0), báo cáo từ lạ (OOV) + `--overrides` |

**Model mẫu có sẵn:** **Ngọc Huyền small 6,1M** (research/non-commercial) trong GitHub release;
repo không chứa file `.pt`/`.onnx` để giữ clone nhẹ — script quickstart tự tải ONNX.
Muốn train giọng khác, xem `docs/TRAINING.md` + `docs/TRAINING_N0.md`.

### Model Ngọc Huyền — số đo chính

| | |
|---|---|
| Dữ liệu | 21,57 h raw → **19,89 h sạch**; train 17,9 h |
| Train | small v2_slot5, **60k bước**, ~5 h 46 trên Mac mini M6 |
| Holdout | mel L1 **4,0 dB** (z 0,298); duration MAE 1,37 frame |
| Free-run | **16,57 dB**; length 0,999; pause F1 **0,825** |
| Thanh điệu | thật 0,9835 · copy 0,9784 · free **0,9743** |
| A/B tai | **24/24** chọn model mới so P2 zero-shot |
| Tốc độ thực tế | **RTF 0,045** end-to-end, ONNX CPU trên VPS (5 câu, 22,44 s audio / 1,01 s xử lý) |

Chi tiết + license: **`docs/NGOC_HUYEN.md`**.

## 3. Luồng hoạt động trong 30 giây

```text
1) CHUẨN BỊ:   WAV + CSV  →  manifest.jsonl  (+ cache feature, kiểm coverage)
2) TRAIN:      manifest   →  acoustic model (dự đoán mel/duration/f0)  → best.pt
                           vocoder riêng (mel → sóng)                 → vocoder.pt
3) SUY LUẬN:   text  →  7 ID/âm tiết  →  mel dự đoán  →  vocoder  →  out.wav
4) XUẤT:       best.pt  →  model.onnx  (chạy bằng ONNX Runtime, fp32/fp16/int8)
```

Điểm cần nhớ để hiểu code:

- **Train dùng thời lượng thật** (teacher forcing); **suy luận tự dự đoán** thời lượng.
- **Không sampling** — cùng đầu vào cho cùng đầu ra.
- Token không phải tiếng Việt vẫn chạy được (fallback), không bao giờ crash.

Chi tiết đầy đủ (tensor shape, công thức loss, số tham số): `docs/MODEL_FLOW.md`.

## 4. Cài đặt

Yêu cầu Python ≥ 3.11.

**Chỉ muốn tạo âm thanh ngay (ONNX, không torch):**

```bash
git clone https://github.com/dvchd/ViFastTts.git
cd ViFastTts
./scripts/run_ngochuyen_demo.sh
# Windows:
# powershell -ExecutionPolicy Bypass -File .\scripts\run_ngochuyen_demo.ps1
# http://127.0.0.1:8090
```

**Phát triển / train / xuất ONNX:**

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev,audio,train,onnx]"
```

Bản tối thiểu (frontend/CLI, không cần torch): `pip install -e .`.

## 5. Thử nhanh

```bash
# Demo web Ngọc Huyền (tải ONNX lần đầu, chạy local)
./scripts/run_ngochuyen_demo.sh
# Windows PowerShell:
# powershell -ExecutionPolicy Bypass -File .\scripts\run_ngochuyen_demo.ps1
# hoặc macOS/Linux: make demo-ngochuyen

# Xem một câu được tách thành âm tiết và 5 thành phần thế nào
vifasttts parse "Hôm nay trời đẹp."
vifasttts parse-syllable "quốc"
vifasttts check-profile "voan bình" --profile strict   # cảnh báo chính tả/từ vay
vifasttts g2p "quốc" --dialect south                   # phiên âm IPA (phân tích)

# So sánh phiên âm IPA Bắc/Nam (chỉ để phân tích)
python examples/g2p_demo.py

# Lấy dữ liệu từ kênh YouTube của bạn (demo 1 video ngắn, cần: pip install -e ".[youtube]")
vifasttts youtube-fetch "https://www.youtube.com/@codelung/videos" --out data/codelung --demo

# Phiên bản CLI
vifasttts --version
```

Kiểm chứng toàn bộ pipeline bằng test (tự tạo dữ liệu tí hon, train 2 bước, sinh WAV, xuất ONNX):

```bash
pytest
```

## 6. Các lệnh chính

| Nhóm | Lệnh |
| --- | --- |
| Frontend | `vifasttts parse "<câu>"` · `parse-syllable <từ>` · `check-profile "<câu>" --profile strict` · `g2p "<câu>" [--dialect south]` |
| Dữ liệu | `build-manifest` · `validate-manifest` (kèm coverage) · `build-lexicon` · `cache-features` · `youtube-fetch` (tải kênh của bạn) |
| Huấn luyện | `vifasttts train ...` · `vifasttts train-vocoder ...` |
| Sinh giọng | `vifasttts synthesize --text "..." --output out.wav [--dialect south] [--speed 0.9] [--overrides file.json] [--peak-normalize]` |
| Batch / dịch vụ | `synthesize-batch --input list.txt --output-dir out/` · `serve --host 127.0.0.1 --port 8000` |
| Xuất | `vifasttts export-onnx ... [--precision fp16\|int8]` · `export-vocoder-onnx ...` |
| Runtime ONNX | `vifasttts synthesize-onnx --acoustic model.onnx --vocoder vocoder.onnx --text "..." --output out.wav [--provider cpu\|cuda\|coreml\|tensorrt]` |
| Khác | `vifasttts --version` |
| Kiểm tra | `pytest` · `ruff check .` · `mypy src/vifasttts` · `tools/parser_audit.py` · `tools/frontend_benchmark.py` · `tools/dataset_report.py` · `tools/split_manifest.py` |

<details>
<summary>Ví dụ đầy đủ (bấm để mở)</summary>

```bash
# Dữ liệu: metadata.csv có dạng  id|text
vifasttts build-manifest --metadata data/metadata.csv --wav-dir data/wavs --output data/manifest.jsonl
vifasttts validate-manifest --manifest data/manifest.jsonl --wav-dir data/wavs

# Huấn luyện
vifasttts train --config configs/base_24k.yaml \
  --train-manifest data/train.jsonl --val-manifest data/val.jsonl --output runs/base
vifasttts train-vocoder --config configs/base_24k.yaml \
  --manifest data/train.jsonl --output runs/vocoder

# Sinh giọng + xuất ONNX
vifasttts synthesize --config configs/base_24k.yaml \
  --checkpoint runs/base/best.pt --vocoder-checkpoint runs/vocoder/last.pt \
  --text "Xin chào, đây là hệ thống thử nghiệm." --output out.wav
vifasttts export-onnx --config configs/base_24k.yaml \
  --checkpoint runs/base/best.pt --output artifacts/model.onnx --precision fp16
vifasttts export-vocoder-onnx --config configs/base_24k.yaml \
  --checkpoint runs/vocoder/last.pt --output artifacts/vocoder.onnx

# Chạy lại chỉ với ONNX Runtime (không cần PyTorch)
vifasttts synthesize-onnx --acoustic artifacts/model.onnx --vocoder artifacts/vocoder.onnx \
  --text "Xin chào" --output onnx.wav --peak-normalize

# Batch và dịch vụ HTTP
vifasttts synthesize-batch --config configs/base_24k.yaml --checkpoint runs/base/best.pt \
  --input data/cau.txt --output-dir data/wavs_out
vifasttts serve --config configs/base_24k.yaml --checkpoint runs/base/best.pt --port 8000
# → curl -X POST localhost:8000/synthesize -d '{"text":"Xin chào"}' -o out.wav
#   (kèm GET /health, GET /info)
```

</details>

Trên **Mac Apple Silicon**: `training.device: auto` (mặc định) chạy acoustic bằng **MPS**,
vocoder bằng **CPU** (đo thực tế nhanh hơn trên máy nhỏ); số đo và ước lượng thời gian cho
Mac mini M6 32GB nằm ở `docs/TRAINING_ESTIMATES.md` §3.1.

## 7. Âm tiết tiếng Việt trong dự án (dễ hiểu)

Mỗi âm tiết (một "tiếng") gồm 5 phần + dấu câu. Ví dụ `quốc`:

| Phần | Trong `quốc` | Có bao nhiêu giá trị | Ví dụ khác |
| --- | --- | --- | --- |
| Âm đầu (onset) | `K` | 24 | `b`, `ch`, `ng`, `qu`... |
| Âm đệm (medial) | `W` | 2 (không có / có) | `oa`, `uy`, `qu`... |
| Âm chính (nucleus) | `Ô` | 15 | `a`, `ie`, `uo`, `oo`... |
| Âm cuối (coda) | `C` | 11 | `ng`, `nh`, `i`, `u`... |
| Thanh điệu | `SAC` (sắc) | 6 | ngang, huyền, hỏi, ngã, nặng |

Cộng thêm **chấm câu** và **ranh giới từ/câu** → mỗi âm tiết là **7 con số** đưa vào model.
Giải thích từ đầu cho người không chuyên: `docs/SYLLABLE_GUIDE.md`.

## 8. Cấu trúc repo

```text
src/vifasttts/
  frontend/   chuẩn hoá text, tách âm tiết, vocab, G2P (phân tích), lexicon/profile, segments, chunking
  data/       manifest, features (mel/f0/vuv/energy/phonation), dataset, cache, subtitles + youtube (tải kênh của bạn)
  models/     acoustic model, conformer, iSTFTNet vocoder, discriminator
  runtime/    chạy ONNX (acoustic + vocoder), iSTFT numpy, postprocess
  train.py    vòng huấn luyện acoustic + vocoder
  infer.py    text → WAV (PyTorch)
  export.py   ONNX (acoustic + vocoder) + quantization
configs/      base_24k.yaml + small_24k.yaml + large_24k.yaml + small_ngochuyen.yaml + ...
tools/        parser_audit, compute_mel_stats, train_chunked, n0_social_card, ... 
deploy/       vifasttts_demo/ (FastAPI ONNX + Dockerfile + static page)
scripts/      fetch_ngochuyen_models.sh · run_ngochuyen_demo.sh · run_A2_fixgap.sh
tests/        2.565 test: parser, normalizer, G2P, model, train/infer/export, ONNX, server
docs/         toàn bộ tài liệu (xem mục 10), gồm TRAINING_N0.md / NGOC_HUYEN.md / N0_DEPLOY.md
```

## 9. Giới hạn hiện tại & việc còn lại

- **Alignment**: pipeline N0 dùng **MFA thật** (6.989/6.989 TextGrid). Với dữ liệu mới, nên chạy MFA/aligner; nếu chưa có, code dùng chia theo trọng số (placeholder), chất lượng thấp hơn.
- **Vocoder**: bản tham chiếu (GAN nhẹ MPD-lite) + **bản nâng cấp MPD đầy đủ 2/3/5/7/11 + MRD + MR-STFT**
  (`discriminator: mpd_mrd`, chạy khối MPS) — xem `docs/REVISION_PLAN_V2.md` §10; GTA fine-tune sẽ làm sau.
- **ONNX**: đã export N0 FP32 (acoustic + Vocos) và runtime CPU; demo dùng ONNX. Chưa gộp vocoder vào một graph duy nhất/INT8 calibration đầy đủ.
- **OOV**: từ ngoài tiếng Việt đọc bằng fallback — muốn kiểm soát thì bật `resolve_oov=True`, dùng `--overrides file.json` hoặc thêm override.
- **Một checkpoint = một giọng, một phương ngữ** (đúng thiết kế; muốn đa giọng phải tách lớp riêng).

Roadmap chi tiết có đánh dấu ✅/⬜: `docs/handoff/TRANG_THAI.md`.

## 10. Tài liệu — nên đọc gì trước?

| Nhóm | Tài liệu | Nội dung |
| --- | --- | --- |
| **Bắt đầu ở đây** | `docs/handoff/TRANG_THAI.md` | Trạng thái tổng, quyết định quan trọng, việc còn lại |
| | `docs/MODEL_FLOW.md` | Luồng model chi tiết: data → train → inference → export |
| | `docs/SYLLABLE_GUIDE.md` | Hướng dẫn tách âm tiết cho người không chuyên |
| | `docs/GLOSSARY.md` | Thuật ngữ (âm đầu/đệm/chính/cuối, toàn ánh/song ánh...) |
| **Frontend** | `docs/FRONTEND.md` | Parser, profile/lexicon, segments, G2P, OOV |
| | `docs/NORMALIZER.md` | Số/ngày/giờ theo vùng miền, dấu thanh, i/y |
| | `docs/STEM_NORMALIZER.md` | Toán/LaTeX, hoá học, đơn vị vật lý |
| | `docs/G2P_VIETNAMESE.md` | Khảo sát sea-g2p, viG2P... và bảng IPA nội bộ |
| **Model & dữ liệu** | `docs/ARCHITECTURE.md` | Sơ đồ as-built, quyết định thiết kế |
| | `docs/DATA_PIPELINE.md` | 15 bước chuẩn bị dữ liệu |
| | `docs/YOUTUBE_DATASET.md` | Lấy dataset sạch từ kênh YouTube của bạn (demo + chạy thật, giấy phép mở) — kèm quy trình tái hiện đầy đủ |
| | `docs/R6_DIARIZATION_RESULTS.md` | **Lọc giọng tự động** (NVIDIA Nemotron 3 Diarization): tách TTS/AI/demo, số liệu + kiểm chứng |
| | `docs/TRAINING.md` | Hướng dẫn train + cảnh báo alignment |
| | `docs/TRAINING_N0.md` | **Run N0 Ngọc Huyền**: pipeline, thời gian, chọn 5–20 h small / 30–50 h base |
| | `docs/NGOC_HUYEN.md` | Model card model mẫu, license, quickstart |
| | `docs/N0_DEPLOY.md` | ONNX + service `vifasttts.hoctuthien.com` |
| | `docs/HUGGINGFACE.md` | Hugging Face model + Space static demo |
| | `docs/TRAINING_RUN_CODELUNG.md` | **Run thật `small` trên kênh @codelung**: số đo MPS, cách chạy lại, triển khai |
| | `docs/REVISION_PLAN_V2.md` | **Kế hoạch sửa nền tảng** trước khi lên base (A1 mel loss, A2 f0 contour, A3 SIL, MFA, mel log-magnitude) |
| | `docs/ARCH_DISCUSSION_M6.md` | **Hồ sơ thảo luận kiến trúc/ngân sách** cho Mac mini M6 32GB + đặc thù dữ liệu @codelung (gửi chuyên gia vòng 4) |
| | `docs/TRAINING_ESTIMATES.md` | **Ước lượng** dữ liệu/tham số/thời gian/máy/chi phí trước khi train |
| | `docs/APPLE_SILICON.md` | **Mac/M-series**: MPS, MLX, ANE, provider ONNX (đo thật + quyết định) |
| | `docs/DEPLOYMENT.md` | ONNX Runtime, quantize, nền tảng |
| **Nghiên cứu** | `docs/SYLLABLE_SYSTEMS_RESEARCH.md` | So sánh mô hình tách/gộp âm tiết (quốc tế + Việt Nam) và audit biên |
| | `docs/TTS_ARCHITECTURE_RESEARCH.md` | Khảo sát họ kiến trúc TTS + đề xuất tương lai |
| **Thiết kế gốc** | `docs/DESIGN_V1_MIEN_BAC.md`, `docs/DESIGN_V2.md`, `docs/FULL_DESIGN.md` | Bản thiết kế ban đầu (tham khảo lịch sử) |
| **Khác** | `docs/RUST_ROADMAP.md` | Kế hoạch port Rust (tối ưu triển khai) |
| | `docs/LICENSES.md` | Giấy phép các thành phần tham chiếu |

## 11. Giấy phép

**Code repo: MIT.** Dữ liệu giọng nói, lexicon, checkpoint và model mẫu có giấy phép riêng;
các công cụ tham chiếu (sea-g2p, MFA, vPhon...) giữ giấy phép gốc — xem `docs/LICENSES.md`.

**Model Ngọc Huyền:** dataset `pnnbao-ump/ngochuyen_voice` là **CC BY-NC 4.0**; checkpoint/
ONNX/weights chỉ dùng **nghiên cứu, phi thương mại**, không dùng giả giọng hoặc production
thương mại. Dataset lấy từ kênh YouTube của bạn mặc định ghi **CC BY 4.0** (ghi nguồn kênh),
đổi bằng `--license`, ví dụ `--license "CC0 1.0"`.
