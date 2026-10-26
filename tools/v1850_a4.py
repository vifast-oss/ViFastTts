"""v18.50 — A4: nối nhãn bấm với bảng đặc trưng P2; AUC + creak P2−A."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

KEY = Path("artifacts/bench/v1850_mark/key.json")
TABLE = Path("artifacts/bench/v1850_features/table.json")
OUT = Path("artifacts/bench/v1850_features/a4.json")
N_BOOT = 10000


def parse_set(text: str) -> set[int]:
    return {int(x) for x in (text or "").split(";") if x.strip().isdigit()}


def auc_score(scores: np.ndarray, labels: np.ndarray) -> float:
    pos = scores[labels]
    neg = scores[~labels]
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    allv = np.concatenate([pos, neg])
    order = np.argsort(allv, kind="mergesort")
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, allv.size + 1)
    # xử lý ties: rank trung bình
    sorted_v = allv[order]
    i = 0
    while i < sorted_v.size:
        j = i + 1
        while j < sorted_v.size and sorted_v[j] == sorted_v[i]:
            j += 1
        if j - i > 1:
            ranks[order[i:j]] = (i + 1 + j) / 2.0
        i = j
    pos_ranks = ranks[:pos.size]
    return float((pos_ranks.sum() - pos.size * (pos.size + 1) / 2)
                 / (pos.size * neg.size))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv")
    parser.add_argument("--key", default=str(KEY))
    parser.add_argument("--table", default=str(TABLE))
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()
    key = json.loads(Path(args.key).read_text(encoding="utf-8"))
    table = {row["sentence"]: row for row in json.loads(Path(args.table).read_text())["table"]}
    items = {item["id"]: item for item in key["items"]}
    answers = {}
    with Path(args.csv).open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            tid = (row.get("item_id") or "").strip()
            answers[tid] = {"clicked": parse_set(row.get("syllables", "")),
                            "mismatch": int((row.get("mismatch") or "0").strip() or 0)}
    p2_items = [x for x in items.values() if x["kind"] == "main" and x["version"] == "P2"]
    # loại câu có A/B mismatch, loại item P2 mismatch
    suspect = set()
    for item in items.values():
        if (item["kind"] == "main" and item["version"] in ("A", "B")
                and answers.get(item["id"], {}).get("mismatch")):
            suspect.add(item["sentence"])
    records = []
    excluded = {"suspect_sentences": sorted(suspect), "p2_mismatch": []}
    for item in p2_items:
        sentence = item["sentence"]
        if sentence in suspect:
            continue
        if answers.get(item["id"], {}).get("mismatch"):
            excluded["p2_mismatch"].append(item["id"])
            continue
        clicked = answers.get(item["id"], {}).get("clicked", set())
        for syl in table[sentence]["P2"]:
            idx = syl["index"]
            a_syl = table[sentence]["A"][idx - 1] if idx - 1 < len(table[sentence]["A"]) else {}
            records.append({**syl, "sentence": sentence, "clicked": idx in clicked,
                            "creak_a": a_syl.get("creak"),
                            "creak_diff": (syl.get("creak") - a_syl.get("creak")
                                           if a_syl.get("creak") is not None else None)})
    n_clicked = sum(1 for r in records if r["clicked"])
    features = ["hnr", "flatness_2_8k", "contrast", "f0_jump_cents", "duration_ratio",
                "dist_start", "dist_end", "coda_stop", "oov", "abbrev_number", "creak"]
    results = {}
    sentences = sorted({r["sentence"] for r in records})
    rng = np.random.default_rng(0)
    for feat in features:
        usable = [r for r in records if r.get(feat) is not None]
        if len(usable) < 30:
            continue
        scores = np.asarray([float(r[feat]) for r in usable])
        labels = np.asarray([bool(r["clicked"]) for r in usable])
        auc = auc_score(scores, labels)
        boots = []
        by_sentence = {s: [r for r in usable if r["sentence"] == s] for s in sentences}
        for _ in range(N_BOOT):
            pick = [sentences[i] for i in rng.integers(0, len(sentences), len(sentences))]
            vals, labs = [], []
            for s in pick:
                vals.extend(float(r[feat]) for r in by_sentence.get(s, []))
                labs.extend(bool(r["clicked"]) for r in by_sentence.get(s, []))
            if len(set(labs)) > 1:
                boots.append(auc_score(np.asarray(vals), np.asarray(labs)))
        ci = [round(float(np.percentile(boots, 2.5)), 4),
              round(float(np.percentile(boots, 97.5)), 4)] if boots else None
        relevant = bool(ci and ((auc >= 0.70 and ci[0] > 0.55)
                                or (auc <= 0.30 and ci[1] < 0.45)))
        results[feat] = {"auc": round(float(auc), 4), "ci95": ci,
                         "relevant": relevant, "n": len(usable)}
    # creak P2-A trên âm tiết bị bấm, tách NGÃ/NẶNG
    clicked = [r for r in records if r["clicked"] and r["creak_diff"] is not None]
    def boot_mean(rows: list[dict]) -> dict:
        if not rows:
            return {"n": 0}
        by_s = {}
        for r in rows:
            by_s.setdefault(r["sentence"], []).append(r["creak_diff"])
        vals = [np.mean(v) for v in by_s.values()]
        means = []
        for _ in range(N_BOOT):
            pick = rng.integers(0, len(vals), len(vals))
            means.append(float(np.mean(np.asarray(vals)[pick])))
        return {"n": len(rows), "mean": round(float(np.mean(vals)), 4),
                "ci95": [round(float(np.percentile(means, 2.5)), 4),
                         round(float(np.percentile(means, 97.5)), 4)]}
    creak_all = boot_mean(clicked)
    creak_nga = boot_mean([r for r in clicked if r.get("tone") == "NGA"])
    creak_nang = boot_mean([r for r in clicked if r.get("tone") == "NANG"])
    result = {"n_sentences": len(sentences), "n_syllables": len(records),
              "n_clicked_p2": n_clicked, "excluded": excluded,
              "descriptive_only": n_clicked < 30,
              "features": results, "creak_diff": {"all": creak_all, "NGA": creak_nga,
                                                  "NANG": creak_nang}}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
