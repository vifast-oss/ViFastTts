"""Engine ONNX cấp cao cho Python: text → audio / stream + phụ đề.

Mục đích: app web, CLI, notebook và service Python khác dùng cùng một API thay
vì mỗi nơi tự chunk, tự tính timing slot và tự ghép WAV/SRT/VTT.

Ví dụ:

    from vifasttts.runtime.tts_engine import OnnxTtsEngine, TtsSettings
    engine = OnnxTtsEngine.from_paths("acoustic.onnx", "vocoder.onnx")
    result = engine.synthesize("Xin chào", TtsSettings())
    for chunk in engine.iter_chunks("Xin chào", TtsSettings()):
        ...  # chunk.samples float32, chunk.units timing tuyệt đối

Engine nhận object `OnnxAcousticModel`/`OnnxVocoder` đã nạp để web không phải
mở session ONNX lại cho mỗi request.
"""

from __future__ import annotations

import io
import time
import wave
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np

from vifasttts.frontend.chunking import (
    chunk_text,
    pause_seconds,
    split_clauses,
    steady_pause_seconds,
)
from vifasttts.frontend.normalizer import NormalizerOptions
from vifasttts.frontend.pipeline import parse_text
from vifasttts.runtime.onnx_engine import OnnxAcousticModel, OnnxVocoder
from vifasttts.runtime.postprocess import postprocess, sharpen_mel_numpy

DIALECTS = ("north", "central", "south")


@dataclass(frozen=True)
class TtsSettings:
    """Tham số tổng hợp; `normalized()` kẹp về miền an toàn giống Rust/HTTP."""

    speed: float = 1.0
    alpha: float = 1.5
    max_chars: int = 300
    fixed_pauses: bool = False
    peak_normalize: bool = False
    dialect: str = "north"
    resolve_oov: bool = True

    def normalized(self) -> TtsSettings:
        dialect = self.dialect if self.dialect in DIALECTS else "north"
        return TtsSettings(
            speed=min(2.0, max(0.5, float(self.speed))),
            alpha=min(3.0, max(0.5, float(self.alpha))),
            max_chars=max(50, min(5000, int(self.max_chars or 300))),
            fixed_pauses=bool(self.fixed_pauses),
            peak_normalize=bool(self.peak_normalize),
            dialect=dialect,
            resolve_oov=bool(self.resolve_oov),
        )


@dataclass
class StreamChunk:
    """Một chunk audio đã render; `units` có timing tuyệt đối theo samples."""

    samples: np.ndarray
    sample_rate: int
    units: list[dict] = field(default_factory=list)
    pause: bool = False


@dataclass
class SynthesisResult:
    """Kết quả đầy đủ cho API full (WAV + units + thời gian xử lý)."""

    wav: bytes
    sample_rate: int
    units: list[dict]
    elapsed: float
    audio_seconds: float


def wav_bytes(samples: np.ndarray, sample_rate: int) -> bytes:
    """Float32 mono → WAV PCM16 (44-byte header, giống runtime Rust)."""
    pcm = (np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0) * 32767.0).round().astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())
    return buffer.getvalue()


def pcm16(samples: np.ndarray) -> bytes:
    """Float32 → PCM16 little-endian mono (dùng cho NDJSON stream)."""
    return (
        np.clip(np.asarray(samples, dtype=np.float32), -1.0, 1.0) * 32767.0
    ).round().astype("<i2").tobytes()


