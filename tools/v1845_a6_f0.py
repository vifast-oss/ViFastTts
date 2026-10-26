"""v18.45 — A6: đo phụ cao độ trên 80 câu (40 A4 cũ + 40 mới).

- RMSE F0 C vs A (cent) trên frame cả hai hữu thanh.
- Tỉ lệ sai hữu thanh/vô thanh (vuv).
- Tỉ số độ lệch chuẩn log-F0 theo câu C/A.
- Spearman giữa BAK(B)-BAK(C) theo câu và từng chỉ số; bootstrap CI95 theo câu.
Chỉ định hướng, không làm cổng chính.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import yaml
from scipy.stats import spearmanr

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from vifasttts.data.features import extract_features

OLD_A4 = Path("artifacts/bench/v1843_a4/result.json")
OLD_DIR = Path("artifacts/bench/v1843_a4")
NEW_A4 = Path("artifacts/bench/v1845_a4_new/result.json")
NEW_DIR = Path("artifacts/bench/v1845_a4_new")
HOLDOUT = "data/codelung/v32/holdout_clean_v2_dur_seg_slot4.jsonl"
CFG32 = "configs/small_codelung_v32.yaml"
OUT = Path("artifacts/bench/v1845_a6")
N_BOOT = 10000


def cut_original(row: dict, sample_rate: int = 24000, hop: int = 256) -> np.ndarray:
    wave, sr = sf.read(row["audio_path"], dtype="float32")
    wave = np.asarray(wave).reshape(-1)
    if sr != sample_rate:
        raise RuntimeError(f"sr {sr} != {sample_rate}")
    start, end = (int(x) for x in row["frame_range"])
    return wave[start * hop:end * hop]


def load_pairs() -> list[dict]:
    cfg = yaml.safe_load(Path(CFG32).read_text(encoding="utf-8"))
    rows = {json.loads(line)["id"]: json.loads(line)
            for line in Path(HOLDOUT).read_text(encoding="utf-8").splitlines() if line.strip()}
    old = json.loads(OLD_A4.read_text(encoding="utf-8"))["rows"]
    new = json.loads(NEW_A4.read_text(encoding="utf-8"))
    pairs = []
    for index, row in enumerate(old):
        pairs.append({"id": row["id"], "set": "old",
                      "a_path": OLD_DIR / f"{index:02d}_A.wav",
                      "c_path": OLD_DIR / f"{index:02d}_C.wav",
                      "d_bak": row["metrics"]["B"]["bak"] - row["metrics"]["C"]["bak"]})
    for index, item_id in enumerate(new["rows"]):
        a_path = OUT / f"{index:02d}_A.wav"
        wave = cut_original(rows[item_id], int(cfg.get("sample_rate", 24000)))
        sf.write(a_path, wave, int(cfg.get("sample_rate", 24000)), subtype="PCM_16")
        pairs.append({"id": item_id, "set": "new", "a_path": a_path,
                      "c_path": NEW_DIR / f"{index:02d}_C.wav",
                      "d_bak": new["baks"]["B"][index] - new["baks"]["C"][index]})
    return pairs


def f0_metrics(a_path: Path, c_path: Path, cfg: dict) -> dict:
    a = extract_features(a_path, cfg)
    c = extract_features(c_path, cfg)
    fa = np.asarray(a["f0"].cpu(), dtype=float).reshape(-1)
    fc = np.asarray(c["f0"].cpu(), dtype=float).reshape(-1)
    va = np.asarray(a["vuv"].cpu(), dtype=float).reshape(-1) > 0.5
    vc = np.asarray(c["vuv"].cpu(), dtype=float).reshape(-1) > 0.5
    n = min(fa.size, fc.size, va.size, vc.size)
    fa, fc, va, vc = fa[:n], fc[:n], va[:n], vc[:n]
    voiced = va & vc & (fa > 1e-6) & (fc > 1e-6)
    if voiced.sum() >= 2:
        cents = 1200.0 * np.log2(fc[voiced] / fa[voiced])
        rmse = float(np.sqrt(np.mean(cents ** 2)))
        std_ratio = (float(np.std(np.log2(fc[voiced])) / np.std(np.log2(fa[voiced])))
                     if np.std(np.log2(fa[voiced])) > 1e-9 else float("nan"))
    else:
        rmse = float("nan")
        std_ratio = float("nan")
    vuv_error = float(np.mean(va != vc)) if n else float("nan")
    return {"rmse_cents": rmse, "vuv_error": vuv_error, "std_ratio": std_ratio,
            "n_frames": int(n), "n_voiced_both": int(voiced.sum())}


def bootstrap_rho(metric: np.ndarray, dbak: np.ndarray, n_boot: int = N_BOOT) -> dict:
    rng = np.random.default_rng(0)
    values = []
    n = metric.size
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        rho = spearmanr(metric[idx], dbak[idx]).statistic
        if np.isfinite(rho):
            values.append(float(rho))
    if not values:
        return {"rho": None, "ci95": None}
    return {"rho": float(spearmanr(metric, dbak).statistic),
            "ci95": [round(float(np.percentile(values, 2.5)), 4),
                     round(float(np.percentile(values, 97.5)), 4)]}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = yaml.safe_load(Path(CFG32).read_text(encoding="utf-8"))
    pairs = load_pairs()
    rows = []
    for index, pair in enumerate(pairs):
        try:
            metrics = f0_metrics(pair["a_path"], pair["c_path"], cfg)
        except (RuntimeError, ValueError, OSError) as exc:  # F0 extractor lỗi: bỏ câu, báo
            metrics = {"error": repr(exc)}
        rows.append({"id": pair["id"], "set": pair["set"], "d_bak": round(pair["d_bak"], 6),
                     **metrics})
        print(json.dumps({"done": index + 1, "total": len(pairs)}), flush=True)
    available = [row for row in rows if "error" not in row]
    failure_rate = 1.0 - len(available) / max(len(rows), 1)
    results = {}
    for key in ("rmse_cents", "vuv_error", "std_ratio"):
        usable = [row for row in available
                  if row.get(key) is not None and np.isfinite(row.get(key, np.nan))]
        if len(usable) < 0.9 * len(rows):
            results[key] = {"dropped": True, "n": len(usable),
                            "reason": "F0 lỗi/không hữu thanh >10% câu"}
            continue
        metric = np.asarray([row[key] for row in usable], dtype=float)
        dbak = np.asarray([row["d_bak"] for row in usable], dtype=float)
        boot = bootstrap_rho(metric, dbak)
        relevant = bool(boot["rho"] is not None and boot["rho"] >= 0.4
                        and boot["ci95"] is not None
                        and (boot["ci95"][0] > 0 or boot["ci95"][1] < 0))
        results[key] = {"dropped": False, "n": len(usable), **boot,
                        "relevant": relevant}
    verdict = ("CÓ chỉ số cao độ liên quan" if any(
        value.get("relevant") for value in results.values()) else
        "KHÔNG có chỉ số cao độ liên quan")
    result = {"rows": rows, "f0_failure_rate": round(failure_rate, 4),
              "metrics": results, "verdict": verdict}
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(json.dumps({"f0_failure_rate": result["f0_failure_rate"],
                      "metrics": results, "verdict": verdict}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
