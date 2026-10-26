"""v18.44 — A5: chấm CSV nghe mù theo luật đã đăng ký.

CSV: `trial_id,answer` với answer ∈ {A,B,tie}. Key: `artifacts/bench/v1844_a5/key.json`.

Luật:
- Hợp lệ: dương ≥3/4 chọn bản sạch; âm ≥3/4 "không phân biệt"; lặp ≥3/4 nhất quán.
- B thắng: binomial một phía p<0,05 trên lượt không hòa, tối thiểu 10 lượt; 16 lượt cần ≥12.
- C thắng rõ: là lạ, dừng, báo.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from scipy.stats import binomtest

KEY = Path("artifacts/bench/v1844_a5/key.json")
OUT = Path("artifacts/bench/v1844_a5/score.json")


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
    parser.add_argument("csv", help="CSV tải từ trang nghe")
    parser.add_argument("--key", default=str(KEY))
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()
    key = json.loads(Path(args.key).read_text(encoding="utf-8"))
    trials = {trial["id"]: trial for trial in key["trials"]}
    answers = {}
    with Path(args.csv).open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            trial_id = (row.get("trial_id") or "").strip()
            answer = (row.get("answer") or "").strip().lower()
            answers[trial_id] = {"a": "A", "b": "B", "tie": "tie"}.get(answer, "missing")
    missing = [trial_id for trial_id in trials if answers.get(trial_id, "missing") == "missing"]

    main = [trial for trial in trials.values() if trial["kind"] == "main"]
    positive = [trial for trial in trials.values() if trial["kind"] == "positive"]
    negative = [trial for trial in trials.values() if trial["kind"] == "negative"]
    repeat = [trial for trial in trials.values() if trial["kind"] == "repeat"]

    main_sources = {trial["id"]: source_of(trial, answers.get(trial["id"], "missing"))
                    for trial in main}
    b_count = sum(source == "B" for source in main_sources.values())
    c_count = sum(source == "C" for source in main_sources.values())
    ties = sum(source == "tie" for source in main_sources.values())
    non_tie = b_count + c_count
    p_b = (binomtest(b_count, non_tie, 0.5, alternative="greater").pvalue
           if non_tie else 1.0)
    p_c = (binomtest(c_count, non_tie, 0.5, alternative="greater").pvalue
           if non_tie else 1.0)
    b_wins = bool(p_b < 0.05 and non_tie >= 10 and b_count >= 12)
    c_wins = bool(p_c < 0.05 and non_tie >= 10 and c_count >= 12)

    pos_ok = sum(source_of(trial, answers.get(trial["id"], "missing")) == "B_clean"
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

    valid = {
        "positive": pos_ok >= 3,
        "negative": neg_ok >= 3,
        "repeat": repeat_ok >= 3,
        "complete": len(missing) == 0,
    }
    valid_all = all(valid.values())
    if not valid_all:
        verdict = "KHÔNG HỢP LỆ — làm lại một phiên khác ngày"
    elif b_wins:
        verdict = "XÁC NHẬN — B (bản ít rè hơn theo BAK) thắng"
    elif c_wins:
        verdict = "C THẮNG RÕ — LẠ, DỪNG, BÁO"
    else:
        verdict = "KHÔNG XÁC NHẬN — B không thắng; không train theo BAK"

    result = {
        "csv": str(Path(args.csv).resolve()),
        "n_trials": len(trials),
        "missing": missing,
        "main": {"b": b_count, "c": c_count, "tie": ties, "non_tie": non_tie,
                 "p_b": round(float(p_b), 6), "p_c": round(float(p_c), 6),
                 "b_wins": b_wins, "c_wins": c_wins},
        "validity": {"positive_clean": pos_ok, "positive_total": len(positive),
                     "negative_tie": neg_ok, "negative_total": len(negative),
                     "repeat_consistent": repeat_ok, "repeat_total": len(repeat),
                     "checks": valid, "all": valid_all},
        "repeat_rows": repeat_rows,
        "verdict": verdict,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
