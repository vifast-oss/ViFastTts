# ViFastTts demo service

ONNX-only demo (không cần torch):
- `app.py` — FastAPI, ONNX acoustic + Vocos, alpha 1.5, model tự nghỉ mặc định.
- `static/index.html` — trang nhập câu, play/tải WAV.
- `Dockerfile` / `requirements.txt` / `docker-compose.yml`.

Build context phải có `src/`, `models/{acoustic,vocoder}.onnx`, `app.py`, `static/`.
Trên VPS, staging ở `/opt/vifasttts` dùng `docker compose up -d --build`; container join
network `coolify`, Traefik label route `vifasttts.hoctuthien.com` → `http://vifasttts:8000`.

## Docker cục bộ

Dockerfile cần context phẳng; tạo staging rồi build:

```bash
./scripts/fetch_ngochuyen_models.sh
TMP=$(mktemp -d)
cp -R src app.py static Dockerfile requirements.txt "$TMP/"
mkdir -p "$TMP/models"
cp artifacts/onnx/n0/*.onnx "$TMP/models/"
docker build -t vifasttts-demo "$TMP"
docker run --rm -p 8090:8000 vifasttts-demo
# http://127.0.0.1:8090
```

Cách nhanh nhất vẫn là `./scripts/run_ngochuyen_demo.sh` (không cần Docker).


## Thống kê

- `/admin` và `/admin.json`.
- Mặc định mở công khai nếu `ADMIN_PASSWORD` chưa đặt.
- Đặt `ADMIN_PASSWORD` trong compose để bật Basic Auth.
- DB `data/stats.sqlite3`; compose bind mount `./data:/app/data`.
- Web/Space dùng `visitor_id` localStorage; API thuần có thể gửi `visitor_id`; fallback IP.
- Có tách lượt tạo theo `source = web | space | api`.
- Chỉ lưu hash visitor, số ký tự, thời lượng audio, thời gian xử lý; không lưu IP/text.
- API mẫu: `{"text":"...", "source":"api", "visitor_id":"client-1234"}`.
