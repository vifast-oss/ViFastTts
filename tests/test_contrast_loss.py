"""Unit test L_con (V1848.A1)."""

from __future__ import annotations

import torch

from vifasttts.models.contrast_loss import contrast_loss, spectral_contrast


def _sample() -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    torch.manual_seed(0)
    target = torch.randn(2, 8, 20)
    voice = torch.ones(2, 8, dtype=torch.bool)
    bins = torch.arange(2, 14)
    return target, voice, bins


def test_p_equal_t_gives_zero() -> None:
    target, voice, bins = _sample()
    loss = contrast_loss(target, target, voice, bins)
    assert float(loss) == 0.0


def test_frequency_smoothed_t_has_positive_loss() -> None:
    target, voice, bins = _sample()
    low = target[..., bins]
    smoothed = torch.nn.functional.avg_pool1d(low, kernel_size=3, stride=1, padding=1)
    pred = target.clone()
    pred[..., bins] = smoothed
    loss = contrast_loss(pred, target, voice, bins)
    assert float(loss) > 0.0


def test_gradient_finite() -> None:
    target, voice, bins = _sample()
    pred = target.clone().requires_grad_(True)
    loss = contrast_loss(pred, target, voice, bins)
    loss.backward()
    assert pred.grad is not None
    assert torch.isfinite(pred.grad).all()


def test_empty_voice_is_zero_and_finite() -> None:
    target, _voice, bins = _sample()
    loss = contrast_loss(target, target, torch.zeros(2, 8, dtype=torch.bool), bins)
    assert float(loss) == 0.0


def test_spectral_contrast_shape() -> None:
    target, _voice, bins = _sample()
    contrast = spectral_contrast(target, bins)
    assert contrast.shape == (2, 8)
    assert torch.isfinite(contrast).all()
