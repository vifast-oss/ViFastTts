"""Golden set v18.43 — chống tái phát âm thầm (V1842.A6 / V1842b.4).

Fast test: 3 câu, CPU, chunk mode, hash mel + wav cho PyTorch CPU và ONNX CPU.
Baseline đầy đủ 20 câu nằm ở `eval/golden/v1843/v1843_golden_full.json` (marker `slow`,
chạy tay bằng `tools/v1843_golden.py --build-full`).

Test này bỏ qua nếu chưa có baseline hoặc thiếu artifact local.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FAST_JSON = ROOT / "eval/golden/v1843/v1843_golden_fast.json"
FAST_NPZ = ROOT / "eval/golden/v1843/v1843_golden_fast.npz"
P2 = ROOT / "artifacts/listen_small_filt/adv_progress_p2/_ckpt/step_02000.pt"
ACOUSTIC = ROOT / "artifacts/onnx/v1837/p2ema_acoustic.onnx"
VOCODER = ROOT / "artifacts/onnx/v1837/vocos_pretrained_vocoder.onnx"

def _legacy_checkpoint_without_vocab_hash() -> bool:
    if not P2.exists():
        return False
    try:
        import torch
        state = torch.load(P2, map_location="cpu", weights_only=False)
        return not bool(state.get("vocab_hash"))
    except (OSError, RuntimeError, AttributeError, TypeError):
        return False


pytestmark = pytest.mark.skipif(
    not (FAST_JSON.exists() and FAST_NPZ.exists() and P2.exists()
         and ACOUSTIC.exists() and VOCODER.exists())
    or _legacy_checkpoint_without_vocab_hash(),
    reason="chưa có baseline golden, thiếu artifact, hoặc checkpoint cũ chưa có vocab_hash",
)


def test_golden_fast_outputs() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools/v1843_golden.py"), "--check-fast", "--skip-onnx"],
        cwd=ROOT, capture_output=True, text=True, timeout=120, check=False,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    result = json.loads(proc.stdout)
    assert result["ok"], json.dumps(result, ensure_ascii=False, indent=1)
    assert result["under_30s"], f"fast test quá 30 s: {result['elapsed_seconds']} s"
    assert result.get("onnx_skipped") == "V1844.A1 đóng băng ONNX"
    assert all(item["runtime"] == "pytorch" for item in result["details"])
    assert all(item["mel_ok"] and item["wav_ok"] for item in result["details"])
