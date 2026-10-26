"""Loss độ tương phản phổ dải thấp (V1848.A1).

`contrast_f(X)` = trung bình theo bin của (max − min) trong cửa sổ 5 bin tại frame f.
`L_con` = trung bình theo frame hữu thanh của |contrast_f(pred) − contrast_f(target)|.

Khớp **mức tương phản theo frame**, không khớp từng bin — tránh ép model lấy trung bình
vị trí họa âm (tức lại nhòe).
"""

from __future__ import annotations

import torch


def spectral_contrast(frames: torch.Tensor, bins: torch.Tensor, window: int = 5) -> torch.Tensor:
    """frames [B,T,M] → contrast [B,T]; chỉ các bin trong `bins`, cửa sổ `window`."""
    if frames.dim() != 3:
        raise ValueError(f"cần [B,T,M], nhận {tuple(frames.shape)}")
    if bins.numel() == 0:
        return torch.zeros(frames.shape[:2], device=frames.device, dtype=frames.dtype)
    low = frames.index_select(-1, bins.to(frames.device))
    if low.size(-1) < window:
        return torch.zeros(frames.shape[:2], device=frames.device, dtype=frames.dtype)
    windows = low.unfold(-1, window, 1)
    return (windows.max(dim=-1).values - windows.min(dim=-1).values).mean(dim=-1)


def contrast_loss(pred: torch.Tensor, target: torch.Tensor, voice: torch.Tensor,
                  bins: torch.Tensor, window: int = 5) -> torch.Tensor:
    """L_con trên các frame hữu thanh; pred/target [B,T,M], voice [B,T] bool."""
    contrast_pred = spectral_contrast(pred, bins, window)
    contrast_target = spectral_contrast(target, bins, window)
    mask = voice.to(device=pred.device, dtype=torch.bool)
    if int(mask.sum()) == 0:
        return pred.sum() * 0.0
    return (contrast_pred - contrast_target).abs()[mask].mean()
