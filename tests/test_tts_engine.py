"""Test engine Python dùng chung: stream/full không cần ONNX thật."""

from __future__ import annotations

from typing import ClassVar

import numpy as np
import pytest

from vifasttts.runtime.tts_engine import (
    OnnxTtsEngine,
    TtsSettings,
    pcm16,
    srt_from_units,
    vtt_from_units,
)


class FakeAcoustic:
    metadata: ClassVar[dict[str, str]] = {"sample_rate": "24000"}

    def features_from_text(self, text, *, dialect, options, resolve_oov=True):
        assert dialect == "north"
        assert resolve_oov is True
        return np.zeros((1, 1, 7), dtype=np.int64)

    def run(self, features, *, speed=1.0, gate_threshold=0.5):
        # "Chào bạn" → 2 item; 1 + 5*2 slot như model v2.
        return {
            "mel": np.zeros((1, 2, 100), dtype=np.float32),
            "slot_durations": np.array(
                [[0, 4, 0, 0, 0, 1, 4, 0, 0, 0, 1]], dtype=np.int64
            ),
        }


class FakeVocoder:
    sample_rate = 24000
    hop_length = 256

    def waveform(self, mel):
        return np.zeros(int(mel.shape[1]) * self.hop_length, dtype=np.float32)


def engine() -> OnnxTtsEngine:
    return OnnxTtsEngine(FakeAcoustic(), FakeVocoder())


def test_settings_are_clamped() -> None:
    settings = TtsSettings(speed=9, alpha=9, max_chars=0, dialect="bad").normalized()
    assert settings.speed == 2.0
    assert settings.alpha == 3.0
    assert settings.max_chars == 300
    assert settings.dialect == "north"


def test_stream_chunks_have_absolute_units() -> None:
    chunks = list(engine().iter_chunks("Chào bạn", TtsSettings()))
    assert len(chunks) == 1
    assert chunks[0].sample_rate == 24000
    assert len(chunks[0].units) == 2
    assert chunks[0].units[0]["start_ms"] == 0
    assert chunks[0].units[1]["start_ms"] > chunks[0].units[0]["start_ms"]


def test_full_synthesis_returns_wav_and_units() -> None:
    result = engine().synthesize("Chào bạn", TtsSettings())
    assert result.wav[:4] == b"RIFF"
    assert result.wav[8:12] == b"WAVE"
    assert result.sample_rate == 24000
    assert len(result.units) == 2
    assert result.audio_seconds > 0


def test_full_peak_normalize_is_supported() -> None:
    result = engine().synthesize("Chào bạn", TtsSettings(peak_normalize=True))
    assert result.wav[:4] == b"RIFF"


def test_stream_rejects_peak_normalize() -> None:
    with pytest.raises(ValueError, match="peak_normalize"):
        list(engine().iter_chunks("Chào bạn", TtsSettings(peak_normalize=True)))


def test_pcm16_and_subtitles() -> None:
    assert len(pcm16(np.array([0.0, 1.0, -1.0], dtype=np.float32))) == 6
    units = [
        {"text": "Chào", "start_ms": 0, "end_ms": 100, "sentence_end": False, "punctuation": ""},
        {"text": "bạn", "start_ms": 100, "end_ms": 220, "sentence_end": True, "punctuation": "."},
    ]
    srt = srt_from_units(units)
    vtt = vtt_from_units(units)
    assert "00:00:00,000 --> 00:00:00,220" in srt
    assert "Chào bạn." in srt
    assert vtt.startswith("WEBVTT")
    assert "00:00:00.100" in vtt
