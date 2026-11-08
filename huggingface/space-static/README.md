---
title: ViFastTts Ngọc Huyền small demo
emoji: 🎙️
colorFrom: red
colorTo: yellow
sdk: static
app_file: index.html
pinned: false
license: cc-by-nc-4.0
---

![ViFastTts](https://huggingface.co/dvchd/vifasttts-ngochuyen-small/resolve/main/assets/vifasttts-lockup-cream.png)

# ViFastTts · Ngọc Huyền small

Static demo miễn phí cho model TTS tiếng Việt small 6,1M, 24 kHz, ONNX CPU.

- `index.html` — landing page: giới thiệu, nghe thử nhanh, mục **Sản phẩm**, tải xuống,
  hướng dẫn cài và form **Góp ý**.
- `demo.html` — demo đầy đủ (tuỳ chọn nâng cao, lịch sử); API gọi VPS.
- Nghe 3 mẫu có sẵn trực tiếp trong trang; custom reading + góp ý gọi VPS.
- ONNX đang dùng là **N0 Q-init** (`vocab_version` + `vocab_hash`).
- Tạo câu mới gọi VPS demo (CORS), vì Gradio/Docker Space CPU free cần PRO.
- Góp ý / báo lỗi gửi qua VPS; admin xem tại `/admin` khi đã đặt `ADMIN_PASSWORD`.
- Research/non-commercial; dataset CC BY-NC 4.0; không dùng giả giọng/lừa đảo.
- Hai file HTML được sinh từ `deploy/vifasttts_web/static/` bằng
  `tools/sync_space_static.py`; không sửa trực tiếp bản Space.

Code: https://github.com/dvchd/ViFastTts
Model: https://huggingface.co/dvchd/vifasttts-ngochuyen-small
VPS demo: https://vifasttts.hoctuthien.com/
