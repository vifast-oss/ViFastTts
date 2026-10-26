# N0 — ONNX + demo service `vifasttts.hoctuthien.com`

> **Demo nghiên cứu / phi thương mại** — dataset CC-BY-NC-4.0. Không dùng làm production
> thương mại, không dùng giả giọng/lừa đảo.

## 1. ONNX

Đã xuất (FP32, opset 18):

| File | Kích thước | Nguồn |
|---|---:|---|
| `artifacts/onnx/n0/acoustic.onnx` | ~30 MB | `runs/acoustic_ngochuyen/best.pt` |
| `artifacts/onnx/n0/vocoder.onnx` | ~52 MB | `artifacts/pretrained/vocos-mel-24khz/pytorch_model.bin` |

Lệnh:

```bash
vifasttts export-onnx --config configs/small_ngochuyen.yaml \
  --checkpoint runs/acoustic_ngochuyen/best.pt \
  --output artifacts/onnx/n0/acoustic.onnx --opset 18
vifasttts export-vocoder-onnx --config configs/small_ngochuyen.yaml \
  --checkpoint artifacts/pretrained/vocos-mel-24khz/pytorch_model.bin \
  --output artifacts/onnx/n0/vocoder.onnx --opset 18
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
- Chống lạm dụng: 6 request/phút/IP (X-Forwarded-For), 1 request đồng thời, text 300 ký tự,
  không lưu text/audio.
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
- Commit upload: `6cfd13e16be700aaec68175086ee44be929bc01b`.

## 4. ONNX trong release

Release prod có asset `n0_onnx_fp32.zip` (acoustic + vocoder ONNX + SHA256SUMS);
có thể tải riêng nếu không dùng checkpoint PyTorch. Package chính vẫn chứa checkpoint +
config + stats + Vocos pretrained.

## 5. Giới hạn

- Public demo, không auth; rate limit đơn giản, không chống DDoS.
- Không lưu dữ liệu nhưng VPS/provider vẫn có access log hạ tầng.
- File `fresh04` “ấm” có thể hơi rè cục bộ; không phải lỗi service.
- Dataset CC-BY-NC-4.0; không dùng thương mại.
