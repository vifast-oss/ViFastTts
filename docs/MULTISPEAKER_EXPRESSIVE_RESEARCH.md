# Đa giọng, song ngữ, biểu cảm và sắc thái đọc — khảo sát cho ViFastTts

> **Trạng thái:** khảo sát, **chưa triển khai**. · **Ngày:** 30/10/2026.
> **Liên quan:** `docs/TTS_ARCHITECTURE_RESEARCH.md`, `docs/VI_TTS_DATA_REFERENCE.md`,
> `docs/ENGLISH_FROM_VI.md`, `docs/MODEL_FLOW.md`, `docs/EVAL_TOOLS.md`.
> Số liệu model/dataset lấy từ trang chính thức + paper (xem §10); **chưa tự đo** trên M6.

## 0. TL;DR

- **Đa giọng tiếng Việt** đã có nhiều lựa chọn chạy CPU/ONNX:
  **VieNeu-TTS v3 Turbo** (Apache-2.0, 25 giọng, 48 kHz, En–Vi, CPU ONNX RTF ≈ 0,5),
  **V-TTS** (74,8M, 5 giọng + zero-shot, CPU RTF ≈ 0,24, CC BY-NC),
  **VietTTS** (24 giọng, CC BY-NC), **F5-TTS-Vi** (1000 h, zero-shot, GPU),
  **XTTS/VALL-E/VoiceCraft** huấn luyện trên PhoAudiobook.
- **Song ngữ Việt–Anh**: VieNeu v3 Turbo là mô hình mở đáng chú ý nhất (10.000 h, 48 kHz,
  code-switch); bản Nano 48M yếu tiếng Anh. Bài học từ Piper/VITS: **thêm dữ liệu code-switch
  cải thiện tiếng Anh mà không cần tăng kích thước model**.
- **Biểu cảm**: ba họ điều khiển — nhãn cảm xúc (4–6 lớp), reference style (StyleTTS2, V-TTS
  style encoder 128), prompt/instruct (Qwen3-TTS, IndexTTS2). Non-verbal cues kiểu VieNeu
  (`[cười]`, `[thở dài]`, `[hắng giọng]`) là mức thấp nhất, dễ tích hợp.
- **Sắc thái/kiểu đọc**: gắn với **reference audio** hoặc **LoRA**; VieNeu v3 Turbo đã bỏ
  tham số `style` (style theo reference). Với ViFastTts, cách thực tế là style embedding +
  reference encoder, hoặc LoRA từng giọng/kiểu.
- **Dữ liệu**: VIVOS (15 h, 65 spk), ViMD (102,56 h, 12.955 spk, CC BY-NC-ND),
  PhoAudiobook (941 h, 735 spk), viVoice (1.017 h), VieNeu-1000h (CC BY-NC),
  VLSP 2022 emotion (5 h, 1 spk, 4 cảm xúc).
- **Khuyến nghị**: nếu cần ra sản phẩm nhanh, **đánh giá VieNeu v3 Turbo như engine thứ hai**
  (Apache-2.0, 25 giọng, En–Vi, CPU ONNX) bên cạnh ViFastTts; nếu tự xây, đi theo R1
  (speaker embedding) → R2 (emotion/style) → R3 (bilingual phoneme) → R4 (zero-shot).

### Chọn nhanh

| Nhu cầu | Lựa chọn | Ghi chú |
| --- | --- | --- |
| Đa giọng + En–Vi + CPU | **VieNeu v3 Turbo** | Apache-2.0; 25 giọng; RTF 0,55–0,62 |
| Nhẹ nhất, 5 giọng + clone | **V-TTS** | 74,8M; CC BY-NC; RTF 0,24 |
| Zero-shot chất lượng cao | F5-TTS-Vi / XTTS-PhoAudiobook | GPU; NC/research |
| Tự xây trong ViFastTts | R1 speaker embedding | giữ deterministic/ONNX |
| Biểu cảm theo nhãn | VLSP 2022 + style embedding | 4 cảm xúc |
| Kiểu đọc riêng | reference audio / LoRA | VieNeu/V-TTS |

