# Hugging Face — đã upload

- Repo: **https://huggingface.co/dvchd/vifasttts-ngochuyen-small**
- Commit: `6cfd13e16be700aaec68175086ee44be929bc01b`
- License metadata: `cc-by-nc-4.0`; model chỉ dùng research/non-commercial.
- Đã có: checkpoint, config, mel/f0 stats, Vocos, ONNX FP32, 10 demo, model card, license.
- Đã kiểm tra `model_info` + tải thử `onnx/acoustic.onnx` (HTTP 200, 31.626.168 byte).

## Gợi ý repo (đã dùng)

- `dvchd/vifasttts-ngochuyen-small` (model)
- License metadata: `cc-by-nc-4.0`
- Tags: `text-to-speech`, `vietnamese`, `onnx`, `vifasttts`, `research`

## File nên đưa

| File | Ghi chú |
|---|---|
| `README.md` | model card + license + cách dùng |
| `best.pt` | acoustic small 60k |
| `config.yaml` | `configs/small_ngochuyen.yaml` |
| `mel_stats.json`, `f0_stats_v2.json` | để load/verify |
| `acoustic.onnx`, `vocoder.onnx` | runtime CPU không torch |
| `LICENSE.md` | CC-BY-NC + attribution dataset |
| `sample.wav` (tuỳ chọn) | 1–3 câu demo, ghi rõ research |

Không đưa audio/transcript gốc của dataset.

## Cách upload lại khi cần cập nhật

```bash
export HF_TOKEN=...                 # đặt trong shell, không commit token
python - <<'PY'
from huggingface_hub import HfApi
api = HfApi()
api.create_repo("dvchd/vifasttts-ngochuyen-small", repo_type="model", private=False, exist_ok=True)
api.upload_folder(
    repo_id="dvchd/vifasttts-ngochuyen-small",
    repo_type="model",
    folder_path="release_hf_ngochuyen",
    commit_message="N0 ngochuyen small research release",
)
PY
```

`release_hf_ngochuyen/` cần có `README.md` (model card), checkpoint, config, stats, ONNX,
license. Không đưa `.venv`, `runs/`, `cache/`, audio gốc.

## Model card tối thiểu

```yaml
---
license: cc-by-nc-4.0
language: [vi]
tags: [text-to-speech, vietnamese, onnx, vifasttts]
library_name: vifasttts
---
```

Nội dung nên có: nguồn dataset + revision, kiến trúc, metrics holdout, cách chạy ONNX,
mặc định alpha/pause, giới hạn, cảnh báo **không production/không giả giọng**, attribution.

## Khi nào upload?

Cần một trong hai:
1. `HF_TOKEN` (write) + username; hoặc
2. bạn tạo repo rỗng và cấp quyền, mình chỉ upload file.

Sau khi upload phải kiểm tra bằng `HfApi.model_info(...)` + tải thử một file, giống quy trình
release GitHub.
