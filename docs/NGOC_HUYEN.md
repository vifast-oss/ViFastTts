# Ngọc Huyền — model TTS tiếng Việt (research, phi thương mại)

> **Model duy nhất được đóng gói kèm repo dưới dạng “model mẫu”.**
> Dataset gốc `pnnbao-ump/ngochuyen_voice` là **CC BY-NC 4.0** → model/weights chỉ dùng
> **nghiên cứu, phi thương mại**. Không dùng để giả giọng, lừa đảo, bán lại hoặc production
> thương mại. Code repo là MIT; quyền của dataset/giọng vẫn giữ nguyên.

## Chạy thử nhanh

```bash
git clone https://github.com/dvchd/ViFastTts.git
cd ViFastTts
./scripts/run_ngochuyen_demo.sh
# Windows PowerShell:
# powershell -ExecutionPolicy Bypass -File .\scripts\run_ngochuyen_demo.ps1
# mở http://127.0.0.1:8090
```

Script tự:
1. kiểm tra Python ≥ 3.11;
2. tải ONNX FP32 N0 từ GitHub release (có kiểm sha256);
3. tạo `.venv-demo` + cài `onnxruntime`, `fastapi`, `uvicorn`;
4. chạy web demo ONNX, **không cần torch**.

Không muốn tải script? Xem `deploy/vifasttts_demo/README.md` để chạy Docker hoặc
`synthesize-onnx` thủ công.

## Demo online

- Web: **https://vifasttts.hoctuthien.com/**
- Hugging Face model: **https://huggingface.co/dvchd/vifasttts-ngochuyen-small**
- Space demo miễn phí: **https://huggingface.co/spaces/dvchd/vifasttts-ngochuyen-demo**
- Thống kê demo (mở công khai): **https://vifasttts.hoctuthien.com/admin**
- Health: https://vifasttts.hoctuthien.com/healthz
- Giới hạn: 300 ký tự · 6 request/phút/IP · không lưu text/audio.

## Model

| Thành phần | Giá trị |
|---|---|
| Kiến trúc | acoustic `v2_slot5` small (6,1M tham số) |
| Sample rate | 24 kHz, mel 100 bin |
| Train | 17,9 h sạch, 60k bước, batch 8, MPS |
| Vocoder | Vocos pretrained `charactr/vocos-mel-24khz` (MIT) |
| ONNX | FP32, opset 18, acoustic + vocoder |
| Đo holdout | mel L1 **4,0 dB** (z 0,298); duration MAE 1,37 frame |
| Free-run 80 câu | mel **16,57 dB**; length 0,999; pause F1 0,825 |
| Thanh điệu | thật 0,9835 · copy 0,9784 · free **0,9743** |
| A/B tai người | **24/24** chọn model mới so P2 zero-shot |
| RTF thực tế | **0,045** end-to-end trên VPS CPU (5 câu, 22,44 s audio / 1,01 s xử lý) |

## Mặc định

- **Alpha 1,5** (`configs/small_ngochuyen.yaml`, `inference.sharpen_alpha`).
- **Vocos pretrained** — fine-tune 10k đã bị loại vì còn rè.
- **Model tự ngắt nghỉ** (`pause_mode="model"`); fixed pause chỉ khi
  `--fixed-pauses` / `pause_mode="fixed"`, mặc định tắt.

## Hai luồng

- **Dùng model:** chỉ cần ONNX + script, không torch, không train.
- **Train model:** cài `.[dev,audio,train,onnx]`, làm dữ liệu/MFA/cache, xem `TRAINING_N0.md`.

## File

- Checkpoint: `runs/acoustic_ngochuyen/best.pt` (không có trong git; tải release).
- Config: `configs/small_ngochuyen.yaml`.
- ONNX: `artifacts/onnx/n0/{acoustic,vocoder}.onnx`.
- Release:
  - prod candidate nội bộ: https://github.com/dvchd/ViFastTts/releases/tag/n0-ngochuyen-prod-v1
  - research: https://github.com/dvchd/ViFastTts/releases/tag/n0-ngochuyen-research-v1

## Dữ liệu & huấn luyện lại

Không kèm audio/transcript gốc. Nguồn:
https://huggingface.co/datasets/pnnbao-ump/ngochuyen_voice (revision `1ebbfbd1…`).

Quy trình đầy đủ (lọc text, split, MFA, segment, cache, train, eval):
`docs/TRAINING_N0.md`. Model card/giới hạn: `docs/handoff/N0_agent2.md`.

## Giới hạn đã biết

- Single-speaker; không speaker ID/zero-shot.
- Từ **“ấm”** trong câu demo `fresh04` có thể hơi rè cục bộ.
- Dataset thiên tin tức/đọc báo; câu ngoài domain có thể kém tự nhiên.
- Không có moderation/safety filter; **không production**.