## 1. Hiện trạng ViFastTts

| Thành phần | Hiện tại | Hệ quả cho multi-speaker/expressive |
| --- | --- | --- |
| Model | `v2_slot5`, ~6,1M, non-autoregressive, deterministic | Nhẹ, CPU/ONNX; nhưng capacity hạn chế |
| Input | 5 ID/âm tiết + boundary/punct | Không có speaker/style/language ID |
| Speaker | **single-speaker** (`speaker_conditioning: false`) | Muốn đa giọng phải thêm embedding + data |
| Style | chỉ `speed`, `f0_scale`, `sharpen_alpha` | Chưa có emotion/style token |
| Bilingual | 5 ID tiếng Việt; English respell | Không biểu diễn được cụm/âm vị Anh (xem `ENGLISH_FROM_VI.md`) |
| Vocoder | Vocos 24 kHz | Dùng lại được cho multi-speaker/style (mel→wave) |
| Deploy | ONNX CPU, Rust port, HF Space | Mọi input mới phải export ONNX + sync |

**Kết luận:** kiến trúc hiện tại đủ nhanh/nhẹ, nhưng để đa giọng/biểu cảm cần **thêm điều kiện
hoá** (speaker/style/language) và **dữ liệu**; không chỉ thêm tham số.

## 2. Đa giọng tiếng Việt — mô hình

### 2.1 Open-source / on-device

| Model | Size | Giọng / zero-shot | Zero-shot | En–Vi | CPU/ONNX | License | Ghi chú |
| --- | ---: | --- | --- | --- | --- | --- | --- |
| **VieNeu-TTS v3 Turbo** | ~0,1B | **25** preset | có (3–8 s) | **có** (10k h) | **có**, RTF 0,55–0,62 (int8 0,35–0,37) | **Apache-2.0** | 48 kHz; emotion cues; conversation; streaming; LoRA; v4 proprietary |
| **VieNeu-TTS v3 Nano** | **48M** | 11 preset | có | yếu | có, RTF 0,11–0,22 | Apache-2.0 | 24 kHz; cho CPU yếu; English kém |
| **V-TTS (valtec)** | 74,8M | 5 preset | có (3–10 s) | hạn chế | có, RTF 0,24 zero-shot; 0,34–0,54 multi | **CC BY-NC 4.0** | speaker 512 + style 128; prosody transfer |
| **VietTTS** | VITS (theo repo) | 24 | có | không | PyTorch (ONNX tùy) | code Apache-2.0; model CC BY-NC | in-the-wild data |
| **F5-TTS-Vi** | ~? | zero-shot | có | không | GPU | **CC-BY-NC-SA-4.0** | 1000 h (ViVoice + VLSP) |
| **XTTS-v2 / VALL-E / VoiceCraft** | 0,5B–1B | zero-shot | có | multilingual | GPU | research | train trên PhoAudiobook 941 h |
| **Piper/VITS CS** | nhỏ | multi | không | **có** (CS) | **có** | tùy | thêm data CS, không tăng size |

**Nhận xét:**

- **VieNeu v3 Turbo** là mô hình mở gần nhất với nhu cầu "đa giọng + En–Vi + CPU": 25 giọng,
  48 kHz, emotion cues, Apache-2.0. Đánh đổi: ~0,1B, CPU RTF 0,5 (chậm hơn ViFastTts), và
  chất lượng tiếng Anh/code-switch cần nghe kiểm chứng.
- **V-TTS** nhẹ hơn (74,8M), 5 giọng + zero-shot, CPU RTF 0,24, nhưng **CC BY-NC** và không có
  bằng chứng En–Vi.
- **F5-TTS-Vi / XTTS / VALL-E** mạnh zero-shot nhưng GPU và license research; không phù hợp
  ONNX CPU trực tiếp.
- **Piper/VITS CS** là bằng chứng: model nhỏ + data code-switch vẫn cải thiện tiếng Anh.

### 2.2 Kiến trúc đa giọng

Ba họ chính:

