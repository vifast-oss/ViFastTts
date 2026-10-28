# Benchmark N0 — nội bộ & tham chiếu bên ngoài

> Ngày: 28/10/2026 · Trạng thái: **chuẩn bị + đo lần đầu**, base 60k chưa xong.
> Mục tiêu: cùng một bộ test đóng băng, cùng script, tách rõ **so sánh nội bộ**
> (cùng giọng) và **tham chiếu ngoài** (khác giọng, chỉ CER/RTF/nghe).

## 1. Bộ test nội bộ đóng băng

```text
data/ngochuyen/bench/bench200.jsonl
200 segment holdout, index 300–500
SHA256: 56faaf84b0a4f58f82152d7c55f5b8456a10023b782162dc1d6e80d903793f90
```

- Không nằm trong train/val.
- Không trùng `demo_texts`, `ab8_texts`, `fresh_texts` (đã kiểm parent ID).
- Khoảng **0,38 h audio**; đủ cho mel/CER/thanh nhưng **không** thay bộ test 1.000+ câu.
- Tạo lại: `tools/build_n0_bench.py`.

Chấm nội bộ:

```bash
.venv/bin/python tools/bench_n0.py \
  --manifest data/ngochuyen/bench/bench200.jsonl \
  --out artifacts/bench_n0/internal_200 \
  --model small=runs/acoustic_ngochuyen_q/resolved_config.json=runs/acoustic_ngochuyen_q/init_q.pt \
  --model base40=runs/acoustic_ngochuyen_base/resolved_config.json=runs/acoustic_ngochuyen_base/best.pt
```

## 2. Kết quả nội bộ lần đầu

| Model | mel z | mel dB | CER-100 | pause F1 | tone C |
|---|---:|---:|---:|---:|---:|
| small Q-init @60k | 0,2947 | 3,994 | 0,0868 | **0,8279** | **0,9778** |
| base @40k | **0,2641** | **3,584** | **0,0819** | 0,8224 | 0,9774 |

Đọc:

- Base tốt hơn **mel/CER**, nhỉnh hơn pause; tone gần như hòa.
- Đây là **cùng giọng, cùng test**, nên so được trực tiếp.
- Base 60k sẽ chấm lại sau khi train xong; chưa đưa vào bảng này.

## 3. Tham chiếu model ngoài — cùng 10 câu mới, alpha 0

Bộ text: `artifacts/ngochuyen/fresh_texts.json` (10 câu, không dùng train/holdout).
Không có audio thật; **khác giọng** nên chỉ so CER/RTF/nghe, không so mel/F0.

| Model | Params | License | CER-10 | RTF (Mac CPU/MPS) | Ghi chú |
|---|---:|---|---:|---:|---|
| ZeroTTS | 202M | MIT | **0,0415** | 0,469 | ONNX CPU, 48 kHz, voice `maichi`; actual |
| VieNeu-TTS v3 Turbo | 131M | Apache-2.0 | 0,0520 | **0,333** | 48 kHz, actual |
| N0 base @40k | 17,1M | nội bộ | 0,0609 | 0,0148* | *MPS; khác phần cứng |
| N0 small @60k | 7,0M | nội bộ | 0,0675 | 0,0141* | *MPS; khác phần cứng |

- **Không đọc CER này như xếp hạng chất lượng**: ZeroTTS/VieNeu có 1.000–10.000+ giờ,
  giọng khác, và CER đo bằng Whisper trên 10 câu.
- RTF nội bộ đo bằng PyTorch MPS; RTF production ONNX CPU trên VPS từng là **0,032**.
  Ba con số RTF **không cùng phần cứng** — chỉ dùng để tham khảo.
- ZeroTTS có sẵn voice, nhưng **encoder clone giọng chưa phát hành** trong bản mở.
- VieNeu v3 Turbo là baseline mở mạnh; v3 Nano 48M và v4 (đóng) không chấm ở đây.

Script:

