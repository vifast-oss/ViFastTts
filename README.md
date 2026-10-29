<p align="center">
  <img src="resources/brand/vifasttts-lockup-cream.png" alt="ViFastTts · Giọng đọc tiếng Việt" width="620">
</p>

# ViFastTts — Text-to-Speech tiếng Việt

[![ci](https://github.com/dvchd/ViFastTts/actions/workflows/ci.yml/badge.svg)](https://github.com/dvchd/ViFastTts/actions/workflows/ci.yml)

## Tải và dùng trên Windows (không cần build)

**Cách nhanh nhất:** tải ZIP → giải nén → chạy `vifasttts-desktop.exe`.

1. Vào [Releases v0.1.1](https://github.com/dvchd/ViFastTts/releases/tag/v0.1.1) và tải
   [`vifasttts-desktop-windows-x64.zip`](https://github.com/dvchd/ViFastTts/releases/download/v0.1.1/vifasttts-desktop-windows-x64.zip)
   (~92 MB).
2. Chuột phải file ZIP → **Extract All** (đừng chạy trực tiếp trong file ZIP).
3. Mở thư mục vừa giải nén → chạy `vifasttts-desktop.exe`.
4. Nếu SmartScreen cảnh báo: **More info → Run anyway** (bản chưa ký số).
5. Gõ tiếng Việt → bấm **Đọc**. Model, vocoder, ONNX Runtime và web đã nằm trong gói.

Không cần Python, Node, GPU, tài khoản HuggingFace hay mạng. Cần Windows 10/11 x64;
nếu máy thiếu DLL hệ thống, cài **VC++ 2015–2022 x64**.

### Chọn file theo nhu cầu

| Nhu cầu | File tải |
|---|---|
| **Windows, dùng ngay** | `vifasttts-desktop-windows-x64.zip` |
| macOS Apple Silicon | `vifasttts-desktop-macos-arm64.zip` |
| Linux x64 | `vifasttts-desktop-linux-x64.tar.gz` |
| Android | `vifasttts-mobile-android.apk` |
| iOS Simulator | `vifasttts-mobile-ios-simulator.zip` |
| Chrome extension | `vifasttts-extension.zip` |
| CLI/TUI/server | `vifasttts-cli-windows-x64.zip` (hoặc macOS/Linux tương ứng) |
| Web tĩnh riêng | `web-dist.tar.gz` (nâng cao) |

Tất cả nằm trong [release v0.1.1](https://github.com/dvchd/ViFastTts/releases/tag/v0.1.1).
Hướng dẫn chi tiết + xử lý lỗi: **[`docs/INSTALL.md`](docs/INSTALL.md)**.

## Tìm model từ HuggingFace: bản nào cần server?

| Ứng dụng | Cách tìm model | Cần bật server? |
|---|---|---|
| **Desktop** | Gọi HuggingFace API trực tiếp trong app | **Không** |
| CLI / TUI | Gọi HuggingFace API trực tiếp | **Không** |
| Web mở qua server | Gọi `/api/models/*` của server | Có (server đang phục vụ web) |
| Chrome extension | Gọi `/api/models/*` của server | Có (mặc định `http://127.0.0.1:8000`) |
| Android / iOS | Trực tiếp HuggingFace nếu Server URL trống; hoặc server LAN | **Không bắt buộc** |
| Web tĩnh (file HTML) | Không tìm; nạp `.vfa/.vfts` thủ công | Không |

- **Desktop** dùng `vifasttts-model-manager` + HuggingFace adapter trực tiếp. Nút
  **Bật server** trong desktop chỉ để phục vụ web/extension/điện thoại; nó **không**
  cần thiết cho việc tìm model của chính desktop.
- **Extension** không gọi HuggingFace trực tiếp. Nó gọi server để tránh CORS và để
  server kiểm hash; nếu server tắt, extension vẫn đọc được model bundled nhưng
  không tìm/tải model mới.
- **Android/iOS** ưu tiên tải trực tiếp HuggingFace khi Server URL để **trống**
  (native không bị CORS). Nếu muốn dùng server để kiểm hash/catalog tập trung, nhập
  `http://192.168.1.100:8000` (cùng Wi-Fi/LAN), bật **Cho phép LAN** trên desktop
  và mở firewall. Điện thoại không dùng được `127.0.0.1` của máy tính.
- **Web** khi được server phục vụ dùng API server; bản web tĩnh chỉ nạp bundle thủ công.
- Model browser chỉ hiện file `.vfa`/`.vfts`; raw `acoustic.onnx` là file nội bộ/dev.

## Dành cho developer

Phần còn lại của README dành cho build/train/kiến trúc. Nếu chỉ muốn dùng app, bạn có thể
dừng ở mục Windows phía trên.

---

**TTS tiếng Việt mã nguồn mở: nhỏ, nhanh, tự train được.** Toolkit nghiên cứu + triển khai
TTS **một giọng**, hiểu văn bản tiếng Việt, sinh giọng 24 kHz và xuất ONNX chạy CPU.
Mỗi checkpoint là một người nói, một phương ngữ — không cần `speaker_id`, `dialect_id`
hay audio mẫu.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-C6281E)](https://www.python.org/)
[![ONNX](https://img.shields.io/badge/runtime-ONNX%20CPU-C6281E)](docs/DEPLOYMENT.md)
[![Code MIT](https://img.shields.io/badge/code-MIT-1F2430)](LICENSE)
[![Model research](https://img.shields.io/badge/model-research%20%2F%20non--commercial-b45309)](docs/NGOC_HUYEN.md)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97-Hugging%20Face-yellow)](https://huggingface.co/dvchd/vifasttts-ngochuyen-small)

## 0. Chạy demo bằng Python (tuỳ chọn, cho developer)

```bash
git clone https://github.com/dvchd/ViFastTts.git
cd ViFastTts
./scripts/run_ngochuyen_demo.sh
# Windows PowerShell:
# powershell -ExecutionPolicy Bypass -File .\scripts\run_ngochuyen_demo.ps1
# mở http://127.0.0.1:8090
```

Script tự tải ONNX FP32 **Q-init** từ HuggingFace (có kiểm sha256), tạo `.venv-demo`,
cài `onnxruntime + fastapi + uvicorn` và chạy web demo — **không cần torch**. Cần Python ≥ 3.11.
Người dùng Windows bình thường nên dùng bản desktop ở trên; mục này chỉ dành cho dev/CLI.

- **Demo online:** https://vifasttts.hoctuthien.com/
- **Hugging Face model:** https://huggingface.co/dvchd/vifasttts-ngochuyen-small
- **Space demo miễn phí:** https://huggingface.co/spaces/dvchd/vifasttts-ngochuyen-demo
- **Thống kê demo:** https://vifasttts.hoctuthien.com/admin
- **Góp ý / báo lỗi:** form trên web và Space; admin xem tại `/admin` sau khi đặt
  `ADMIN_PASSWORD` (nội dung bị khoá nếu chưa đặt).
- **Model/card:** `docs/NGOC_HUYEN.md`
- **Model bundles:** [.vfa/.vfts](https://huggingface.co/dvchd/vifasttts-ngochuyen-small/tree/main/bundles) ·
  [base 60k sau Q](https://huggingface.co/dvchd/vifasttts-ngochuyen-base) ·
  [3 mẫu nghe](https://huggingface.co/dvchd/vifasttts-ngochuyen-small/tree/main/demo)
- **App release:** [v0.1.1](https://github.com/dvchd/ViFastTts/releases/tag/v0.1.1)

### Chọn đúng luồng

**A. Người dùng model (không train, không cần torch):** chạy script ở trên, mở web, hoặc gọi
`synthesize-onnx`; dùng checkpoint/ONNX có sẵn. Không cần MFA, không cần dữ liệu.

**B. Người train model:** cài `.[dev,audio,train,onnx]`, chuẩn bị audio + transcript, chạy MFA,
cache, train, eval, export. Bắt đầu ở `docs/TRAINING_N0.md` (N0) hoặc `docs/TRAINING.md` (tổng quát).

> **Giấy phép model mẫu:** dataset `pnnbao-ump/ngochuyen_voice` là **CC BY-NC 4.0**.
> Model Ngọc Huyền chỉ dùng **nghiên cứu/phi thương mại**; không dùng giả giọng, lừa đảo
> hoặc production thương mại. Code repo là MIT.

![Luồng model N0](https://huggingface.co/dvchd/vifasttts-ngochuyen-small/resolve/main/assets/og-image.png)

> **Đọc nhanh:** muốn hiểu kiến trúc → mục 2–3; muốn train lại → `docs/TRAINING_N0.md`;
> muốn triển khai → `docs/handoff/N0_DEPLOY.md`.

## 1. Dự án làm gì?

Ba khối chính, ghép lại thành một câu TTS hoàn chỉnh:

```text
Văn bản  ──▶  FRONTEND (tiếng Việt)  ──▶  MODEL (mel + thời lượng)  ──▶  VOCODER  ──▶  WAV
```

| Khối | Nhiệm vụ | Điểm mạnh |
| --- | --- | --- |
| **Frontend** | Chuẩn hoá số/ngày/giờ/đơn vị, tách âm tiết, chuyển thành **7 ID/âm tiết** | Phủ toàn bộ tiếng Việt chuẩn, không UNK; normalizer có nhánh Bắc/Trung/Nam (mức văn bản) |
| **Model acoustic** | Từ 7 ID → dự đoán mel + thời lượng + f0/vuv/energy | Non-autoregressive, chạy tất định, xuất ONNX được |
| **Vocoder** | Từ mel → sóng 24 kHz | iSTFTNet nhẹ, có vòng huấn luyện GAN tham chiếu |

**Khác biệt cốt lõi:** thay vì đưa chuỗi ký tự hay BPE vào model, dự án mô tả mỗi âm tiết
bằng 5 thành phần ngôn ngữ học `âm đầu + âm đệm + âm chính + âm cuối + thanh điệu`
(cộng dấu câu/chấm câu — xem mục 7). Nhờ vậy: phát âm ổn định, dấu thanh không bao giờ sai
vị trí, và không có "từ lạ" với tiếng Việt chuẩn.

## 2. Trạng thái hiện tại (số liệu thật)

| Hạng mục | Kết quả |
| --- | --- |
| Bộ test | **2.916 test pass / 24 skip**; `ruff` sạch |
| Parser âm tiết | Vét cạn **49.104 tổ hợp = 0 lỗi**; 39K từ thật: 6.617/6.633 parse OK |
| Kho âm tiết | 25 âm đầu (thêm Q) · 2 âm đệm · 15 âm chính · 11 âm cuối · 6 thanh → **264 vần** |
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

> **Vocab Q:** từ commit `60b5cf9`, onset **Q** đứng cuối vocab (ID cũ không đổi) cho chữ `qu`.
> Checkpoint/ONNX mới mang `vocab_version` + `vocab_hash`; artifact cũ không còn được hỗ trợ,
> không dùng adapter Q→K. Bản **đang live** là Q-init (`Q = K`, bit-exact N0 Bắc cũ);
> fine-tune Q 3k đã train/export nhưng **chưa chọn**; release nghe thử cũ đã xoá
> (29/10/2026), artifact base/bundle nằm trên [HuggingFace](https://huggingface.co/dvchd/vifasttts-ngochuyen-small/tree/main/bundles).
> Xem `docs/Q_ONSET.md`, `CHANGELOG.md`, `docs/SYLLABLE_GUIDE.md`.

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
| Âm đầu (onset) | `Q` | 25 | `K`, `b`, `ch`, `ng`, `tr`... |
| Âm đệm (medial) | `NONE` | 2 (không có / có) | `W` trong `hoa`, `quất`, `uy`... |
| Âm chính (nucleus) | `UÔ` | 15 | `A`, `IÊ`, `ƯƠ`, `OO`... |
| Âm cuối (coda) | `C` | 11 | `N`, `NG`, `NH`, `J`, `W`... |
| Thanh điệu | `SAC` (sắc) | 6 | ngang, huyền, hỏi, ngã, sắc, nặng |

`quốc` = `Q + NONE + UÔ + C + SAC`: chữ `u` thuộc nguyên âm đôi `uô`, **không phải
âm đệm `W`**; giọng Bắc đọc `quốc` giống `cuốc` (`cuốc` = `K + NONE + UÔ + C + SAC`),
nhưng Q/K là hai token riêng. So sánh `quất` = `Q + W + Â + T + SAC`.

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
resources/    brand/ (logo, favicon, OG image, manifest; xem resources/brand/README.md)
deploy/       vifasttts_demo/ (FastAPI ONNX + Dockerfile + static page)
scripts/      fetch_ngochuyen_models.sh · run_ngochuyen_demo.sh · run_A2_fixgap.sh
tests/        2.916 test: parser, normalizer, G2P, model, train/infer/export, ONNX, server
docs/         toàn bộ tài liệu (xem mục 10 + docs/README.md); N0 deploy ở docs/handoff/N0_DEPLOY.md
```

## 9. Giới hạn hiện tại & việc còn lại

- **Alignment**: pipeline N0 dùng **MFA thật** (6.989/6.989 TextGrid). Với dữ liệu mới, nên chạy MFA/aligner; nếu chưa có, code dùng chia theo trọng số (placeholder), chất lượng thấp hơn.
- **Vocoder**: bản tham chiếu (GAN nhẹ MPD-lite) + **bản nâng cấp MPD đầy đủ 2/3/5/7/11 + MRD + MR-STFT**
  (`discriminator: mpd_mrd`, chạy khối MPS) — xem `docs/archive/plans/REVISION_PLAN_V2.md` §10; GTA fine-tune sẽ làm sau.
- **ONNX**: đã export N0 FP32 (acoustic + Vocos) và runtime CPU; demo dùng ONNX. Chưa gộp vocoder vào một graph duy nhất/INT8 calibration đầy đủ.
- **OOV**: từ ngoài tiếng Việt đọc bằng fallback — muốn kiểm soát thì bật `resolve_oov=True`, dùng `--overrides file.json` hoặc thêm override.
- **Một checkpoint = một giọng, một phương ngữ** (đúng thiết kế; không có `speaker_id`/`dialect_id`
  nên không đổi giọng lúc chạy). Bộ mã hoá 5 ô dùng chung cho mọi vùng, nên **có 15–20 h dữ liệu
  sạch của một giọng/vùng là train được checkpoint riêng** mà không sửa kiến trúc
  (xem `docs/TRAINING_N0.md`, `docs/SYLLABLE_GUIDE.md`). Muốn **một model phục vụ nhiều vùng**
  thì phải thêm conditioning vùng/người nói — chưa làm.

Roadmap chi tiết có đánh dấu ✅/⬜: `docs/handoff/TRANG_THAI.md`.

## 10. Tài liệu — nên đọc gì trước?

Mục lục đầy đủ + phân loại **hiện hành / tham chiếu / lịch sử**: **`docs/README.md`**.

| Nhóm | Tài liệu | Nội dung |
| --- | --- | --- |
| **Bắt đầu ở đây** | `docs/README.md` | Bản đồ toàn bộ tài liệu, trạng thái từng nhóm |
| **Rust port** | `docs/RUST_PORT.md` · `desktop/README.md` · `mobile/android/README.md` | Port inference Rust, app desktop egui, APK local-first |
| | `docs/handoff/TRANG_THAI.md` | Trạng thái tổng, quyết định hiện hành, việc còn lại |
| | `docs/MODEL_FLOW.md` | Luồng model chi tiết: data → train → inference → export |
| | `docs/SYLLABLE_GUIDE.md` | Hướng dẫn tách âm tiết cho người không chuyên |
| | `docs/GLOSSARY.md` | Thuật ngữ (âm đầu/đệm/chính/cuối, toàn ánh/song ánh...) |
| **Frontend** | `docs/FRONTEND.md` | Parser, profile/lexicon, segments, G2P, OOV, Q |
| | `docs/NORMALIZER.md` | Số/ngày/giờ theo vùng miền, dấu thanh, i/y |
| | `docs/STEM_NORMALIZER.md` | Toán/LaTeX, hoá học, đơn vị vật lý |
| | `docs/G2P_VIETNAMESE.md` | Khảo sát sea-g2p, viG2P... và bảng IPA nội bộ |
| **Model & dữ liệu** | `docs/ARCHITECTURE.md` | Sơ đồ as-built, quyết định thiết kế |
| | `docs/ACOUSTIC_V2.md` | Thiết kế + nhật ký đo acoustic v2 (§0–§51) |
| | `docs/EVAL_TOOLS.md` | Danh mục thước đo, lệnh chạy, mốc so |
| | `docs/DATA_PIPELINE.md` | Pipeline chuẩn bị dữ liệu |
| | `docs/YOUTUBE_DATASET.md` | Lấy dataset sạch từ kênh YouTube của bạn |
| | `docs/TRAINING.md` | Hướng dẫn train + cảnh báo alignment |
| | `docs/TRAINING_N0.md` | **Run N0 Ngọc Huyền**: pipeline, thời gian, chọn dữ liệu |
| | `docs/NGOC_HUYEN.md` | Model card model mẫu, license, quickstart |
| | `docs/Q_ONSET.md` | Quyết định Q + fine-tune candidate |
| | `docs/handoff/N0_DEPLOY.md` | ONNX + service `vifasttts.hoctuthien.com` |
| | `docs/HUGGINGFACE.md` | Hugging Face model + Space static demo |
| | `docs/TRAINING_ESTIMATES.md` | Ước lượng dữ liệu/tham số/thời gian/máy/chi phí |
| | `docs/APPLE_SILICON.md` | Mac/M-series: MPS, MLX, ANE, provider ONNX |
| | `docs/DEPLOYMENT.md` | ONNX Runtime, quantize, nền tảng |
| **Nghiên cứu** | `docs/SYLLABLE_SYSTEMS_RESEARCH.md` | So sánh mô hình tách/gộp âm tiết + audit biên |
| | `docs/TTS_ARCHITECTURE_RESEARCH.md` | Khảo sát họ kiến trúc TTS + đề xuất tương lai |
| | `docs/VI_TTS_DATA_REFERENCE.md` | Model/dataset TTS tiếng Việt công khai |
| **Lịch sử** | `docs/archive/README.md` | Thiết kế gốc, kế hoạch/review cũ, báo cáo V08–V18.52 |
| **Khác** | `docs/LICENSES.md` | Giấy phép các thành phần tham chiếu |

## 11. Giấy phép

**Code repo: MIT.** Dữ liệu giọng nói, lexicon, checkpoint và model mẫu có giấy phép riêng;
các công cụ tham chiếu (sea-g2p, MFA, vPhon...) giữ giấy phép gốc — xem `docs/LICENSES.md`.

**Model Ngọc Huyền:** dataset `pnnbao-ump/ngochuyen_voice` là **CC BY-NC 4.0**; checkpoint/
ONNX/weights chỉ dùng **nghiên cứu, phi thương mại**, không dùng giả giọng hoặc production
thương mại. Dataset lấy từ kênh YouTube của bạn mặc định ghi **CC BY 4.0** (ghi nguồn kênh),
đổi bằng `--license`, ví dụ `--license "CC0 1.0"`.