1. **Speaker embedding + FiLM/AdaIN** (VITS/YourTTS/V-TTS):
   - Speaker encoder (ECAPA-TDNN 192 hoặc x-vector 512) → vector.
   - Đưa vào encoder/decoder qua FiLM/AdaIN hoặc concat; thêm speaker classifier.
   - Deterministic, ONNX-friendly; phù hợp ViFastTts.
2. **Zero-shot reference** (V-TTS, XTTS, VALL-E):
   - Speaker encoder + reference audio; có thể thêm style/prosody encoder.
   - Linh hoạt nhưng nặng hơn, cần reference lúc inference, dễ nhiễu.
3. **LLM/codec** (VieNeu v2/v3, VALL-E):
   - Backbone LM + neural codec; chất lượng cao, nhưng autoregressive/flow, khó deterministic
     và nặng CPU hơn.

**Bài học:** với mục tiêu CPU/ONNX, họ (1) là hợp lý nhất; (2) chỉ nên làm sau khi (1) ổn định.

## 3. Song ngữ Việt–Anh

### 3.1 Mô hình

- **VieNeu-TTS v3 Turbo**: 10.000 h Việt–Anh, 48 kHz, 25 giọng, code-switch; Apache-2.0.
  Bản **Nano 48M** yếu tiếng Anh/code-switch rõ rệt (theo README).
- **VieNeu v2 / v2-Turbo**: 0,3B, En–Vi code-switch, GGUF/ONNX; deprecated nhưng tham khảo.
- **Piper/VITS CS pipeline** (paper "Lightweight TTS Pipeline for Codeswitching in Vietnamese"):
  thêm dữ liệu code-switch cải thiện độ rõ tiếng Anh/mixed **mà không tăng kích thước model
  hay CPU** — đây là bằng chứng quan trọng cho ViFastTts.
- **sea-g2p**: G2P Việt/Thái/Indonesia + English code-switch; dùng cho frontend.
- **Bilingual phoneme set** (arXiv 2508.19270): bộ âm vị chung Việt–Anh cho ASR/TTS.
- **TSPC** (arXiv 2509.05983): phoneme-centric cho code-switch Việt–Anh (ASR).
- **ViMedCSS**: 34 h, 16.576 utterance code-switch y khoa (ASR; có thể dùng làm text/audio
  tham chiếu, không phải TTS dataset).
- **F5-TTS-Vi**: 1000 h (ViVoice + VLSP 2021–2023), zero-shot; chưa có bằng chứng En–Vi.

### 3.2 Bài học kỹ thuật

- **Không cần model khổng lồ** nếu dữ liệu code-switch đủ: Piper/VITS nhỏ vẫn cải thiện rõ.
- **Bộ âm vị chung + language ID** quan trọng hơn việc nhồi thêm ngôn ngữ vào cùng vocab âm tiết.
- **Frontend 5-ID hiện tại không đủ** cho tiếng Anh (xem `ENGLISH_FROM_VI.md`): cần phoneme
  sequence hoặc branch riêng cho tiếng Anh.
- **Đánh giá**: CS-WER (chỉ trên span code-switch) + N-WER + English WER + Vietnamese CER.

## 4. Biểu cảm trong câu nói

### 4.1 Ba họ điều khiển

| Họ | Ví dụ | Ưu | Nhược |
| --- | --- | --- | --- |
| **Nhãn cảm xúc** | 4–6 lớp: neutral, vui, buồn, giận, ngạc nhiên, sợ | đơn giản, deterministic, dễ ONNX | trung bình hoá, thiếu sắc thái mịn |
| **Reference style** | StyleTTS2 style encoder; V-TTS style 128; IndexTTS2 | tự nhiên, chuyển style từ audio mẫu | cần reference, dễ lẫn speaker |
| **Prompt/instruct** | Qwen3-TTS "speak warmly"; ECE-TTS; WeSCon | linh hoạt, ngôn ngữ tự nhiên | thường autoregressive/LLM, khó CPU |
| **Non-verbal cues** | VieNeu `[cười]`, `[thở dài]`, `[hắng giọng]`; Dia laughter/cough | rẻ, dễ tích hợp | chỉ là điểm nhấn, không phải emotion đầy đủ |

