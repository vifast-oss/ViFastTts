---
title: ViFastTts Ngọc Huyền small
emoji: 🎙️
colorFrom: red
colorTo: yellow
sdk: gradio
sdk_version: 5.50.0
app_file: app.py
pinned: false
license: cc-by-nc-4.0
---

![ViFastTts](https://huggingface.co/dvchd/vifasttts-ngochuyen-small/resolve/main/assets/vifasttts-lockup-cream.png)

# ViFastTts · Ngọc Huyền small

Demo nghe thử model TTS tiếng Việt **small 6,1M acoustic**, 24 kHz, ONNX CPU.

- **Research / phi thương mại**. Dataset `pnnbao-ump/ngochuyen_voice` là CC BY-NC 4.0.
- Không dùng để giả giọng, lừa đảo hoặc production thương mại.
- Mặc định alpha 1.5, Vocos pretrained, model tự ngắt nghỉ; nghỉ cố định mặc định tắt.
- ONNX đang dùng là **N0 Q-init** (`vocab_version` + `vocab_hash`); Q = K cho giọng Bắc.
- Free CPU Space có thể sleep khi không dùng; lần đầu có thể chậm do tải model/khởi động.

Code: https://github.com/dvchd/ViFastTts
Model: https://huggingface.co/dvchd/vifasttts-ngochuyen-small
Demo VPS: https://vifasttts.hoctuthien.com/
