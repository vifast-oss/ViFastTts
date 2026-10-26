"""v18.46 — A2: xác nhận C_lo trên 40 câu DÀI độc lập.

Cùng pipeline/cổng V1845.A4. Δac < 0,15 => ĐÓNG C_lo và hướng "rè acoustic dải thấp".
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import torch
import yaml

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("VIFASTT_INTRA_THREADS", "2")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

from tools.v1845_a4_confirm import (
    CFG32,
    HOLDOUT,
    P2,
    bak,
    band_bins,
    bootstrap_recovery,
    predict_c_mel,
    render_mel,
    replace_bins,
)
from vifasttts.data.dataset import TtsDataset
from vifasttts.infer import Synthesizer

OUT = Path("artifacts/bench/v1846_a2_long")
A2 = {"delta_min": 0.15, "recovery_min": 0.5, "ci_lower_min": 0.3,
      "sum_min": 0.5, "sum_max": 1.5, "control_tol": 0.02}

LONG_IDS = [
    "2b65WyiFC9k_0169__s02", "2b65WyiFC9k_0006__s00", "2b65WyiFC9k_0203__s00",
    "2b65WyiFC9k_0144__s00", "4ITcvEa_Acc_0125__s00", "4ITcvEa_Acc_0174__s00",
    "4ITcvEa_Acc_0196__s00", "4ITcvEa_Acc_0057__s02", "BD83pScFukQ_0203__s00",
    "BD83pScFukQ_0169__s00", "BD83pScFukQ_0322__s00", "BD83pScFukQ_0096__s01",
    "EM_ObHWvd94_0195__s00", "EM_ObHWvd94_0084__s00", "EM_ObHWvd94_0069__s00",
    "EM_ObHWvd94_0106__s00", "EUNlJU1BuzE_0239__s01", "EUNlJU1BuzE_0156__s00",
    "EUNlJU1BuzE_0039__s00", "EUNlJU1BuzE_0067__s00", "VeU_85bZlrY_0126__s01",
    "VeU_85bZlrY_0034__s03", "VeU_85bZlrY_0034__s02", "VeU_85bZlrY_0037__s01",
    "o8RjAmBtyZo_0075__s03", "o8RjAmBtyZo_0178__s00", "o8RjAmBtyZo_0174__s01",
    "o8RjAmBtyZo_0136__s00", "vEtfty4Cc6Y_0083__s01", "vEtfty4Cc6Y_0016__s00",
    "vEtfty4Cc6Y_0272__s01", "vEtfty4Cc6Y_0017__s00", "z0zSgR_oie4_0231__s00",
    "z0zSgR_oie4_0122__s01", "z0zSgR_oie4_0269__s00", "z0zSgR_oie4_0043__s00",
    "EUNlJU1BuzE_0189__s00", "z0zSgR_oie4_0211__s01", "2b65WyiFC9k_0185__s00",
    "BD83pScFukQ_0184__s00",
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    cfg = yaml.safe_load(Path(CFG32).read_text(encoding="utf-8"))
    dataset = TtsDataset(HOLDOUT, cfg, cache_dir=cfg.get("training", {}).get("cache_dir"))
    by_id = {row["id"]: index for index, row in enumerate(dataset.rows)}
    rows = [dataset.rows[by_id[item]] for item in LONG_IDS]
    engine = Synthesizer(cfg, P2, device="cpu")
    engine.model.eval()
    engine.vocoder.eval()
    _centers, lo_bins, hi_bins = band_bins(24000, 1024, 100, 12000.0)
    values = {name: [] for name in ("B", "C", "C_all", "C_none", "C_lo", "C_hi")}
    for count, row in enumerate(rows):
        item = dataset[by_id[row["id"]]]
        b_mel = item["mel"].detach().cpu().numpy().astype(np.float32)
        c_mel = predict_c_mel(engine, item["features"], row)
        frames = min(b_mel.shape[0], c_mel.shape[0])
        b_mel, c_mel = b_mel[:frames], c_mel[:frames]
        variants = {"B": b_mel, "C": c_mel, "C_all": b_mel.copy(), "C_none": c_mel.copy(),
                    "C_lo": replace_bins(c_mel, b_mel, lo_bins),
                    "C_hi": replace_bins(c_mel, b_mel, hi_bins)}
        for name, mel in variants.items():
            wave = render_mel(engine, mel, OUT / f"{count:02d}_{name}.wav", 24000)
            values[name].append(bak(wave, 24000))
        print(json.dumps({"done": count + 1, "total": len(rows)}), flush=True)
    means = {name: float(np.mean(val)) for name, val in values.items()}
    arrays = {name: np.asarray(val, dtype=float) for name, val in values.items()}
    delta = means["B"] - means["C"]
    ci = bootstrap_recovery(arrays)
    recovery = {name: ((means[name] - means["C"]) / delta) if abs(delta) > 1e-12 else None
                for name in ("C_lo", "C_hi")}
    sum_lo_hi = (recovery["C_lo"] or 0) + (recovery["C_hi"] or 0)
    controls_ok = (abs(means["C_all"] - means["B"]) <= A2["control_tol"]
                   and abs(means["C_none"] - means["C"]) <= A2["control_tol"])
    if not controls_ok:
        branch, status = "LẠ — đối chứng lệch", "DỪNG, BÁO"
    elif delta < A2["delta_min"]:
        branch, status = "ĐÓNG C_lo — Δac < 0,15", "ĐÓNG"
    elif recovery["C_hi"] >= A2["recovery_min"] and recovery["C_lo"] < A2["recovery_min"]:
        branch, status = "LẠ — C_hi chính trong khi C_lo không", "DỪNG, BÁO"
    elif not (A2["sum_min"] <= sum_lo_hi <= A2["sum_max"]):
        branch, status = "LẠ — tổng lo+hi ngoài [0,5; 1,5]", "DỪNG, BÁO"
    elif recovery["C_lo"] >= A2["recovery_min"] and ci["C_lo"][0] >= A2["ci_lower_min"]:
        branch, status = "ĐẠT — C_lo xác nhận trên bộ dài", "TIẾP"
    else:
        branch, status = "KHÔNG ĐẠT — C_lo chưa xác nhận", "BÁO"
    result = {"criteria": A2, "rows": LONG_IDS,
              "means": {name: round(means[name], 6) for name in means},
              "delta_ac": round(delta, 6),
              "recovery": {name: round(value, 4) if value is not None else None
                           for name, value in recovery.items()},
              "recovery_ci95": ci, "sum_lo_hi": round(sum_lo_hi, 4),
              "controls_ok": bool(controls_ok),
              "verdict": {"branch": branch, "status": status}}
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(json.dumps({key: result[key] for key in
                      ("means", "delta_ac", "recovery", "recovery_ci95",
                       "sum_lo_hi", "verdict")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