### 4.2 Mô hình/paper đáng chú ý

- **StyleTTS2**: non-autoregressive, style diffusion + style encoder; reference-based;
  multi-speaker; nền cho nhiều model nhẹ (Kokoro).
- **IndexTTS2** (AAAI 2026): tách **emotion** và **speaker**; điều khiển duration; zero-shot.
- **ECE-TTS**: zero-shot emotion TTS, điều khiển emotion + intensity.
- **WeSCon** (NeurIPS 2025): điều khiển emotion/rate **theo từ** trong câu.
- **TED-TTS** (ACL 2026): chuyển emotion trong câu **training-free**.
- **Sparse autoencoder** (arXiv 2606.01479): phân tích/điều khiển emotion trong LLM-TTS.
- **VieNeu v3 Turbo**: emotion cues phiên bản thử nghiệm; chưa phải emotion label đầy đủ.
- **V-TTS**: prosody transfer từ reference (intonation, rhythm, emotion).
- **VibeVoice / Dia / Higgs Audio V2**: multi-speaker, long-form, biểu cảm; không phải tiếng Việt.

### 4.3 Đánh giá biểu cảm

- **Phân loại cảm xúc** trên audio sinh (SER classifier) — accuracy/F1.
- **Style similarity** (embedding cosine) nếu có reference.
- **Prosody**: F0 range/mean, speaking rate, pause duration, energy.
- **Người nghe**: MOS/CMOS/ABX cho tự nhiên + đúng cảm xúc.
- **Regression**: CER tiếng Việt, không được tăng.

## 5. Sắc thái / kiểu đọc

### 5.1 Các kiểu đọc

| Kiểu | Đặc điểm | Dữ liệu tham khảo |
| --- | --- | --- |
| Tin tức / thời sự | rõ, đều, ít cảm xúc | ViMD (news 63 tỉnh), VLSP 2020 |
| Audiobook / kể chuyện | chậm, ngữ điệu, nhấn cảm xúc | PhoAudiobook (735 narrator), viVoice |
| Hội thoại / chatbot | tự nhiên, ngắt nghỉ, khẩu ngữ | VietSuperSpeech (267 h), VietSpeech (1.100 h) |
| Phim / phỏng vấn | cảm xúc mạnh, đa dạng | VLSP 2022 emotion (5 h, 4 cảm xúc) |
| Quảng cáo / trình bày | năng lượng, nhấn mạnh | cần thu thêm |

### 5.2 Cách điều khiển

- **Reference audio**: chọn clip mẫu đúng kiểu; model bám style (VieNeu v3 Turbo, V-TTS,
  StyleTTS2). Đây là cách thực tế nhất.
- **LoRA**: fine-tune một giọng/kiểu với 10–30 phút audio (VieNeu v3 Turbo hỗ trợ LoRA;
  ~6 GB GPU). Phù hợp "kiểu đọc riêng" ổn định.
- **Style token/embedding**: nhãn `news/audiobook/chat` + style encoder; nhẹ, deterministic.
- **Prompt/instruct**: Qwen3-TTS kiểu "speak slowly, warm"; mạnh nhưng LLM/AR.
- **Lưu ý VieNeu**: tham số `style` đã **deprecated**; style nằm trong reference voice/clip.

## 6. Dữ liệu

