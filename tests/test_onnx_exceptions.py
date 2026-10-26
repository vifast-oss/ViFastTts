"""A1c — parity đọc ngoại lệ có định danh; input khác vượt 0,02 vẫn FAIL."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from v1840_onnx_parity import (
    CRITERIA,
    EXCEPTIONS,
    load_exceptions,
    vocoder_check,
)


def _row(max_abs: float = 0.023357868194580078) -> dict:
    return {
        "spectrum_real": {"max_abs": max_abs, "mean_abs": 1e-05, "shape_equal": True,
                          "finite": True},
        "spectrum_imag": {"max_abs": 0.017773866653442383, "mean_abs": 1e-05,
                          "shape_equal": True, "finite": True},
        "waveform": {"shape_equal": True, "finite": True, "max_abs": 3.23e-04,
                     "rmse": 7.74e-06},
    }


def _context(acoustic: str = "ff6844ec8a28b2c17a40d944d9ebe19476a159b8573c22fdd52c932cbfcdf23f",
             vocoder: str = "ed193b8246ae4078203e2b88fae5bc492b53b9f6ae6fd7652a1278aca02dd3f3") -> dict:
    return {"mode": "chunk", "provider": "CPUExecutionProvider",
            "acoustic_sha256": acoustic, "vocoder_sha256": vocoder}


def test_exception_file_has_onnx_exc_001() -> None:
    data = load_exceptions(EXCEPTIONS)
    ids = [entry["id"] for entry in data["exceptions"]]
    assert "ONNX-EXC-001" in ids
    entry = next(item for item in data["exceptions"] if item["id"] == "ONNX-EXC-001")
    assert entry["input"] == "2b65WyiFC9k_0030__s03"
    assert entry["criterion"] == CRITERIA["vocoder"]["spectrum_max_abs"]
    assert entry["observed_max"]["real"] > entry["criterion"]


def test_exception_applies_only_to_named_input() -> None:
    data = load_exceptions(EXCEPTIONS)
    named = {"id": "2b65WyiFC9k_0030__s03", "kind": "manifest"}
    other = {"id": "some_other_input", "kind": "manifest"}
    assert vocoder_check(_row(), named, _context(), data)["pass"] is True
    assert vocoder_check(_row(), named, _context(), data)["exception_id"] == "ONNX-EXC-001"
    failed = vocoder_check(_row(), other, _context(), data)
    assert failed["pass"] is False
    assert failed["exception_id"] is None
    assert failed["spectrum_ok"] is False


def test_exception_invalid_when_hash_changes() -> None:
    data = load_exceptions(EXCEPTIONS)
    named = {"id": "2b65WyiFC9k_0030__s03", "kind": "manifest"}
    changed = _context(acoustic="0" * 64)
    result = vocoder_check(_row(), named, changed, data)
    assert result["pass"] is False
    assert result["exception_id"] is None


def test_exception_does_not_hide_waveform_failure() -> None:
    data = load_exceptions(EXCEPTIONS)
    named = {"id": "2b65WyiFC9k_0030__s03", "kind": "manifest"}
    row = _row()
    row["waveform"]["max_abs"] = 1.0
    assert vocoder_check(row, named, _context(), data)["pass"] is False
