"""Test tools/audit_syllable_pairs.py — audit cặp âm tiết frontend."""
from __future__ import annotations

from tools.audit_syllable_pairs import audit_syllables


def test_audit_co_ban():
    report = audit_syllables(
        {"tai", "tay", "quốc", "cuốc", "hi", "hy", "sa", "xa", "xyz123"}
    )
    # "xyz123" không phải âm tiết Việt → fallback
    assert report["fallback"] == ["xyz123"]
    # i/y gộp (biến thể chính tả — "hi"/"hy"); quốc/cuốc tách Q/K nhưng cùng IPA Bắc
    merge_keys = {item["abstract"] for item in report["merges"]}
    assert "H+NONE+I+NONE+NGANG" in merge_keys
    assert "K+NONE+UÔ+C+SAC" not in merge_keys
    # s/x và quốc/cuốc là tách có chủ đích (cùng IPA Bắc, khác abstract)
    assert report["split_families"] == {"S/X": 1, "K/Q": 1}
    # cả 8 âm tiết hợp lệ đều được audit, không có nhóm lạ
    assert report["syllables"] == 9
