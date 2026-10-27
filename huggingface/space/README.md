---
title: ViFastTTS Ngọc Huyền small
emoji: 🎙️
colorFrom: teal
colorTo: green
sdk: gradio
sdk_version: 5.50.0
app_file: app.py
pinned: false
license: cc-by-nc-4.0
---

# ViFastTTS · Ngọc Huyền small

Demo nghe thử model TTS tiếng Việt **small 6,1M acoustic**, 24 kHz, ONNX CPU.

- **Research / phi thương mại**. Dataset `pnnbao-ump/ngochuyen_voice` là CC BY-NC 4.0.
- Không dùng để giả giọng, lừa đảo hoặc production thương mại.
- Mặc định alpha 1.5, Vocos pretrained, model tự ngắt nghỉ; nghỉ cố định mặc định tắt.
- Free CPU Space có thể sleep khi không dùng; lần đầu có thể chậm do tải model/khởi động.

Code: https://github.com/dvchd/ViFastTts
Model: https://huggingface.co/dvchd/vifasttts-ngochuyen-small
Demo VPS: https://vifasttts.hoctuthien.com/
