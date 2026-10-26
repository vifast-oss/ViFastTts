# N0 — research release (GitHub)

> **Research / non-commercial — NOT production.** Dataset CC-BY-NC-4.0; không dùng thương mại,
> không dùng giả giọng/lừa đảo. Xem `LICENSE.md` trong gói.

## Link

- Release: https://github.com/dvchd/ViFastTts/releases/tag/n0-ngochuyen-small-research-v1
- Asset: `n0_ngochuyen_small_research_v1.zip`
- SHA256SUMS: cùng release

## Nội dung gói

- `runs/acoustic_ngochuyen/best.pt` — small v2_slot5, 6,1M, step 60.000
  (sha256 `d1b21642…f640070`).
- `configs/small_ngochuyen.yaml` + `data/ngochuyen/{mel_stats,f0_stats_v2}.json`.
- `artifacts/pretrained/vocos-mel-24khz/pytorch_model.bin` — Vocos **pretrained mặc định** (MIT).
- 10 câu demo mới + `texts.json`; `MODEL_CARD.md`, `LICENSE.md`, `metrics/summary.json`,
  `inference.py`, `README.md`.

**Không kèm**: audio/transcript gốc, cache, Vocos fine-tune (đã loại vì rè).

## Kiểm chứng

- Zip: 129.508.079 byte · sha256
  `98689c76911286034ab4a7df86793ee7a796dd29b33dbe09543bd3c969cfd375`.
- Đã tải lại từ GitHub và giải nén chạy `inference.py` CPU: WAV 24 kHz tạo thành công.
- Code trong tag: `n0(infer): mặc định model tự nghỉ; --fixed-pauses/pause_mode opt-in`.

## Ngắt nghỉ

Mặc định `pause_mode="model"` — model tự nghỉ. `--fixed-pauses` (CLI/HTTP
`pause_mode="fixed"`) là opt-in, **mặc định tắt**.

## License

Dataset **CC-BY-NC-4.0** (`pnnbao-ump/ngochuyen_voice`); Vocos MIT; model weights
research/non-commercial, không bảo hành. Không dùng production.
