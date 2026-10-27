#!/usr/bin/env python3
"""Audit nhãn âm tiết trong manifest trước/sau reparse — chỉ báo cảnh báo, không chặn.

Ví dụ:
    python tools/validate_syllables.py data/ngochuyen/manifests/train_dur_seg_slot4.jsonl
    python tools/validate_syllables.py --report artifacts/validate_syllables.json \
        data/ngochuyen/manifests/train_dur_seg_slot4.jsonl ...
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
for extra in (_ROOT, _ROOT / "tools"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from vifasttts.frontend.lexicon import strict_warnings
from vifasttts.frontend.pipeline import parse_text
from vifasttts.frontend.rules import MEDIAL_NUCLEUS_COMPATIBILITY, STOP_CODAS

_WARNING_ORDER = (
    "stale_abstract", "legacy_k_w", "stored_coda_tone", "stored_medial_nucleus",
    "fallback", "labial-w", "coda-nh-ch-after-nonfront", "spelling-c-before-front",
    "spelling-k-before-back", "spelling-g-before-front", "spelling-gh-before-back",
    "spelling-ng-before-front", "spelling-ngh-before-back",
    "standalone-ie", "open-double-vowel-spelling", "other",
)


def _stored_checks(stored: dict[str, Any]) -> list[str]:
    """Kiểm luật trên nhãn đã lưu (kể cả nhãn cũ trước khi reparse)."""
    issues: list[str] = []
    onset = str(stored.get("onset") or "NONE")
    medial = str(stored.get("medial") or "NONE")
    nucleus = str(stored.get("nucleus") or "NONE")
    coda = str(stored.get("coda") or "NONE")
    tone = str(stored.get("tone") or "NGANG")
    if onset == "K" and medial == "W":
        issues.append("legacy_k_w")
    if coda in STOP_CODAS and tone not in {"SAC", "NANG"}:
        issues.append("stored_coda_tone")
    if nucleus not in MEDIAL_NUCLEUS_COMPATIBILITY.get(medial, set()):
        issues.append("stored_medial_nucleus")
    return issues


def audit_manifest(path: str | Path) -> dict[str, Any]:
    """Quét một manifest JSONL; trả thống kê cảnh báo + ví dụ."""
    manifest = Path(path)
    counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    rows = 0
    syllables = 0
    with manifest.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, 1):
            if not line.strip():
                continue
            rows += 1
            row = json.loads(line)
            text = row.get("text")
            stored = row.get("syllables") or []
            if not text:
                counts["other"] += 1
                examples["other"].append(f"row {row.get('id', lineno)}: thiếu text")
                continue
            parsed = parse_text(str(text))
            if len(parsed) != len(stored):
                counts["other"] += 1
                examples["other"].append(
                    f"row {row.get('id', lineno)}: số âm tiết {len(stored)} → {len(parsed)}"
                )
                continue
            for current, old in zip(parsed, stored):
                syllables += 1
                ident = f"{row.get('id', lineno)}:{current.normalized}"
                old_abstract = old.get("abstract") or {}
                current_abstract = current.to_dict()["abstract"]
                if old_abstract != current_abstract:
                    counts["stale_abstract"] += 1
                    if len(examples["stale_abstract"]) < 20:
                        examples["stale_abstract"].append(
                            f"{ident}: {old_abstract} → {current_abstract}"
                        )
                for issue in _stored_checks(old_abstract):
                    counts[issue] += 1
                    if len(examples[issue]) < 20:
                        examples[issue].append(ident)
                if current.status.value != "VALID":
                    counts["fallback"] += 1
                    if len(examples["fallback"]) < 20:
                        examples["fallback"].append(f"{ident}: {current.raw!r}")
                    continue
                for issue in strict_warnings(current):
                    counts[issue] += 1
                    if len(examples[issue]) < 20:
                        examples[issue].append(ident)
    ordered = {key: counts.get(key, 0) for key in _WARNING_ORDER if counts.get(key, 0)}
    for key in counts:
        if key not in ordered:
            ordered[key] = counts[key]
    return {
        "manifest": str(manifest),
        "rows": rows,
        "syllables": syllables,
        "warnings": ordered,
        "total_warnings": sum(ordered.values()),
        "examples": dict(examples),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifests", nargs="+", help="Manifest JSONL có text + syllables")
    parser.add_argument("--report", help="Ghi báo cáo JSON")
    args = parser.parse_args()
    reports = [audit_manifest(path) for path in args.manifests]
    for report in reports:
        print(f"{report['manifest']}: {report['rows']} row, "
              f"{report['syllables']} âm tiết, {report['total_warnings']} cảnh báo")
        print("  " + ", ".join(f"{key}={value}" for key, value in report["warnings"].items()))
        for key, items in report["examples"].items():
            if items:
                print(f"  {key}: " + " | ".join(items[:3]))
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(
            json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Đã ghi {args.report}")


if __name__ == "__main__":
    main()