| Dataset | Giờ | Speaker | Kiểu | License / truy cập | Dùng cho |
| --- | ---: | ---: | --- | --- | --- |
| **VIVOS** | 15 | 65 (46 train/19 test) | đọc, studio | mở cho nghiên cứu | multi-speaker cơ bản |
| **ViMD** | 102,56 | 12.955 | news, 63 phương ngữ | **CC BY-NC-ND 4.0** | đa giọng/đa vùng (cẩn thận ND) |
| **PhoAudiobook** | 941 | 735 | audiobook | research (kiểm tra HF) | multi-speaker, audiobook style |
| **viVoice** | 1.017 | 186 kênh | narration YouTube | cần quyền (HF) | multi-speaker, expressive |
| **VietSpeech** | 1.100 | ? | social voice | research | đa dạng domain |
| **VieNeu-1000h** | 1.000 | multi | TTS, phonemize | **CC BY-NC 4.0**, không public | multi-speaker, En–Vi |
| **VLSP 2022 TTS emotion** | ~5 | 1 | phim/phỏng vấn, 4 cảm xúc | research (VLSP) | emotion |
| **Emotion corpus (IEEE)** | ? | 147 | 5.280 utterance, 4 cảm xúc | research | emotion |
| **quangdung/emotion-tts-vietnamese** | 69,5 GB | ? | emotion TTS | kiểm tra HF | emotion |
| **ViMedCSS** | 34 | ? | y khoa, code-switch | research | CS text/audio (ASR) |
| **VietSuperSpeech** | 267,39 | ? | hội thoại/call center | research | conversational style |
| **Vietnam-Celeb / VieSpeaker** | 87k utt / 902 h | 1.000 / 4.715 | speaker recognition | research | speaker encoder |

**Cảnh báo license:**

- **CC BY-NC-ND** (ViMD): "ND" hạn chế tạo derivative — training model có thể bị coi là
  derivative; cần tư vấn pháp lý trước khi dùng cho sản phẩm.
- **CC BY-NC** (V-TTS, VieNeu-1000h, N0 Ngọc Huyền, F5 CC-BY-NC-SA): chỉ phi thương mại.
- **Research-only** (VLSP, PhoAudiobook/viVoice tùy điều kiện): không dùng thương mại nếu
  chưa có phép.
- **Commercial**: FutureBeeAI (30 h/30 spk, 1–2 h/spk), hoặc thuê thu âm.

## 7. Kiến trúc đề xuất cho ViFastTts

### 7.1 Multi-speaker (R1)

- Thêm **speaker embedding** 192–512 (ECAPA/x-vector) + FiLM/AdaIN ở encoder/decoder.
- Input mới: `speaker_id` (int) hoặc `speaker_emb` (float [D]); ONNX thêm input.
- Speaker classifier (aux loss) + speaker interpolation.
- Model +1–3M; giữ deterministic; Vocos dùng lại.
- Data: 5–10 giọng, 5–20 h/giọng (VIVOS quá ít/giọng ~14 phút → cần PhoAudiobook/FutureBee
  hoặc thu thêm).

### 7.2 Emotion/style (R2)

- **Nhãn** 4–6 cảm xúc + **style embedding** 128 từ reference encoder.
- FiLM/AdaIN ở encoder + duration/pitch predictor.
- Prosody controls: `f0_scale`, `energy_scale`, `speed` (đã có một phần).
- Deterministic: label/reference embedding, không sampling.
- Data: VLSP 2022 (4 cảm xúc) + thu thêm 1–5 h/cảm xúc.

### 7.3 Bilingual (R3)

- **Bộ âm vị chung Việt–Anh** + language ID (2 chiều), hoặc branch phoneme cho tiếng Anh.
- Frontend: sea-g2p / G2P EN → IPA; VI rule-based → IPA.
- Data: VieNeu-1000h (nếu được phép), viVoice, ViMedCSS (CS), hoặc thu code-switch.
- Không dùng 5-ID syllable cho tiếng Anh (xem `ENGLISH_FROM_VI.md`).

### 7.4 Zero-shot (R4)

- Speaker encoder + reference audio; V-TTS/XTTS là tham chiếu.
- Nặng hơn R1; chỉ làm sau khi R1 ổn định.

### 7.5 Kích thước/CPU

- 6,1M hiện tại quá nhỏ cho multi-speaker + emotion + bilingual.
- Mục tiêu 20–50M (tham chiếu VieNeu Nano 48M, V-TTS 74,8M), RTF < 0,3 trên M6.
- Giữ Vocos 24 kHz; nếu 48 kHz thì vocoder/chi phí tăng.

### 7.6 Phương án "mua" — dùng VieNeu v3 Turbo

