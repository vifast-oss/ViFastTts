"""Hugging Face Space cho N0 — ONNX CPU, research/non-commercial."""

from __future__ import annotations

import os

import gradio as gr
import numpy as np
from huggingface_hub import hf_hub_download

from vifasttts.frontend.chunking import (
    chunk_text,
    pause_seconds,
    split_clauses,
    steady_pause_seconds,
)
from vifasttts.frontend.normalizer import NormalizerOptions
from vifasttts.runtime.onnx_engine import OnnxAcousticModel, OnnxVocoder
from vifasttts.runtime.postprocess import postprocess, sharpen_mel_numpy

MODEL_REPO = os.environ.get("MODEL_REPO", "dvchd/vifasttts-ngochuyen-small")
MAX_CHARS = 3000
CHUNK_CHARS = 300
ALPHA = 1.5

acoustic = OnnxAcousticModel(
    hf_hub_download(MODEL_REPO, "onnx/acoustic.onnx"), provider="cpu"
)
vocoder = OnnxVocoder(
    hf_hub_download(MODEL_REPO, "onnx/vocoder.onnx"), provider="cpu"
)
SAMPLE_RATE = vocoder.sample_rate or int(acoustic.metadata.get("sample_rate", 24000))


def synthesize(text: str, speed: float, fixed_pauses: bool):
    text = " ".join(str(text or "").replace("\x00", " ").split()).strip()
    if not text:
        raise gr.Error("Nhập câu cần đọc trước.")
    if len(text) > MAX_CHARS:
        raise gr.Error(f"Tối đa {MAX_CHARS} ký tự.")
    if not any(ch.isalpha() for ch in text):
        raise gr.Error("Cần ít nhất một chữ cái.")
    speed = min(1.15, max(0.85, float(speed)))
    options = NormalizerOptions(dialect="north")
    chunks = (split_clauses(text, max_chars=CHUNK_CHARS) if fixed_pauses
              else chunk_text(text, max_chars=CHUNK_CHARS))
    pieces: list[np.ndarray] = []
    for index, chunk in enumerate(chunks):
        features = acoustic.features_from_text(chunk, options=options)
        outputs = acoustic.run(features, speed=speed, gate_threshold=1.01 if fixed_pauses else 0.5)
        mel = sharpen_mel_numpy(np.asarray(outputs["mel"], dtype=np.float32), ALPHA)
        pieces.append(np.asarray(vocoder.waveform(mel), dtype=np.float32))
        if index < len(chunks) - 1:
            seconds = (steady_pause_seconds(chunk) if fixed_pauses else pause_seconds(chunk))
            pause = int(SAMPLE_RATE * seconds)
            if pause:
                pieces.append(np.zeros(pause, dtype=np.float32))
    return SAMPLE_RATE, postprocess(np.concatenate(pieces), SAMPLE_RATE)


with gr.Blocks(title="ViFastTts · Ngọc Huyền small") as demo:
    gr.Markdown(
        "![ViFastTts](https://huggingface.co/dvchd/vifasttts-ngochuyen-small/resolve/main/assets/vifasttts-lockup-cream.png)\n\n"
        "# ViFastTts · Ngọc Huyền small\n"
        "**Research demo, phi thương mại.** Model acoustic 6,1M, ONNX CPU, 24 kHz. "
        "Mặc định để model tự ngắt nghỉ; nghỉ cố định là tuỳ chọn và đang tắt."
    )
    with gr.Row():
        with gr.Column(scale=3):
            text = gr.Textbox(
                label="Câu cần đọc",
                placeholder="Sáng nay trời đẹp, chúng ta cùng đi dạo nhé.",
                lines=5,
                max_lines=8,
            )
            with gr.Row():
                speed = gr.Slider(0.85, 1.15, value=1.0, step=0.05, label="Tốc độ")
                fixed = gr.Checkbox(value=False, label="Nghỉ cố định (mặc định tắt)")
            button = gr.Button("Tạo âm thanh", variant="primary")
            audio = gr.Audio(label="Kết quả", type="numpy", autoplay=False)
        with gr.Column(scale=2):
            gr.Markdown(
                "### Mặc định\n"
                "- Alpha 1,5\n"
                "- Vocos pretrained\n"
                "- Model tự nghỉ\n"
                "- 3000 ký tự\n\n"
                "**Không dùng để giả giọng, lừa đảo hoặc thương mại.** "
                "Dataset gốc CC BY-NC 4.0; code MIT."
            )
    examples = gr.Examples(
        examples=[
            ["Sáng nay trời đẹp, chúng ta cùng đi dạo quanh hồ nhé."],
            ["Cô giáo nhẹ nhàng nhắc học sinh kiểm tra lại bài tập trước khi vào tiết mới."],
            ["Chiếc tàu rời bến từ sớm, mang theo những giỏ cá tươi vừa được đánh bắt ngoài khơi."],
        ],
        inputs=[text],
    )
    button.click(synthesize, inputs=[text, speed, fixed], outputs=[audio])
    text.submit(synthesize, inputs=[text, speed, fixed], outputs=[audio])

if __name__ == "__main__":
    demo.queue(default_concurrency_limit=1).launch()
