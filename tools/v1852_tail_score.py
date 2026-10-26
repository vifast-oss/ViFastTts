"""v18.52 — A2: chấm hiệu chỉnh bộ dò đuôi (40 + 8 đối chứng)."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

KEY = Path("artifacts/bench/v1852_tail/key.json")
OUT = Path("artifacts/bench/v1852_tail/score.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv")
    parser.add_argument("--key", default=str(KEY))
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()
    key = json.loads(Path(args.key).read_text(encoding="utf-8"))
    items = {x["id"]: x for x in key["items"]}
    answers = {}
    with Path(args.csv).open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            answers[row["item_id"]] = (row.get("answer") or "").strip().lower()
    missing = [iid for iid in items if answers.get(iid, "") == ""]
    pos = [x for x in items.values() if x["kind"] == "control_positive"]
    neg = [x for x in items.values() if x["kind"] == "control_negative"]
    pos_ok = sum(answers.get(x["id"]) == "co" for x in pos)
    neg_ok = sum(answers.get(x["id"]) == "khong" for x in neg)
    calib = [x for x in items.values() if x["kind"] == "calib"]
    pairs = [(bool(x["detector_positive"]), answers.get(x["id"]))
             for x in calib if answers.get(x["id"]) in ("co", "khong")]
    tp = sum(1 for d, a in pairs if d and a == "co")
    fp = sum(1 for d, a in pairs if d and a == "khong")
    fn = sum(1 for d, a in pairs if not d and a == "co")
    tn = sum(1 for d, a in pairs if not d and a == "khong")
    agree = (tp + tn) / max(len(pairs), 1)
    precision = tp / max(tp + fp, 1)
    valid = pos_ok >= 3 and neg_ok >= 3 and not missing
    passed = bool(valid and agree >= 0.85 and precision >= 0.8)
    result = {"n": len(items), "missing": missing,
              "controls": {"positive_co": pos_ok, "positive_total": len(pos),
                           "negative_khong": neg_ok, "negative_total": len(neg)},
              "calibration": {"n_answered": len(pairs), "tp": tp, "fp": fp, "fn": fn,
                              "tn": tn, "agreement": round(agree, 4),
                              "precision": round(precision, 4)},
              "valid": valid, "detector_pass": passed,
              "verdict": ("ĐẠT — bộ dò khớp tai" if passed else
                          ("PHIÊN KHÔNG HỢP LỆ" if not valid else
                           "TRƯỢT — bộ dò không đủ khớp tai"))}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