```bash
# ZeroTTS
.venv/bin/pip install --no-deps zerotts==0.1.5
.venv/bin/python tools/bench_external_zerotts.py \
  --texts artifacts/ngochuyen/fresh_texts.json \
  --out artifacts/bench_n0/external_zerotts.json

# VieNeu v3 Turbo
.venv/bin/pip install vieneu==3.8.3 sea-g2p kaldi-native-fbank
.venv/bin/python tools/bench_external_vieneu.py \
  --texts artifacts/ngochuyen/fresh_texts.json \
  --out artifacts/bench_n0/external_vieneu_turbo.json --mode v3turbo
```

## 4. Các model tiếng Việt mới/đáng theo dõi (10/2026)

| Model | Dữ liệu/điểm mạnh | License | Dùng được? |
|---|---|---|---|
| **ZeroTTS** (202M, ONNX) | 48 kHz, CPU streaming, zero-shot voice latents; CER thấp | MIT | **Đã chấm**; baseline ngoài |
| **VieNeu v3 Turbo** (131M) | 10k+ h, Vi–En, 48 kHz, clone 3–5 s, CPU | Apache-2.0 | **Đã chấm** |
| **VieNeu v3 Nano** (48M) | ONNX 24 kHz, nhẹ hơn, chất lượng thấp hơn | Apache-2.0 | Có thể chấm thêm |
| **F5-TTS Vietnamese 1000h** | F5 flow matching, 1.000 h, zero-shot | CC-BY-NC-SA-4.0 | Chưa chấm: cần GPU + ref audio |
| **Vi-F5-TTS** | F5 fine-tune 100 h | MIT (model card) | Chưa chấm: cần GPU + ref audio |
| **viXTTS / XTTS-v2 Vietnamese** | XTTS clone, 467M | kiểm tra lại (thường NC) | Chưa chấm: nặng, không ONNX nhẹ |
| **OmniVoice** (0,6B) | đa ngữ; báo cáo RTF CPU ~6,1× | cần kiểm tra | Chưa chấm; chậm |
| **Chatterbox Multilingual V3** (0,5B) | 23 ngôn ngữ, MIT | MIT | **Không có tiếng Việt** trong danh sách chính thức |
| **Qwen3-TTS** (1,7B) | 10 ngôn ngữ | cần kiểm tra | **Không có tiếng Việt** |
| **Piper/Kokoro** | nhẹ, ONNX | Apache/MIT | Không có tiếng Việt chính thức |

Nguồn chính:
- ZeroTTS: <https://huggingface.co/zeroweight-ai/ZeroTTS>
- VieNeu v2/v3: <https://huggingface.co/pnnbao-ump/VieNeu-TTS-v2>,
  <https://huggingface.co/pnnbao-ump/VieNeu-TTS-v3-Turbo>
- F5 Vi: <https://huggingface.co/hynt/F5-TTS-Vietnamese-ViVoice>
- Vi-F5: <https://huggingface.co/danhtran2mind/Vi-F5-TTS>
- Chatterbox: <https://huggingface.co/ResembleAI/chatterbox>
- Qwen3-TTS: <https://github.com/QwenLM/Qwen3-TTS>

## 5. Benchmark online

Có thể dùng để tham khảo:
- **Open TTS Leaderboard** (HF, 30/09/2026): WER/CER, RTFx, TTFA, speaker similarity.
  <https://huggingface.co/spaces/hf-audio/open_tts_leaderboard>
- TTS Arena v2, Artificial Analysis, Voice Arena.

**Chưa submit** vì:
- giọng N0 là **CC-BY-NC-4.0**, cần rà license/quyền của người nói;
- bộ test và model chưa chốt;
- nhiều leaderboard nghiêng tiếng Anh/đa ngữ, không công bằng cho tiếng Việt.

## 6. Việc tiếp theo

1. Base 60k xong → chạy lại `tools/bench_n0.py` với `base60`.
2. A/B 50–100 câu mới, alpha 0; chỉ chốt nếu base thắng rõ.
3. Nếu base thắng: export ONNX, đo RTF CPU thật, cập nhật model card.
4. Không submit online trước khi rà license và có bộ test cuối.
