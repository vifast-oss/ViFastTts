"""v18.46 — A3: Spearman giữa hiệu BAK(B)-BAK(C) và thời lượng câu trên 120 câu."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.stats import spearmanr

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.v1845_a4_confirm import bak

A43 = json.loads(Path("artifacts/bench/v1843_a4/result.json").read_text(encoding="utf-8"))
A45 = json.loads(Path("artifacts/bench/v1845_a4_new/result.json").read_text(encoding="utf-8"))
A4 = json.loads(Path("artifacts/bench/v1846_a4_mechanism/window.json").read_text(encoding="utf-8"))
LONG = Path("artifacts/bench/v1846_a2_long")
OUT = Path("artifacts/bench/v1846_a3_duration")
N_BOOT = 10000


def main() -> None:
    rows = []
    for index, row in enumerate(A43["rows"]):
        rows.append({"id": row["id"], "set": "old43", "seconds": None,
                     "d_bak": row["metrics"]["B"]["bak"] - row["metrics"]["C"]["bak"]})
    for index, item_id in enumerate(A45["rows"]):
        rows.append({"id": item_id, "set": "old45", "seconds": None,
                     "d_bak": A45["baks"]["B"][index] - A45["baks"]["C"][index]})
    for index, item_id in enumerate(json.loads((LONG / "result.json").read_text())["rows"]):
        b = bak(sf.read(LONG / f"{index:02d}_B.wav", dtype="float32")[0], 24000)
        c = bak(sf.read(LONG / f"{index:02d}_C.wav", dtype="float32")[0], 24000)
        rows.append({"id": item_id, "set": "long", "seconds": None, "d_bak": b - c})
    by_id = {item["id"]: item for item in A4["items"]}
    for row in rows:
        row["seconds"] = by_id[row["id"]]["seconds"]
    durations = np.asarray([row["seconds"] for row in rows], dtype=float)
    dbak = np.asarray([row["d_bak"] for row in rows], dtype=float)
    rho = float(spearmanr(durations, dbak).statistic)
    rng = np.random.default_rng(0)
    boots = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, len(rows), size=len(rows))
        value = spearmanr(durations[idx], dbak[idx]).statistic
        if np.isfinite(value):
            boots.append(float(value))
    ci = [round(float(np.percentile(boots, 2.5)), 4),
          round(float(np.percentile(boots, 97.5)), 4)]
    relevant = bool(rho >= 0.3 and (ci[0] > 0 or ci[1] < 0))
    result = {"n": len(rows), "rho": round(rho, 4), "ci95": ci,
              "relevant": relevant, "rows": rows, "bootstrap": N_BOOT}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("n", "rho", "ci95", "relevant")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
