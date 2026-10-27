"""Demo web ONNX cho N0 — research/non-commercial.

Chạy trong Docker; không cần torch. Mặc định model tự nghỉ, alpha 1.5, Vocos pretrained.
"""

from __future__ import annotations

import io
import logging
import os
import threading
import time
import wave
from collections import defaultdict, deque
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from vifasttts.frontend.chunking import (
    chunk_text,
    pause_seconds,
    split_clauses,
    steady_pause_seconds,
)
from vifasttts.frontend.normalizer import NormalizerOptions
from vifasttts.runtime.onnx_engine import OnnxAcousticModel, OnnxVocoder
from vifasttts.runtime.postprocess import postprocess, sharpen_mel_numpy

ROOT = Path(__file__).resolve().parent
MODEL_DIR = Path(os.environ.get("MODEL_DIR", ROOT / "models"))
ACOUSTIC = MODEL_DIR / "acoustic.onnx"
VOCODER = MODEL_DIR / "vocoder.onnx"
MAX_CHARS = 300
RATE_LIMIT = 6
RATE_WINDOW = 60.0
ALPHA = float(os.environ.get("VIFASTT_SHARPEN_ALPHA", "1.5"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("vifasttts-demo")

app = FastAPI(title="ViFastTTS research demo", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://huggingface.co"],
    allow_origin_regex=r"https://.*\.hf\.space",
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
_lock = threading.Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)

if not ACOUSTIC.exists() or not VOCODER.exists():
    raise RuntimeError(f"Thiếu ONNX: {ACOUSTIC} / {VOCODER}")

acoustic = OnnxAcousticModel(ACOUSTIC, provider="cpu")
vocoder = OnnxVocoder(VOCODER, provider="cpu")
SAMPLE_RATE = vocoder.sample_rate or int(acoustic.metadata.get("sample_rate", 24000))


class TtsRequest(BaseModel):
    text: str
    speed: float = 1.0
    fixed_pauses: bool = False


def _wav_bytes(waveform: np.ndarray, sample_rate: int) -> bytes:
    pcm = (np.clip(np.asarray(waveform, dtype=np.float32), -1.0, 1.0) * 32767.0).round().astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    return buffer.getvalue()


def _rate_ok(client: str) -> bool:
    now = time.monotonic()
    bucket = _hits[client]
    while bucket and now - bucket[0] > RATE_WINDOW:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT:
        return False
    bucket.append(now)
    return True


def _synthesize(text: str, speed: float, fixed_pauses: bool) -> tuple[bytes, float]:
    started = time.perf_counter()
    options = NormalizerOptions(dialect="north")
    chunks = (split_clauses(text, max_chars=MAX_CHARS) if fixed_pauses
              else chunk_text(text, max_chars=MAX_CHARS))
    if not chunks:
        raise HTTPException(status_code=422, detail="Không có nội dung để đọc")
    pieces: list[np.ndarray] = []
    for index, chunk in enumerate(chunks):
        features = acoustic.features_from_text(chunk, options=options)
        outputs = acoustic.run(features, speed=speed, gate_threshold=1.01 if fixed_pauses else 0.5)
        mel = np.asarray(outputs["mel"], dtype=np.float32)
        mel = sharpen_mel_numpy(mel, ALPHA)
        pieces.append(np.asarray(vocoder.waveform(mel), dtype=np.float32))
        if index < len(chunks) - 1:
            seconds = (steady_pause_seconds(chunk) if fixed_pauses else pause_seconds(chunk))
            pause = int(SAMPLE_RATE * seconds)
            if pause:
                pieces.append(np.zeros(pause, dtype=np.float32))
    waveform = postprocess(np.concatenate(pieces), SAMPLE_RATE)
    return _wav_bytes(waveform, SAMPLE_RATE), time.perf_counter() - started


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (ROOT / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "sample_rate": SAMPLE_RATE, "arch": acoustic.metadata.get("arch", "?"),
            "alpha": ALPHA, "pause": "model"}


@app.post("/api/tts")
def tts(payload: TtsRequest, request: Request) -> Response:
    text = " ".join(str(payload.text).replace("\x00", " ").split()).strip()
    if not text:
        raise HTTPException(status_code=422, detail="Nhập câu cần đọc")
    if len(text) > MAX_CHARS:
        raise HTTPException(status_code=422, detail=f"Tối đa {MAX_CHARS} ký tự")
    if not any(char.isalpha() for char in text):
        raise HTTPException(status_code=422, detail="Cần ít nhất một chữ cái")
    speed = min(1.2, max(0.8, float(payload.speed)))
    forwarded = request.headers.get("x-forwarded-for", "")
    client = forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
    if not _rate_ok(client):
        raise HTTPException(status_code=429, detail="Quá nhiều yêu cầu; thử lại sau 1 phút")
    if not _lock.acquire(timeout=45):
        raise HTTPException(status_code=503, detail="Máy đang bận; thử lại sau")
    try:
        audio, elapsed = _synthesize(text, speed, bool(payload.fixed_pauses))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("synthesis failed")
        raise HTTPException(status_code=500, detail="Lỗi tổng hợp; thử câu khác") from exc
    finally:
        _lock.release()
    logger.info("tts ok %.2fs chars=%d fixed=%s", elapsed, len(text), payload.fixed_pauses)
    return Response(content=audio, media_type="audio/wav", headers={
        "Content-Disposition": 'inline; filename="vifasttts-demo.wav"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    })
