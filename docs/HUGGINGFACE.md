# Hugging Face — đã upload

- Repo: **https://huggingface.co/dvchd/vifasttts-ngochuyen-small**
- Commit ONNX Q: `8148ae3c2108df87184015f7579675dfd088cb24` (acoustic Q, `vocab_version`
  + `vocab_hash`; file `onnx/acoustic.onnx` sha256 `df61599a…`).
- Commit model card/logo: `460afac94b40fe6ff1504a28e748f0aeb8233cba`
  (asset logo ở các commit trước đó).
- License metadata: `cc-by-nc-4.0`; model chỉ dùng research/non-commercial.
- Đã có (layout chuẩn, 29/10/2026): `best.pt`, `config.yaml`, `resolved_config.json`,
  `data/ngochuyen/*`, ONNX FP32, `bundles/*.vfa|.vfts`, 10 demo, model card, license.
- Không còn `resources/` (bản sao bundle), `configs/` (bản sao config), `artifacts/`,
  `runs/` hay `bundles/models.json`/`bundles/SHA256SUMS` trùng lặp.
- Repo base 60k sau Q: `dvchd/vifasttts-ngochuyen-base`.
- Đã kiểm tra `model_info` + tải thử ONNX/bundle (sha256 khớp).

## Download stats — HF đếm theo query file

HF chỉ đếm lượt tải qua **query file** mặc định (`config.json`, `config.yaml`,
`hyperparams.yaml`, `params.json`, `meta.yaml`) hoặc filter của library. Vì vậy:

- `config.yaml` **ở root** đã có để model browser/HF UI tải config được tính.
- Tải thẳng `.vfa`/`.vfts`/`onnx/acoustic.onnx` **không** được tính nếu chưa đăng ký
  `countDownloads` cho library `vifasttts` trong `huggingface.js`; app tải bundle trực tiếp
  nên `downloads` của repo sẽ thấp hơn lượt dùng thật.
- `downloads` trên API là số tổng hợp, có thể cập nhật chậm; không dùng nó để kết luận
  ngay sau một lần tải thử.
- Đã gửi PR [`huggingface.js#2747`](https://github.com/huggingface/huggingface.js/pull/2747)
  thêm `countDownloads` cho `vifasttts` với `.vfa`, `.vfts`, `.onnx`; sau khi merge,
  các file này mới được HF tính vào download.
- Muốn số chính xác theo người dùng/file: dùng **Publisher Analytics** (log request-level,
  unique downloaders) hoặc thêm analytics phía server/app. Không tạo request giả để tăng số.

Kiểm tra hiện tại (29/10/2026): small `downloads=3`, base `downloads=0`; đây là số
tổng hợp của HF, không phải số bundle app đã tải.

## Gợi ý repo (đã dùng)

- `dvchd/vifasttts-ngochuyen-small` (model)
- License metadata: `cc-by-nc-4.0`
- Tags: `text-to-speech`, `vietnamese`, `onnx`, `vifasttts`, `research`

## File nên đưa

| File | Ghi chú |
|---|---|
| `README.md` | model card + license + cách dùng |
| `best.pt` | acoustic small Q-init 60k |
| `config.yaml` | `configs/small_ngochuyen.yaml` |
| `resolved_config.json` | config lúc train |
| `data/ngochuyen/mel_stats.json`, `data/ngochuyen/f0_stats_v2.json` | để load/verify |
| `onnx/acoustic.onnx`, `onnx/vocoder.onnx` | runtime CPU không torch; acoustic Q có `vocab_hash` |
| `bundles/*.vfa`, `bundles/*.vfts` | bundle phân phối cho app |
| `LICENSE.md` | CC-BY-NC + attribution dataset |
| `assets/vifasttts-lockup-cream.png` | logo model card (nguồn `resources/brand/`) |
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

`release_hf_ngochuyen/` cần có `README.md` (model card), `best.pt`, config/stats, ONNX,
`bundles/`, license. Không đưa `.venv`, `runs/`, `cache/`, `artifacts/`, audio gốc.

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


## Logo trên model card

- Nguồn: `resources/brand/`; bản dùng cho model card là `vifasttts-lockup-cream.png`
  (nền kem, đọc được ở dark mode).
- Asset trên HF: `assets/vifasttts-lockup-cream.png`; README model dùng URL
  `https://huggingface.co/dvchd/vifasttts-ngochuyen-small/resolve/main/assets/vifasttts-lockup-cream.png`.

## Space demo

- Static Space miễn phí: https://huggingface.co/spaces/dvchd/vifasttts-ngochuyen-demo
- App trực tiếp: https://dvchd-vifasttts-ngochuyen-demo.static.hf.space/
- Space static có 3 mẫu audio, gọi VPS API cho câu mới (CORS) và gửi góp ý/báo lỗi qua
  `POST /api/feedback` (CORS).
- Gradio/Docker Space CPU free hiện trả **402 Payment Required** trên account này; cần PRO.
  Vì vậy bản free dùng static Space, không chạy backend trong Space.
