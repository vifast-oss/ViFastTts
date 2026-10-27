# N0 — ONNX + demo service `vifasttts.hoctuthien.com`

> **Demo nghiên cứu / phi thương mại** — dataset CC-BY-NC-4.0. Không dùng làm production
> thương mại, không dùng giả giọng/lừa đảo.

## 1. ONNX

Đã xuất (FP32, opset 18):

| File | Kích thước | Nguồn / trạng thái |
|---|---:|---|
| `artifacts/onnx/n0_q/acoustic.onnx` | 31.626.449 B | `runs/acoustic_ngochuyen_q/init_q.pt` — **đang live**; sha256 `16e66b70…` |
| `artifacts/onnx/n0_q/vocoder.onnx` | 54.158.691 B | Vocos pretrained; sha256 `b3eb09cf…` |
| `artifacts/onnx/n0_q_ft/acoustic.onnx` | — | fine-tune 3k; sha256 `394fa657…` — **chưa live** |
| `artifacts/onnx/n0/acoustic.onnx` | 31.626.449 B* | N0 cũ chưa có Q; sha256 `6c8bde3d…` — **bị từ chối** |

\* ONNX N0 cũ vẫn giữ để đối chiếu, nhưng runtime mới từ chối vì thiếu `onset_has_q=true`.

Lệnh export bản Q-init (đang live):

```bash
vifasttts export-onnx --config configs/small_ngochuyen_q.yaml \
  --checkpoint runs/acoustic_ngochuyen_q/init_q.pt \
  --output artifacts/onnx/n0_q/acoustic.onnx --opset 18
vifasttts export-vocoder-onnx --config configs/small_ngochuyen.yaml \
  --checkpoint artifacts/pretrained/vocos-mel-24khz/pytorch_model.bin \
  --output artifacts/onnx/n0_q/vocoder.onnx --opset 18
```

Đã smoke-test `synthesize-onnx` CPU. Service dùng ONNX Runtime, **không cần torch**.

## 2. Service

- URL: **https://vifasttts.hoctuthien.com/**
- Health: `https://vifasttts.hoctuthien.com/healthz`
- Host: VPS `jp` (Tailscale `100.104.111.17`), LXD container `hoctuthien-vps` (web host
  của `hoctuthien.com`), Docker path `/opt/vifasttts`.
- Image: `vifasttts-vifasttts:latest`; container `vifasttts`, restart `unless-stopped`.
- Routing: Traefik trong LXD (Coolify proxy) dùng Docker labels; DNS
  `vifasttts.hoctuthien.com` đã trỏ VPS, wildcard `*.hoctuthien.com` đi qua LXD.
- TLS: Let's Encrypt (TLS-ALPN) tại Traefik LXD; cert hợp lệ.
- Trang: nhập text 300 ký tự, play/tải WAV; mặc định **model tự nghỉ**, alpha **1.5**,
  Vocos pretrained. Fixed pause là checkbox, mặc định tắt.
- **Q (27/10/2026, đang live):** onset Q (ID cuối) cho `qu`; ONNX đang phục vụ là
  `n0_q/acoustic.onnx` (Q-init, `Q = K`, bit-exact với N0 Bắc cũ) và mang metadata
  `onset_has_q=true`. Model/ONNX cũ thiếu cờ này bị từ chối, không có adapter Q→K.
  Fine-tune 3k (`n0_q_ft`) **chưa deploy**. D/GI/R/V vẫn 4 token (Bắc Trung Bộ có thổ ngữ
  phân biệt; Trung bộ chính/Nam gộp D/GI — không ghi “Nam phân biệt D/GI”).
- **Nhận diện:** nguồn logo ở `resources/brand/` (`vifasttts-icon.svg`,
  `vifasttts-lockup.svg`, favicon, `og-image.png`, manifest). Web phục vụ
  `/static/brand/`; `app.py` mount `StaticFiles` và có route `/favicon.ico`.
- Chống lạm dụng: 6 request/phút/IP (X-Forwarded-For), 1 request đồng thời, text 300 ký tự,
  không lưu text/audio.
- **Thống kê:** `/admin` (HTML) và `/admin.json`; tổng người dùng, tổng lượt tạo, lượt xem trang,
  **lượt tạo web / Space / API riêng**, audio đã tạo, 20 lượt gần nhất.
  Không lưu IP/text; visitor lưu dạng hash. `/admin` hiển thị cả hàng chờ đề xuất cách đọc.
  Nếu `ADMIN_PASSWORD` rỗng hoặc chưa đặt, `/admin` mở công khai nhưng **nút duyệt bị khoá**;
  đặt env này để bật Basic Auth và mở duyệt.
  DB: `/app/data/stats.sqlite3`, bind mount `./data:/app/data` nên giữ qua restart.
- **Vì sao trước đây chỉ thấy 1 người:** outer Traefik dùng TLS passthrough cho `*.hoctuthien.com`,
  nên Traefik trong LXD thấy mọi request đến từ cùng IP upstream. Web và static Space giờ tạo
  `visitor_id` trong localStorage và gửi `/api/visit` + `/api/tts`; API thuần có thể gửi
  `visitor_id` trong JSON, nếu không sẽ fallback hash IP (có thể gộp sau proxy).
- API payload mẫu:
  `{"text":"...", "source":"api", "visitor_id":"my-client-1234"}`.
  `source` mặc định `api`; web/Space gửi `web`/`space`.