def _time(ms: int, vtt: bool = False) -> str:
    ms = max(0, int(ms))
    hours, rest = divmod(ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, millis = divmod(rest, 1000)
    separator = "." if vtt else ","
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{millis:03d}"


def karaoke_lines(units: list[dict], max_chars: int = 80) -> list[list[dict]]:
    """Nhóm unit thành dòng phụ đề; ưu tiên sentence_end rồi giới hạn ký tự."""
    lines: list[list[dict]] = []
    current: list[dict] = []
    for unit in units:
        current.append(unit)
        length = sum(len(str(item.get("text", ""))) + 1 for item in current)
        if unit.get("sentence_end") or length >= max_chars:
            lines.append(current)
            current = []
    if current:
        lines.append(current)
    return lines


def srt_from_units(units: list[dict]) -> str:
    """TimedUnit → SRT; rỗng nếu chưa có timing."""
    blocks: list[str] = []
    for index, line in enumerate(karaoke_lines(units), start=1):
        start, end = line[0]["start_ms"], line[-1]["end_ms"]
        text = " ".join(
            str(item.get("text", "")) + str(item.get("punctuation") or "")
            for item in line
        )
        blocks.append(f"{index}\n{_time(start)} --> {_time(end)}\n{text}")
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def vtt_from_units(units: list[dict]) -> str:
    """TimedUnit → WebVTT karaoke."""
    lines = ["WEBVTT", ""]
    for line in karaoke_lines(units):
        start, end = line[0]["start_ms"], line[-1]["end_ms"]
        lines.append(f"{_time(start, vtt=True)} --> {_time(end, vtt=True)}")
        for item in line:
            lines.append(
                f"<{_time(item['start_ms'], vtt=True)}>{item.get('text', '')}"
                f"{item.get('punctuation') or ''}"
            )
        lines.append("")
    return "\n".join(lines)


class OnnxTtsEngine:
    """Bọc acoustic + vocoder đã nạp; dùng chung cho full và stream."""

    def __init__(self, acoustic: OnnxAcousticModel, vocoder: OnnxVocoder) -> None:
        self.acoustic = acoustic
        self.vocoder = vocoder
        self.sample_rate = int(
            getattr(vocoder, "sample_rate", 0)
            or int(acoustic.metadata.get("sample_rate", 24000))
        )

    @classmethod
    def from_paths(
        cls,
        acoustic_path: str | Path,
        vocoder_path: str | Path,
        *,
        provider: str = "cpu",
    ) -> OnnxTtsEngine:
        """Nạp session một lần từ đường dẫn ONNX."""
        return cls(
            OnnxAcousticModel(acoustic_path, provider=provider),
            OnnxVocoder(vocoder_path, provider=provider),
        )

    def iter_chunks(
        self,
        text: str,
        settings: TtsSettings | None = None,
        *,
        normalizer: NormalizerOptions | None = None,
    ) -> Iterator[StreamChunk]:
        """Render từng đoạn; không gom toàn bộ audio.

        `normalizer` nên được caller dựng từ cùng dictionary/overrides với full
        để timing và cách đọc không lệch. `peak_normalize` không hỗ trợ stream
        (cần biết đỉnh toàn file) — dùng `synthesize`.
        """
        settings = (settings or TtsSettings()).normalized()
        if settings.peak_normalize:
            raise ValueError("peak_normalize chưa hỗ trợ streaming")
        normalizer = normalizer or NormalizerOptions(dialect=settings.dialect)
        chunks = (
            split_clauses(text, max_chars=settings.max_chars)
            if settings.fixed_pauses
            else chunk_text(text, max_chars=settings.max_chars)
        )
        if not chunks:
            raise ValueError("Không có nội dung để đọc")
        hop = int(getattr(self.vocoder, "hop_length", 256) or 256)
        sample_offset = 0
        for index, chunk in enumerate(chunks):
            items = parse_text(
                chunk,
                dialect=settings.dialect,
                options=normalizer,
                resolve_oov=settings.resolve_oov,
            )
            features = self.acoustic.features_from_text(
                chunk,
                dialect=settings.dialect,
                options=normalizer,
                resolve_oov=settings.resolve_oov,
            )
            outputs = self.acoustic.run(
                features,
                speed=settings.speed,
                gate_threshold=1.01 if settings.fixed_pauses else 0.5,
            )
            mel = sharpen_mel_numpy(np.asarray(outputs["mel"], dtype=np.float32), settings.alpha)
            piece = np.asarray(self.vocoder.waveform(mel), dtype=np.float32)
            units = self._units(
                items, outputs.get("slot_durations"), sample_offset, hop, settings.dialect
            )
            if piece.size:
                yield StreamChunk(piece, self.sample_rate, units)
            sample_offset += int(piece.size)
            if index < len(chunks) - 1:
                seconds = (
                    steady_pause_seconds(chunk)
                    if settings.fixed_pauses
                    else pause_seconds(chunk)
                )
                pause = int(self.sample_rate * seconds)
                if pause:
                    yield StreamChunk(
                        np.zeros(pause, dtype=np.float32),
                        self.sample_rate,
                        pause=True,
                    )
                    sample_offset += pause

    def _units(
        self,
        items: list,
        slots,
        sample_offset: int,
        hop: int,
        dialect: str,
    ) -> list[dict]:
        """Timing tuyệt đối từ slot_durations; bỏ qua nếu model không xuất timing."""
        if slots is None or not items:
            return []
        values = [max(0, int(value)) for value in np.asarray(slots).reshape(-1).tolist()]
        if len(values) != 1 + 5 * len(items):
            return []
        cursor = values[0]
        units: list[dict] = []
        for item_index, item in enumerate(items):
            base = 1 + 5 * item_index
            voiced = sum(values[base:base + 4])
            start_ms = (
                sample_offset * 1000 // self.sample_rate
                + cursor * hop * 1000 // self.sample_rate
            )
            end_ms = start_ms + voiced * hop * 1000 // self.sample_rate
            cursor += voiced + values[base + 4]
            units.append({
                "text": item.raw or item.normalized,
                "start_ms": start_ms,
                "end_ms": max(start_ms + 1, end_ms),
                "kind": "syllable",
                "punctuation": item.punctuation,
                "sentence_end": bool(item.boundaries.sentence_end),
                "phrase_end": bool(item.boundaries.phrase_end),
            })
        return units

    def synthesize(
        self,
        text: str,
        settings: TtsSettings | None = None,
        *,
        normalizer: NormalizerOptions | None = None,
    ) -> SynthesisResult:
        """Tổng hợp đầy đủ; áp fade/peak normalize trên toàn waveform."""
        settings = (settings or TtsSettings()).normalized()
        started = time.perf_counter()
        pieces: list[np.ndarray] = []
        units: list[dict] = []
        # Stream không peak-normalize; full áp postprocess sau khi ghép toàn file.
        chunk_settings = replace(settings, peak_normalize=False)
        for chunk in self.iter_chunks(text, chunk_settings, normalizer=normalizer):
            if chunk.samples.size:
                pieces.append(chunk.samples)
            units.extend(chunk.units)
        if not pieces:
            raise ValueError("Không có nội dung để đọc")
        waveform = np.concatenate(pieces)
        waveform = postprocess(
            waveform,
            self.sample_rate,
            target_db=-3.0 if settings.peak_normalize else None,
        )
        return SynthesisResult(
            wav=wav_bytes(waveform, self.sample_rate),
            sample_rate=self.sample_rate,
            units=units,
            elapsed=time.perf_counter() - started,
            audio_seconds=float(waveform.size) / self.sample_rate,
        )
