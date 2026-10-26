"""Test postprocess: fade và chuẩn hoá đỉnh."""
from __future__ import annotations

import numpy as np

from vifasttts.runtime.postprocess import fade, peak_normalize, postprocess


def test_peak_normalize_hits_target():
    wav = np.array([0.1, -0.2, 0.05], dtype=np.float32)
    out = peak_normalize(wav, target_db=-6.0)
    target = 10 ** (-6.0 / 20.0)
    assert abs(float(np.max(np.abs(out))) - target) < 1e-6


def test_peak_normalize_silence_unchanged():
    wav = np.zeros(10, dtype=np.float32)
    out = peak_normalize(wav)
    assert np.allclose(out, wav)


def test_fade_ends_at_zero():
    wav = np.ones(1000, dtype=np.float32)
    out = fade(wav, sample_rate=1000, fade_in_ms=10.0, fade_out_ms=20.0)
    assert out[0] == 0.0 and out[-1] == 0.0
    assert np.allclose(out[100:900], 1.0)  # vùng giữa không đổi


def test_postprocess_combo():
    wav = np.ones(2000, dtype=np.float32) * 0.8
    out = postprocess(wav, 1000, target_db=-3.0)
    assert out[0] == 0.0 and out[-1] == 0.0
    target = 10 ** (-3.0 / 20.0)
    assert abs(float(np.max(np.abs(out))) - target) < 1e-5


def test_sharpen_mel_numpy_matches_torch_2d():
    """Bản numpy dùng cho ONNX phải khớp torch (zero-pad 3×3, chia 9)."""
    import numpy as np
    import torch

    from vifasttts.runtime.postprocess import sharpen_mel, sharpen_mel_numpy

    rng = np.random.default_rng(0)
    x = rng.normal(size=(9, 7)).astype(np.float32)
    expected = sharpen_mel(torch.from_numpy(x), 1.5).numpy()
    actual = sharpen_mel_numpy(x, 1.5)
    assert np.allclose(actual, expected, atol=1e-6)


def test_sharpen_mel_numpy_batch_shape():
    """Nhận batch [B,T,F] và alpha=0 trả nguyên bản."""
    import numpy as np

    from vifasttts.runtime.postprocess import sharpen_mel_numpy

    x = np.arange(3 * 5 * 4, dtype=np.float32).reshape(3, 5, 4)
    assert sharpen_mel_numpy(x, 0.0).shape == (3, 5, 4)
    assert np.allclose(sharpen_mel_numpy(x, 0.0), x)
    assert sharpen_mel_numpy(x, 1.5).shape == x.shape
