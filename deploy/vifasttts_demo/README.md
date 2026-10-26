# ViFastTts demo service

ONNX-only demo (không cần torch):
- `app.py` — FastAPI, ONNX acoustic + Vocos, alpha 1.5, model tự nghỉ mặc định.
- `static/index.html` — trang nhập câu, play/tải WAV.
- `Dockerfile` / `requirements.txt` / `docker-compose.yml`.

Build context phải có `src/`, `models/{acoustic,vocoder}.onnx`, `app.py`, `static/`.
Chạy local:

```bash
docker build -t vifasttts-demo .
docker run --rm -p 8090:8000 vifasttts-demo
```

Trên VPS dùng `docker compose up -d --build`; container join network `coolify`, Traefik
file provider route `vifasttts.hoctuthien.com` → `http://vifasttts:8000`.