- Apache-2.0, 25 giọng, En–Vi, emotion cues, CPU ONNX, RTF ≈ 0,5.
- Có thể dùng làm **engine thứ hai** cho multi-speaker/expressive/bilingual, giữ ViFastTts
  cho deterministic/nhanh/tiếng Việt.
- Cần đo: MOS, RTF trên M6, chất lượng En–Vi, license model/data, dung lượng.

## 8. Lộ trình & cổng đề xuất

| Bước | Nội dung | Cổng đề xuất |
| --- | --- | --- |
| **R1** | 5 giọng + speaker embedding | SECS ≥ 0,80 · MOS ≥ 3,8 · VI CER delta ≤ +0,01 · RTF < 0,3 |
| **R2** | 4 cảm xúc + style token/reference | emotion accuracy ≥ 70% · MOS ≥ 3,8 · ABX style |
| **R3** | Việt–Anh code-switch | CS-WER ≤ 20% · EN WER ≤ 1,0 · VI CER delta ≤ +0,01 |
| **R4** | zero-shot cloning | SECS ≥ 0,75 · MOS ≥ 3,5 |

*Các ngưỡng là đề xuất, chưa đo; phải chốt lại sau baseline.*

## 9. Rủi ro

- **License**: ND/NC/research-only; không dùng thương mại khi chưa rõ.
- **Chất lượng dữ liệu**: ViMD spontaneous/noisy; VIVOS ít giờ/giọng; PhoAudiobook audiobook.
- **Speaker leakage/identity/deepfake**: watermark, consent, kiểm soát.
- **Catastrophic forgetting** khi fine-tune đa nhiệm.
- **CPU/ONNX**: speaker/style encoder tăng latency; 48 kHz tăng chi phí.
- **Determinism**: style diffusion/sampling khó tái lập; ưu tiên embedding/label.
- **Đánh giá chủ quan**: MOS/ABX cần người nghe; ASR chỉ là proxy.

## 10. Tài liệu tham khảo

- VieNeu-TTS — https://github.com/pnnbao97/VieNeu-TTS
- V-TTS (valtec) — https://github.com/tronghieuit/valtec-tts
- VietTTS — https://huggingface.co/dangvansam/viet-tts
- F5-TTS-Vi — https://huggingface.co/hynt/F5-TTS-Vietnamese-ViVoice
- PhoAudiobook / Zero-shot TTS for Vietnamese — https://arxiv.org/abs/2506.01322
- ViMD — https://aclanthology.org/2024.emnlp-main.426 · https://huggingface.co/datasets/nguyendv02/ViMD_Dataset
- VIVOS — https://huggingface.co/datasets/AILAB-VNUHCM/vivos
- VLSP 2022 TTS emotion — https://vlsp.org.vn/vlsp2022/eval/tts
- VieNeu-TTS-1000h — https://huggingface.co/datasets/pnnbao-ump/VieNeu-TTS-1000h
- sea-g2p — https://github.com/pnnbao97/sea-g2p
- Bilingual phoneme set Vi–En — https://arxiv.org/abs/2508.19270
- TSPC — https://arxiv.org/abs/2509.05983
- ViMedCSS — https://aclanthology.org/2026.lrec-1.445.pdf
- StyleTTS2 — https://github.com/yl4579/StyleTTS2
- IndexTTS2 — https://ojs.aaai.org/index.php/AAAI/article/view/40820
- ECE-TTS — https://www.mdpi.com/2076-3417/15/9/5108
- WeSCon — https://neurips.cc/virtual/2025/poster/117924
- TED-TTS — https://aclanthology.org/2026.acl-long.1077.pdf
- ECAPA/x-vector cho multi-speaker TTS — https://arxiv.org/abs/2506.20190

## 11. Ghi chú

- Số liệu model/dataset lấy từ README/paper tại thời điểm 30/10/2026; **chưa tự đo** trên M6.
- Trước khi dùng dataset: kiểm tra license trên trang gốc; đặc biệt ViMD (ND) và các bộ
  research-only.
- Trước khi triển khai: theo quy ước repo, đo baseline + cổng, không nâng cấp trước khi có
  thước đo (AGENTS.md §1).
