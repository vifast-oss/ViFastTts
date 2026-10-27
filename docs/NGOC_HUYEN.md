<p align="center">
  <img src="../resources/brand/vifasttts-lockup-cream.png" alt="ViFastTts · Giọng đọc tiếng Việt" width="560">
</p>

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
2. tải ONNX FP32 **N0 Q-init** từ GitHub release (có kiểm sha256);
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
- Giới hạn mặc định: **3000 ký tự** · 6 request/phút/IP · không lưu text/audio;
  có thể đổi bằng env `MAX_CHARS` (UI đọc `/api/config`).
- Web VPS có **3 mẫu nghe sẵn** (không gọi API) lấy từ release `n0-demo-samples-v1`.

## Model

> **Vocab Q (27/10/2026):** onset `Q` cho chữ `qu` là cấu trúc chuẩn bị đa phương ngữ,
> đứng cuối vocab. N0 giọng Bắc dùng Q-init với `Q` = `K` (giữ đúng giọng đã nghe); checkpoint/ONNX
> mới mang `onset_has_q=true`. Model/ONNX cũ chưa có Q bị từ chối rõ ràng (không adapter).

| Thành phần | Giá trị |
|---|---|
| Kiến trúc | acoustic `v2_slot5` small (6,1M tham số) |
| Sample rate | 24 kHz, mel 100 bin |
| Train | 17,9 h sạch, 60k bước, batch 8, MPS |
| Vocoder | Vocos pretrained `charactr/vocos-mel-24khz` (MIT) |
| ONNX | FP32, opset 18, acoustic + vocoder; `onset_has_q=true` (Q-init đang live) |
| Đo holdout | mel L1 **4,0 dB** (z 0,298); duration MAE 1,37 frame |
| Free-run 80 câu | mel **16,57 dB**; length 0,999; pause F1 0,825 |
| Thanh điệu | thật 0,9835 · copy 0,9784 · free **0,9743** |
| A/B tai người | **24/24** chọn model mới so P2 zero-shot |
| RTF thực tế | **0,045** end-to-end trên VPS CPU (5 câu, 22,44 s audio / 1,01 s xử lý) |

**Đang live:** **Q-init** (N0 cũ + hàng Q = K) — output bit-exact với N0 Bắc cũ; ONNX
`n0_q/acoustic.onnx` sha256 `16e66b70…`, `healthz` báo `onset_has_q=true`.
Fine-tune Q 3k (`val mel 0,26320` · `rough 0,76318`) đã export nhưng **chưa chọn**;
nghe A/B tại release `q-preview-2026-10-27`. Chi tiết: `docs/Q_ONSET.md`,
`docs/handoff/N0_DEPLOY.md`, `docs/handoff/TRANG_THAI.md`.

## Mặc định

- **Alpha 1,5** (`configs/small_ngochuyen.yaml`, `inference.sharpen_alpha`).
- **Vocos pretrained** — fine-tune 10k đã bị loại vì còn rè.
- **Model tự ngắt nghỉ** (`pause_mode="model"`); fixed pause chỉ khi
  `--fixed-pauses` / `pause_mode="fixed"`, mặc định tắt.

## Hai luồng

- **Dùng model:** chỉ cần ONNX + script, không torch, không train.
- **Train model:** cài `.[dev,audio,train,onnx]`, làm dữ liệu/MFA/cache, xem `TRAINING_N0.md`.

## Tùy chọn cách đọc

Trong web/Space có mục **Tùy chọn nâng cao: cách đọc từ**:

- mỗi dòng một quy tắc `từ gốc = cách đọc`, ví dụ `AI = ây ai`;
- key có thể là **cụm/domain/công thức** (dấu chấm, space, `+`, `->`, LaTeX), ví dụ
  `khongdich.com = không dịch chấm com`,
  `H2 + O2 -> H2O = hát hai cộng ô hai tạo ra nước`,
  `\frac{a}{b} = a trên b`; rule cụm được áp trước khi tách token;
- lưu trong `localStorage` của trình duyệt;
- mặc định **tích gửi để duyệt**; người dùng có thể bỏ tích để chỉ lưu local;
- quy tắc **tự lưu khi gõ**; gửi duyệt khi bấm **Tạo âm thanh** (nếu checkbox bật);
- server chỉ lưu cặp từ/cách đọc vào hàng chờ, không lưu câu/IP;
- admin chỉ duyệt được khi đặt `ADMIN_PASSWORD`; nếu chưa đặt, nút duyệt bị khoá;
- áp dụng cho request hiện tại, tối đa **50 quy tắc**, key ≤80 ký tự, value ≤120 ký tự;
- xem được **201 quy tắc tinh gọn + fallback tiếng Anh + ví dụ STEM** qua nút “Xem từ điển & STEM”.

API cũng nhận:

```json
{
  "text": "AI và VPS",
  "overrides": {"AI": "ây ai", "VPS": "vi pi ét"},
  "source": "api"
}
```

`GET /api/overrides` trả bảng có sẵn + quy tắc đã duyệt + mục `stem` (ví dụ quy tắc nội bộ cho hoá học/toán/vật lý/LaTeX, đọc thực tế do normalizer sinh). Quy tắc người dùng được ưu tiên trước STEM; các dạng như `NaCl` dạng trần, `x^2`, `\alpha` chưa có quy tắc riêng thì thêm vào ô cách đọc (hoặc dùng `\ce{NaCl}`).
Gửi đề xuất qua `POST /api/overrides/suggest` (tối đa 10 quy tắc/lần, không lưu câu/IP). Mặc định quy tắc chỉ nằm trong
localStorage; nếu người dùng tích “gửi để duyệt”, server chỉ lưu cặp từ/cách đọc vào hàng chờ,
không lưu câu/IP. Admin duyệt khi có `ADMIN_PASSWORD`; nếu chưa đặt, nút duyệt bị khoá.
Không hỗ trợ regex/script, chỉ thay từ nguyên vẹn; key người dùng được ưu tiên trước bảng có sẵn.

## File

- Checkpoint live: `runs/acoustic_ngochuyen_q/init_q.pt` (Q-init, `Q = K`;
  sha256 `3c330cfc…`); gốc N0: `runs/acoustic_ngochuyen/best.pt`
  (sha256 `d1b21642…f640070`); fine-tune Q 3k: `runs/acoustic_ngochuyen_q/best.pt`.
- Config: `configs/small_ngochuyen.yaml` (N0) · `configs/small_ngochuyen_q.yaml` (Q fine-tune).
- ONNX live: `artifacts/onnx/n0_q/{acoustic,vocoder}.onnx`; candidate:
  `artifacts/onnx/n0_q_ft/`; bản N0 cũ `artifacts/onnx/n0/` bị runtime mới từ chối.
- Release:
  - prod candidate nội bộ: https://github.com/dvchd/ViFastTts/releases/tag/n0-ngochuyen-prod-v1
    (asset Q đang live: `n0_onnx_fp32_q.zip`, sha256 `ef35567c…`)
  - research: https://github.com/dvchd/ViFastTts/releases/tag/n0-ngochuyen-research-v1
  - nghe thử Q: https://github.com/dvchd/ViFastTts/releases/tag/q-preview-2026-10-27
  - 3 mẫu VPS: https://github.com/dvchd/ViFastTts/releases/tag/n0-demo-samples-v1

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
