---
license: cc-by-nc-4.0
language:
  - vi
tags:
  - text-to-speech
  - vietnamese
  - onnx
  - vifasttts
  - research
pipeline_tag: text-to-speech
library_name: vifasttts
---

<p align="center">
  <img src="https://huggingface.co/dvchd/vifasttts-ngochuyen-small/resolve/main/assets/vifasttts-lockup-cream.png" alt="ViFastTts · Giọng đọc tiếng Việt" width="620">
</p>

# ViFastTts N0 — Ngọc Huyền (research, non-commercial)

> **Model nghiên cứu, KHÔNG production thương mại.**
> Dataset `pnnbao-ump/ngochuyen_voice` là **CC BY-NC 4.0**. Không dùng để giả giọng,
> lừa đảo, bán lại hoặc triển khai thương mại khi chưa có quyền riêng.
> Code ViFastTts là MIT hoặc Apache-2.0; quyền dataset/giọng vẫn giữ nguyên.

Model TTS tiếng Việt **một giọng nữ**, acoustic **small 6,1M tham số**, 24 kHz.
Repo này chứa checkpoint, config, stats, ONNX FP32, bundle `.vfa/.vfts` và 10 câu demo.

## Bundle `.vfa` / `.vfts`

- `bundles/n0-ngochuyen.vfa` — acoustic-only, dùng `onnx/vocoder.onnx`.
- `bundles/n0-ngochuyen.vfts` — full bundle, tự chứa vocoder + frontend.
- Base 60k **sau Q** nằm ở repo riêng:
  https://huggingface.co/dvchd/vifasttts-ngochuyen-base

## Vocab Q (27/10/2026)

ONNX trong repo này đã có onset **Q** (`vocab_version` + `vocab_hash`) cho chữ `qu`; Q ở cuối vocab,
khởi tạo bằng K cho N0 Bắc. Checkpoint/ONNX cũ không có hash bị từ chối; không có
adapter Q→K. Checkpoint `.pt` cũ vẫn là model K (dùng `--init-from` nếu fine-tune Q).

## Hai luồng sử dụng

### A. Chỉ dùng model để tạo âm thanh

Không cần train, không cần torch nếu dùng ONNX.

```bash
git clone https://github.com/vifast-oss/ViFastTts.git
cd ViFastTts
./scripts/run_ngochuyen_demo.sh       # macOS / Linux
# Windows PowerShell:
# powershell -ExecutionPolicy Bypass -File .\scripts\run_ngochuyen_demo.ps1
```

Hoặc tải ONNX trong repo này:

```python
from huggingface_hub import hf_hub_download
acoustic = hf_hub_download("dvchd/vifasttts-ngochuyen-small", "onnx/acoustic.onnx")
vocoder = hf_hub_download("dvchd/vifasttts-ngochuyen-small", "onnx/vocoder.onnx")
```

Sau đó dùng `vifasttts.runtime.onnx_engine` hoặc service demo:
https://tts.vifast.org/

Mặc định: `sharpen_alpha=1.5`, Vocos pretrained, **model tự ngắt nghỉ**.
Nghỉ cố định là opt-in (`--fixed-pauses` / `pause_mode="fixed"`), mặc định tắt.

### B. Tự train một giọng mới

Cần Python 3.11+, torch, MFA/aligner, audio + transcript.

```bash
git clone https://github.com/vifast-oss/ViFastTts.git
cd ViFastTts
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\Activate.ps1
pip install -e ".[dev,audio,train,onnx]"
```

Quy trình và số đo đầy đủ:
- `docs/TRAINING_N0.md`: pipeline N0, thời gian, chọn dữ liệu small/base.
- `docs/TRAINING.md`: hướng dẫn train tổng quát.
- `docs/DATA_PIPELINE.md`: chuẩn bị dữ liệu và alignment.

## Kết quả tham chiếu

| Chỉ số | Giá trị |
|---|---|
| Dữ liệu | 21,57 h raw → 19,89 h sạch; train 17,9 h |
| Huấn luyện | 60.000 bước, batch 8, khoảng 5 h 46 trên Mac mini M6 |
| Holdout mel L1 | **4,0 dB** (z 0,298) |
| Free-run 80 câu | **16,57 dB**, length 0,999, pause F1 0,825 |
| Thanh điệu | thật 0,9835 · copy 0,9784 · free 0,9743 |
| A/B tai người | 24/24 chọn model mới so P2 zero-shot |
| RTF thực tế | 0,045 end-to-end trên VPS CPU (5 câu, 22,44 s audio / 1,01 s xử lý) |

## File

```text
best.pt                         # acoustic small Q-init 60k
config.yaml                     # configs/small_ngochuyen.yaml
resolved_config.json
data/ngochuyen/mel_stats.json
data/ngochuyen/f0_stats_v2.json
onnx/acoustic.onnx
onnx/vocoder.onnx
bundles/n0-ngochuyen.vfa
bundles/n0-ngochuyen.vfts
bundles/README.md
models.json                     # catalog tham khảo
demo/                           # 10 câu mới + texts.json
assets/
```

## Giấy phép và attribution

- Dataset: `pnnbao-ump/ngochuyen_voice`, revision `1ebbfbd1fb828dfd41bff8b1645ad9e56cfc614a`,
  **CC BY-NC 4.0**.
- Vocos: `charactr/vocos-mel-24khz`, MIT.
- Model weights: chỉ dùng research/non-commercial; xem `LICENSE.md`.

## Download stats

HuggingFace chỉ tính download cho các **query file** (`config.json`, `config.yaml`,
`hyperparams.yaml`, `params.json`, `meta.yaml`), không tính trực tiếp file
`.vfa`/`.vfts`. Vì vậy tải bundle trực tiếp từ app có thể không hiện trong
`downloads` của repo. Đây là giới hạn của HF, không phải lỗi catalog; không tạo
request giả để tăng số.

## Liên kết

- Code: https://github.com/vifast-oss/ViFastTts
- Demo: https://tts.vifast.org/
- Hugging Face: https://huggingface.co/dvchd/vifasttts-ngochuyen-small
- Space demo: https://huggingface.co/spaces/dvchd/vifasttts-ngochuyen-demo
- Model bundles: https://huggingface.co/dvchd/vifasttts-ngochuyen-small/tree/main/bundles
- Base 60k sau Q: https://huggingface.co/dvchd/vifasttts-ngochuyen-base
- ONNX: `onnx/acoustic.onnx`, `onnx/vocoder.onnx`

## Giới hạn

- Single-speaker; không speaker ID, không zero-shot giọng khác.
- Từ “ấm” trong câu demo `fresh04` có thể hơi rè cục bộ.
- Không có safety filter; không dùng cho impersonation.
