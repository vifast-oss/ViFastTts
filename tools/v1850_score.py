"""v18.50 — chấm trang đánh dấu rè cục bộ (A/B/P2/PILOT + mismatch).

CSV: item_id,syllables,mismatch. Syllables 1-based, ';'-separated.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

KEY = Path("artifacts/bench/v1850_mark/key.json")
OUT = Path("artifacts/bench/v1850_mark/score.json")
N_BOOT = 10000


def parse_set(text: str) -> set[int]:
    return {int(x) for x in (text or "").split(";") if x.strip().isdigit()}


def jaccard(a: set[int], b: set[int]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 1.0


def ci(values: list[float]) -> list[float]:
    return [round(float(np.percentile(values, 2.5)), 4),
            round(float(np.percentile(values, 97.5)), 4)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv")
    parser.add_argument("--key", default=str(KEY))
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()
    key = json.loads(Path(args.key).read_text(encoding="utf-8"))
    items = {item["id"]: item for item in key["items"]}
    answers = {}
    with Path(args.csv).open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            tid = (row.get("item_id") or "").strip()
            answers[tid] = {"clicked": parse_set(row.get("syllables", "")),
                            "mismatch": int((row.get("mismatch") or "0").strip() or 0)}
    missing = [tid for tid in items if tid not in answers]
    # đối chứng cấy: bấm đúng ±1
    artificial = [item for item in items.values() if item["kind"] == "artificial"]
    art_ok = 0
    art_rows = []
    for item in artificial:
        clicked = answers.get(item["id"], {}).get("clicked", set())
        target = int(item["target"])
        ok = any(abs(x - target) <= 1 for x in clicked)
        art_ok += int(ok)
        art_rows.append({"id": item["id"], "target": target, "clicked": sorted(clicked),
                         "ok": ok})
    # đối chứng lặp
    by_path = {item["path"]: item for item in items.values() if item["kind"] == "main"}
    repeat_ok = 0
    repeat_rows = []
    for item in [x for x in items.values() if x["kind"] == "repeat"]:
        original = by_path.get(item["repeat_of"])
        if original is None:
            repeat_rows.append({"id": item["id"], "consistent": False, "jaccard": 0})
            continue
        jac = jaccard(answers.get(item["id"], {}).get("clicked", set()),
                      answers.get(original["id"], {}).get("clicked", set()))
        ok = jac >= 0.5
        repeat_ok += int(ok)
        repeat_rows.append({"id": item["id"], "original": original["id"],
                            "jaccard": round(jac, 4), "consistent": ok})
    valid = {"artificial": art_ok >= 2, "repeat": repeat_ok >= 2,
             "complete": not missing}
    # mismatch: A -> loại câu; B -> loại câu; P2/PILOT -> loại bản đó, báo
    main = [x for x in items.values() if x["kind"] == "main"]
    by_sentence = {}
    for item in main:
        by_sentence.setdefault(item["sentence"], {})[item["version"]] = item
    suspect_labels = []
    model_wrong = []
    for sentence, versions in by_sentence.items():
        if (versions.get("A") and answers.get(versions["A"]["id"], {}).get("mismatch")
                or versions.get("B") and answers.get(versions["B"]["id"], {}).get("mismatch")):
            suspect_labels.append(sentence)
        for version in ("P2", "PILOT"):
            if versions.get(version) and answers.get(versions[version]["id"], {}).get("mismatch"):
                model_wrong.append({"sentence": sentence, "version": version})
    # Tập câu chung: loại nhãn nghi sai; P2/PILOT mismatch loại bản đó khỏi rate
    valid_sentences = [s for s in by_sentence if s not in suspect_labels]
    rates = {}
    caches = {}
    for version in ("A", "B", "P2", "PILOT"):
        num = den = 0
        per_sentence = {}
        for sentence in valid_sentences:
            item = by_sentence[sentence].get(version)
            if item is None:
                continue
            if any(x["sentence"] == sentence and x["version"] == version for x in model_wrong):
                continue
            clicked = answers.get(item["id"], {}).get("clicked", set())
            n = len(item["syllables"])
            per_sentence[sentence] = (len(clicked), n)
            num += len(clicked)
            den += n
        caches[version] = per_sentence
        rates[version] = num / den if den else None
    common = [s for s in valid_sentences
              if all(s in caches[v] for v in ("A", "B", "P2", "PILOT"))]
    def ratio(version, sentences):
        num = sum(caches[version][s][0] for s in sentences)
        den = sum(caches[version][s][1] for s in sentences)
        return num / den if den else float("nan")
    rng = np.random.default_rng(0)
    boot = {v: [] for v in ("A", "B", "P2", "PILOT")}
    boot_diff = {"P2-B": [], "PILOT-P2": [], "A-B": []}
    for _ in range(N_BOOT):
        sample = [common[i] for i in rng.integers(0, len(common), len(common))] if common else []
        for v in list(boot):
            boot[v].append(ratio(v, sample))
        boot_diff["P2-B"].append(ratio("P2", sample) - ratio("B", sample))
        boot_diff["PILOT-P2"].append(ratio("PILOT", sample) - ratio("P2", sample))
        boot_diff["A-B"].append(ratio("A", sample) - ratio("B", sample))
    rates_ci = {v: ci(boot[v]) for v in boot}
    diff_ci = {k: ci(v) for k, v in boot_diff.items()}
    r = {v: (rates[v] if rates[v] is not None else float("nan")) for v in rates}
    if r.get("P2") is not None and r["P2"] < 0.02:
        source = "HIẾM — r(P2) < 2%; báo, không A4"
    elif r.get("A") is not None and r.get("P2") is not None and r["A"] >= 0.7 * r["P2"]:
        source = "ĐẶC ĐIỂM GIỌNG — r(A) ≥ 0,7×r(P2); báo"
    elif (r.get("A") is not None and r.get("B") is not None and r.get("P2") is not None
          and r["A"] <= 0.5 * r["B"] and r["B"] >= 0.7 * r["P2"]):
        source = "VOCODER — r(A) ≤0,5×r(B) và r(B) ≥0,7×r(P2)"
    elif (r.get("B") is not None and r.get("P2") is not None
          and r["B"] <= 0.5 * r["P2"] and diff_ci["P2-B"][0] > 0):
        source = "ACOUSTIC — r(B) ≤0,5×r(P2) và CI dưới r(P2)-r(B)>0"
    else:
        source = "HỖN HỢP — không rơi nhánh nào"
    result = {
        "n": len(items), "missing": missing,
        "validity": {"artificial_ok": art_ok, "artificial_total": len(artificial),
                     "artificial_rows": art_rows, "repeat_ok": repeat_ok,
                     "repeat_total": len(repeat_rows), "repeat_rows": repeat_rows,
                     "checks": valid, "all": all(valid.values())},
        "suspect_labels": suspect_labels, "model_wrong_text": model_wrong,
        "valid_sentences": valid_sentences, "common_sentences": common,
        "rates": {v: round(float(r[v]), 4) if r.get(v) is not None and np.isfinite(r[v]) else None
                  for v in r},
        "rates_ci95": rates_ci, "diff_ci95": diff_ci,
        "source": source,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("validity", "suspect_labels",
                                             "model_wrong_text", "rates", "rates_ci95",
                                             "diff_ci95", "source")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
