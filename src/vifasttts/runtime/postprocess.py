"""Hậu xử lý waveform thuần numpy (fade, chuẩn hoá đỉnh).

Dùng chung cho cả đường PyTorch (`infer.py`) và runtime ONNX (`runtime/`).
"""

from __future__ import annotations

import numpy as np


def peak_normalize(wav: np.ndarray, target_db: float = -3.0) -> np.ndarray:
    """Chuẩn hoá đỉnh về `target_db` (dBFS). Im lặng → giữ nguyên."""
    array = np.asarray(wav, dtype=np.float32)
    peak = float(np.max(np.abs(array))) if array.size else 0.0
    if peak <= 1e-8:
        return array
    target = float(10.0 ** (target_db / 20.0))
    return (array * (target / peak)).astype(np.float32)


def fade(wav: np.ndarray, sample_rate: int, fade_in_ms: float = 10.0, fade_out_ms: float = 20.0) -> np.ndarray:
    """Fade tuyến tính đầu/cuối để tránh tiếng "cụp" khi phát."""
    array = np.asarray(wav, dtype=np.float32).copy()
    length = array.size
    if length == 0:
        return array
    fade_in = min(length, max(0, int(sample_rate * fade_in_ms / 1000.0)))
    fade_out = min(length, max(0, int(sample_rate * fade_out_ms / 1000.0)))
    if fade_in > 1:
        array[:fade_in] *= np.linspace(0.0, 1.0, fade_in, dtype=np.float32)
    if fade_out > 1:
        array[-fade_out:] *= np.linspace(1.0, 0.0, fade_out, dtype=np.float32)
    return array


def postprocess(wav: np.ndarray, sample_rate: int, *, target_db: float | None = None) -> np.ndarray:
    """Fade mặc định; chuẩn hoá đỉnh nếu `target_db` được đặt."""
    output = fade(wav, sample_rate)
    if target_db is not None:
        output = peak_normalize(output, target_db)
    return output


def sharpen_mel_numpy(mel, alpha: float = 1.5):
    """Bản numpy của `sharpen_mel` (unsharp 3×3, zero-pad, chia 9) cho runtime ONNX.

    Không cần torch; nhận `[T,F]` hoặc `[B,T,F]`, giữ shape.
    """
    if not alpha:
        return mel
    x = np.asarray(mel, dtype=np.float32)
    if x.ndim == 2:
        padded = np.pad(x, ((1, 1), (1, 1)), mode="constant")
        blur = sum(
            padded[1 + di:1 + di + x.shape[0], 1 + dj:1 + dj + x.shape[1]]
            for di in (-1, 0, 1) for dj in (-1, 0, 1)
        ) / 9.0
    elif x.ndim == 3:
        padded = np.pad(x, ((0, 0), (1, 1), (1, 1)), mode="constant")
        blur = sum(
            padded[:, 1 + di:1 + di + x.shape[1], 1 + dj:1 + dj + x.shape[2]]
            for di in (-1, 0, 1) for dj in (-1, 0, 1)
        ) / 9.0
    else:
        raise ValueError("sharpen_mel_numpy chỉ nhận [T,F] hoặc [B,T,F]")
    return (x + np.float32(alpha) * (x - blur)).astype(np.float32)


def sharpen_mel(mel, alpha: float = 1.5):
    """Làm nét mel trong không gian z (unsharp 3×3 box-blur) — bản "sh25" chính thức của repo.

    Lịch sử: bản sh25 đầu tiên (13/10) chỉ là script demo **không lưu vào repo** ⇒ mất code ✗.
    Hàm này là bản tương đương được promote vào `src/` (V11, 14/10) để không tái diễn.
    `alpha=1,5` = mức người dùng đã chọn ("sh25 toàn cục"); **alpha=0 ⇒ không đổi**.
    ⚠ §38.2: tăng alpha mạnh hơn mức này **khuếch đại rè** ở ngã/nặng — đừng tăng tuỳ tiện.
    """
    import torch

    if not alpha:
        return mel
    x = mel.unsqueeze(0).unsqueeze(0)                       # [1,1,T,F]
    blur = torch.nn.functional.avg_pool2d(x, 3, stride=1, padding=1)
    return (x + float(alpha) * (x - blur)).squeeze(0).squeeze(0)
