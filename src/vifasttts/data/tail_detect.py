"""Bộ dò tiếng nói ở đuôi segment (V1852.A1).

Vùng đuôi = từ mốc kết thúc âm tiết cuối (MFA) đến hết segment.
Dương khi: hữu thanh trong đuôi ≥ 0,12 s VÀ đỉnh RMS 50 ms ≥ −15 dB so với trung vị
RMS các frame hữu thanh của chính segment.
"""

from __future__ import annotations

import numpy as np


def tail_start_frame(lead: int, durations: list[int], gaps: list[int]) -> int:
    """Frame bắt đầu vùng đuôi (kết thúc âm tiết cuối)."""
    return int(lead) + sum(int(x) for x in durations) + sum(int(x) for x in gaps[:-1])


def frame_rms_db(wave: np.ndarray, sr: int, hop: int = 256,
                 window_ms: float = 50.0) -> np.ndarray:
    """RMS dB theo cửa sổ ~50 ms, bước hop."""
    width = max(int(sr * window_ms / 1000.0), hop)
    if wave.size < width:
        return np.zeros(0, dtype=np.float64)
    frames = np.lib.stride_tricks.sliding_window_view(wave, width)[::hop]
    rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1) + 1e-12)
    return 20.0 * np.log10(rms + 1e-12)


def voiced_flags(wave: np.ndarray, sr: int, hop: int = 256) -> np.ndarray:
    """F0 > 0 bằng pyworld harvest + stonemask (cùng extractor repo)."""
    import pyworld as pw

    x = np.asarray(wave, dtype=np.float64)
    f0, temporal = pw.harvest(x, sr, frame_period=1000.0 * hop / sr)
    f0 = pw.stonemask(x, f0, temporal, sr)
    return f0 > 0


def measure_tail(wave: np.ndarray, sr: int, tail_start: int, hop: int = 256,
                 min_voiced_s: float = 0.12, min_gain_db: float = -15.0) -> dict:
    """Đo vùng đuôi; trả dict + `positive` theo luật cố định."""
    wave = np.asarray(wave, dtype=np.float32).reshape(-1)
    tail_start = max(0, min(int(tail_start), wave.size))
    tail = wave[tail_start:]
    full_voiced = voiced_flags(wave, sr, hop)
    rms = frame_rms_db(wave, sr, hop)
    n = min(rms.size, full_voiced.size)
    voiced_rms = rms[:n][full_voiced[:n]]
    median_voiced = float(np.median(voiced_rms)) if voiced_rms.size else float("nan")
    tail_voiced = full_voiced[min(len(full_voiced), tail_start // hop):]
    voiced_s = float(tail_voiced.sum()) * hop / sr
    tail_rms = rms[min(rms.size, tail_start // hop):]
    peak = float(np.max(tail_rms)) if tail_rms.size else float("nan")
    gain = peak - median_voiced if np.isfinite(peak) and np.isfinite(median_voiced) else float("nan")
    return {
        "tail_seconds": round(tail.size / sr, 4),
        "tail_voiced_seconds": round(voiced_s, 4),
        "tail_peak_rms_db": round(peak, 3) if np.isfinite(peak) else None,
        "median_voiced_rms_db": round(median_voiced, 3) if np.isfinite(median_voiced) else None,
        "gain_db": round(gain, 3) if np.isfinite(gain) else None,
        "positive": bool(voiced_s >= min_voiced_s and np.isfinite(gain) and gain >= min_gain_db),
    }
