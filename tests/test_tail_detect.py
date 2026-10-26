"""Unit test bộ dò đuôi V1852.A1."""

from __future__ import annotations

import numpy as np

from vifasttts.data.tail_detect import measure_tail, tail_start_frame

SR = 24000
HOP = 256


def _voice(seconds: float) -> np.ndarray:
    t = np.arange(int(seconds * SR)) / SR
    signal = sum((0.2 / k) * np.sin(2 * np.pi * 150 * k * t) for k in range(1, 8))
    return signal.astype(np.float32)


def _speech_then_tail(tail_speech: bool) -> np.ndarray:
    speech = _voice(1.5)
    tail = np.zeros(int(0.5 * SR), dtype=np.float32)
    if tail_speech:
        voiced = _voice(0.3)
        tail[: voiced.size] = voiced
    return np.concatenate([speech, tail])


def test_tail_start_frame() -> None:
    assert tail_start_frame(0, [10, 20], [3, 100]) == 33


def test_silent_tail_is_negative() -> None:
    wave = _speech_then_tail(False)
    result = measure_tail(wave, SR, int(1.5 * SR), HOP)
    assert result["positive"] is False
    assert result["tail_voiced_seconds"] < 0.12


def test_speech_in_tail_is_positive() -> None:
    wave = _speech_then_tail(True)
    result = measure_tail(wave, SR, int(1.5 * SR), HOP)
    assert result["positive"] is True
    assert result["tail_voiced_seconds"] >= 0.12
