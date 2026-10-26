"""v18.49 — A3: chấm CSV nghe mù PILOT vs CONTROL."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from scipy.stats import binomtest

KEY = Path("artifacts/bench/v1849_a3/key.json")
OUT = Path("artifacts/bench/v1849_a3/score.json")


def source_of(trial: dict, answer: str) -> str:
    answer = (answer or "").lower()
    if answer == "tie":
        return "tie"
    if answer == "a":
        return trial["a_source"]
    if answer == "b":
        return trial["b_source"]
    return "missing"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv")
    parser.add_argument("--key", default=str(KEY))
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()
    key = json.loads(Path(args.key).read_text(encoding="utf-8"))
    trials = {trial["id"]: trial for trial in key["trials"]}
    answers = {}
    with Path(args.csv).open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            tid = (row.get("trial_id") or "").strip()
            ans = (row.get("answer") or "").strip().lower()
            answers[tid] = {"a": "A", "b": "B", "tie": "tie"}.get(ans, "missing")
    missing = [tid for tid in trials if answers.get(tid, "missing") == "missing"]
    main = [trial for trial in trials.values() if trial["kind"] == "main"]
    positive = [trial for trial in trials.values() if trial["kind"] == "positive"]
    negative = [trial for trial in trials.values() if trial["kind"] == "negative"]
    repeat = [trial for trial in trials.values() if trial["kind"] == "repeat"]
    sources = {trial["id"]: source_of(trial, answers.get(trial["id"], "missing"))
               for trial in main}
    pilot = sum(value == "PILOT" for value in sources.values())
    control = sum(value == "CONTROL" for value in sources.values())
    ties = sum(value == "tie" for value in sources.values())
    non_tie = pilot + control
    p_pilot = binomtest(pilot, non_tie, 0.5, alternative="greater").pvalue if non_tie else 1.0
    p_control = binomtest(control, non_tie, 0.5, alternative="greater").pvalue if non_tie else 1.0
    pilot_wins = bool(p_pilot < 0.05 and non_tie >= 10)
    control_wins = bool(p_control < 0.05 and non_tie >= 10)
    pos_ok = sum(source_of(trial, answers.get(trial["id"], "missing")) == "CONTROL_clean"
                 for trial in positive)
    neg_ok = sum(answers.get(trial["id"], "missing") == "tie" for trial in negative)
    main_by_sentence = {trial["sentence"]: trial for trial in main}
    repeat_ok = 0
    repeat_rows = []
    for trial in repeat:
        original = main_by_sentence.get(trial["repeat_of"])
        if original is None:
            repeat_rows.append({"id": trial["id"], "consistent": False,
                                "reason": "thiếu main gốc"})
            continue
        left = source_of(original, answers.get(original["id"], "missing"))
        right = source_of(trial, answers.get(trial["id"], "missing"))
        consistent = left == right
        repeat_ok += int(consistent)
        repeat_rows.append({"id": trial["id"], "repeat_of": trial["repeat_of"],
                            "original_source": left, "repeat_source": right,
                            "consistent": consistent})
    checks = {"positive": pos_ok >= 3, "negative": neg_ok >= 3,
              "repeat": repeat_ok >= 3, "complete": not missing}
    valid = all(checks.values())
    if not valid:
        verdict = "KHÔNG HỢP LỆ — làm lại ngày khác"
    elif pilot_wins:
        verdict = "PILOT THẮNG"
    elif control_wins:
        verdict = "CONTROL THẮNG RÕ — ĐÓNG L_con"
    elif non_tie < 10:
        verdict = "TAI KHÔNG PHÂN BIỆT — <10 lượt không hòa"
    else:
        verdict = "KHÔNG KẾT LUẬN"
    result = {"n": len(trials), "missing": missing,
              "main": {"pilot": pilot, "control": control, "tie": ties,
                       "non_tie": non_tie, "p_pilot": round(float(p_pilot), 6),
                       "p_control": round(float(p_control), 6),
                       "pilot_wins": pilot_wins, "control_wins": control_wins},
              "validity": {"positive_clean": pos_ok, "positive_total": len(positive),
                           "negative_tie": neg_ok, "negative_total": len(negative),
                           "repeat_consistent": repeat_ok, "repeat_total": len(repeat),
                           "checks": checks, "all": valid},
              "repeat_rows": repeat_rows, "verdict": verdict}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