- **Cách đọc custom:** web có mục “Tùy chọn nâng cao”; lưu tối đa 50 quy tắc trong
  `localStorage`, gửi qua `overrides` của `/api/tts`. API cũng nhận trực tiếp:
  `{"text":"AI", "overrides":{"AI":"ây ai"}}`.
  Key cụm/domain (`khongdich.com = không dịch chấm com`) được áp trước token hoá;
  đây là literal match, không phải regex.
  Gửi đề xuất: `POST /api/overrides/suggest` với `{"rules":{"AI":"ây ai"}}`.
  Mặc định mọi quy tắc chỉ ở local; nếu tích “gửi để duyệt”, server lưu cặp từ/cách đọc
  vào hàng chờ (`/api/overrides/suggest`), không lưu câu/IP. Checkbox gửi **mặc định bật**,
  bỏ tích để chỉ lưu local; quy tắc gửi khi **tạo âm thanh** hoặc bấm **Lưu quy tắc**;
  trạng thái checkbox được nhớ trong localStorage. Admin chỉ duyệt
  được khi có `ADMIN_PASSWORD`; nếu chưa đặt, nút duyệt bị khoá. Bảng có sẵn 570 quy tắc qua
  `GET /api/overrides`; không hỗ trợ regex/script.
- **Validator từ vay:** `resources/loanword_labial_w.txt` (buýt, voan, boa);
  `tools/validate_syllables.py` chỉ cảnh báo, không chặn. Reparse manifest trước khi train;
  feature cache không chứa token nên không cần rebuild.
- **Góp ý / báo lỗi:** form trên web và static Space gửi `POST /api/feedback` với
  `category = gop_y | cai_tien | bao_loi`, `message` 5–1000 ký tự, `contact` không bắt buộc,
  `visitor_id` và `source`. Server lưu bảng SQLite `feedback`, chỉ hash visitor, không lưu IP;
  có honeypot + giới hạn 6 lần/phút. `/admin` tổng hợp số lượng theo loại/trạng thái và hiển thị
  nội dung **chỉ khi có `ADMIN_PASSWORD`**; chưa đặt thì nội dung bị khoá, CSV cũng bị khoá.
  Admin đánh dấu `Đã đọc` / `Đã xử lý`; tải CSV tại `/admin/feedback.csv`.
- **RTF thực tế:** 5 câu, tổng audio **22,44 s**, tổng xử lý **1,01 s** trên VPS CPU
  (HTTP loopback trong container), **RTF 0,045**, khoảng 22 lần nhanh hơn thời gian thực.
  Chưa tính độ trễ mạng từ trình duyệt.

## 3. Deploy / cập nhật

Từ Mac (repo root), tạo staging có `src`, `models`, `app.py`, `static`, `Dockerfile`,
`requirements.txt`, `docker-compose.yml`; đóng gói rồi:

```bash
scp vifasttts_deploy.tgz root@100.104.111.17:/tmp/
ssh root@100.104.111.17 'lxc file push /tmp/vifasttts_deploy.tgz hoctuthien-vps/tmp/'
ssh root@100.104.111.17 'lxc exec hoctuthien-vps -- bash -lc \
  "mkdir -p /opt/vifasttts && tar -xzf /tmp/vifasttts_deploy.tgz -C /opt/vifasttts && \
   cd /opt/vifasttts && docker compose up -d --build"'
```

Kiểm tra:

```bash
curl -sS https://vifasttts.hoctuthien.com/healthz
curl -sS -X POST https://vifasttts.hoctuthien.com/api/tts \
  -H 'Content-Type: application/json' \
  -d '{"text":"Xin chào, đây là demo.","speed":1.0,"fixed_pauses":false}' -o demo.wav
```

## 3.1 Hugging Face

- Model: **https://huggingface.co/dvchd/vifasttts-ngochuyen-small**
- License metadata `cc-by-nc-4.0`; có checkpoint, config/stats, Vocos, ONNX, demo, model card.
- Commit upload checkpoint/model card gốc: `6cfd13e16be700aaec68175086ee44be929bc01b`;
  commit ONNX Q: `0b08245ee96710a738d7b1e543151e026b4f6cde`.

## 4. ONNX trong release

- `n0_onnx_fp32_q.zip` — **Q, đang live**: 79.437.883 B, sha256 `ef35567c4433cf…`;
  bên trong có `n0_onnx_fp32/acoustic.onnx` (`16e66b70…`) + vocoder (`b3eb09cf…`) + SHA256SUMS.
- `n0_onnx_fp32.zip` — N0 cũ chưa có Q, giữ lịch sử; runtime mới **từ chối**.
- Package chính vẫn chứa checkpoint + config + stats + Vocos pretrained.
- Release `q-preview-2026-10-27` chỉ có 2 WAV nghe thử (`init.wav`, `finetune.wav`), không phải
  asset triển khai; xoá sau khi chọn model.

## 5. Giới hạn

- Public demo, không auth; rate limit đơn giản, không chống DDoS.
- Không lưu dữ liệu nhưng VPS/provider vẫn có access log hạ tầng.
- File `fresh04` “ấm” có thể hơi rè cục bộ; không phải lỗi service.
- Dataset CC-BY-NC-4.0; không dùng thương mại.
