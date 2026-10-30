# ViFastTts demo service

ONNX-only demo (không cần torch):
- `app.py` — FastAPI, ONNX acoustic + Vocos, alpha 1.5, model tự nghỉ mặc định;
  giới hạn mặc định 3000 ký tự (`MAX_CHARS`), chunk nội bộ 300 ký tự.
  Full và stream dùng chung `vifasttts.runtime.tts_engine.OnnxTtsEngine`.
- `GET /api/config` trả defaults/capabilities/endpoints; `POST /api/tts/stream`
  trả NDJSON PCM16 (UI checkbox **Stream** phát bằng WebAudio).
- `GET /api/stats` trả số liệu tổng hợp công khai; `POST /api/download` ghi lượt bấm
  nút tải theo nền tảng (không lưu IP/file, không xác nhận tải xong).
- `static/index.html` — landing page: giới thiệu, nghe thử nhanh, mục **Sản phẩm**,
  tải xuống + hướng dẫn cài chi tiết từng nền tảng, form **Góp ý**, mục **Thống kê**.
- `static/demo.html` — demo đầy đủ tại `/demo` (`/demo.html` chuyển hướng): tuỳ chọn
  nâng cao, stream, lịch sử; góp ý chuyển về landing.
- `/brand/*` mount cùng nội dung `static/brand/` để landing dùng đường dẫn tương đối;
  nhờ vậy cùng một HTML chạy được trên VPS và HF Space tĩnh.
- `static/samples/` — 3 WAV mẫu (không commit; tải bằng `scripts/fetch_demo_samples.sh`).
- `static/brand/` — icon, lockup, favicon, OG image, manifest (nguồn: `resources/brand/`).
- `Dockerfile` / `requirements.txt` / `docker-compose.yml`.

Build context phải có `src/`, `models/{acoustic,vocoder}.onnx`, `app.py`, `static/`
(kèm `static/brand/`).
Trên VPS, staging ở `/opt/vifasttts` dùng `docker compose up -d --build`; container join
network `coolify`, Traefik label route `vifasttts.hoctuthien.com` → `http://vifasttts:8000`.

## Docker cục bộ

Dockerfile cần context phẳng; tạo staging rồi build:

```bash
./scripts/fetch_ngochuyen_models.sh
TMP=$(mktemp -d)
cp -R src app.py static Dockerfile requirements.txt "$TMP/"
mkdir -p "$TMP/models"
cp artifacts/onnx/n0_q/*.onnx "$TMP/models/"
docker build -t vifasttts-demo "$TMP"
docker run --rm -p 8090:8000 vifasttts-demo
# http://127.0.0.1:8090
```

Cách nhanh nhất vẫn là `./scripts/run_ngochuyen_demo.sh` (không cần Docker).

## Đồng bộ HF Space

Landing/demo dùng chung HTML với Space tĩnh (`brand/...` tương đối, JS tự chọn API
base theo host). Sau khi sửa `static/index.html` hoặc `static/demo.html`:

```bash
.venv/bin/python tools/sync_space_static.py --check  # CI: phải khớp
.venv/bin/python tools/sync_space_static.py          # chép sang huggingface/space-static
```


## Thống kê

- `/admin` và `/admin.json`.
- Mặc định mở công khai nếu `ADMIN_PASSWORD` chưa đặt.
- Đặt `ADMIN_PASSWORD` trong compose để bật Basic Auth.
- DB `data/stats.sqlite3`; compose bind mount `./data:/app/data`.
- Web/Space dùng `visitor_id` localStorage; API thuần có thể gửi `visitor_id`; fallback IP.
- Có tách lượt tạo theo `source = web | space | api`.
- Chỉ lưu hash visitor, số ký tự, thời lượng audio, thời gian xử lý; không lưu IP/text.
- API mẫu: `{"text":"...", "source":"api", "visitor_id":"client-1234"}`.
- `GET /api/config` trả max_chars/rate_limit; response `/api/tts` có header
  `X-Processing-Seconds`, `X-Audio-Seconds`, `X-RTF` để UI hiển thị thời gian/RTF.
- Cách đọc custom: localStorage + `overrides` trong request; xem `GET /api/overrides`;
  tối đa 50 quy tắc, không hỗ trợ regex/script; key có thể là cụm/domain
  (`khongdich.com = không dịch chấm com`, `H2 + O2 -> H2O = hát hai cộng ô hai tạo ra nước`). Gửi để duyệt mặc định bật; quy tắc được gửi khi
  tạo âm thanh; server chỉ lưu suggestion pending, admin duyệt khi có
  `ADMIN_PASSWORD`; chưa đặt thì nút duyệt bị khoá nhưng đề xuất vẫn vào hàng chờ.
- Góp ý / báo lỗi: `POST /api/feedback`; lưu SQLite bảng `feedback`; nội dung chỉ admin xem
  khi đã đặt `ADMIN_PASSWORD`; xuất CSV `/admin/feedback.csv`. Có rate limit + honeypot.
