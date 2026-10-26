"""v18.47 — A2: đo trực tiếp CR độ tương phản phổ ≤4 kHz (P2 TF / mel gốc).

CR = contrast(C) / contrast(B); contrast = trung bình (max−min) log-mel trong cửa sổ 5 bin,
chỉ frame hữu thanh. Spearman giữa (1−CR) và BAK(B)−BAK(C), bootstrap CI95 10.000.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch
import yaml
from scipy.stats import spearmanr

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.v1845_a4_confirm import (
    CFG32,
    HOLDOUT,
    P2,
    bak,
    band_bins,
    predict_c_mel,
    render_mel,
)
from tools.v1845_a5_smoothing import frame_vuv
from vifasttts.data.dataset import TtsDataset
from vifasttts.infer import Synthesizer

OUT = Path("artifacts/bench/v1847_a2_contrast")
N_BOOT = 10000
IDS = [
    "2b65WyiFC9k_0032__s00", "2b65WyiFC9k_0202__s01", "2b65WyiFC9k_0080__s01",
    "2b65WyiFC9k_0322__s01", "4ITcvEa_Acc_0046__s00", "4ITcvEa_Acc_0204__s00",
    "4ITcvEa_Acc_0219__s00", "4ITcvEa_Acc_0165__s02", "BD83pScFukQ_0038__s00",
    "BD83pScFukQ_0162__s00", "BD83pScFukQ_0014__s00", "BD83pScFukQ_0094__s00",
    "EM_ObHWvd94_0017__s00", "EM_ObHWvd94_0140__s00", "EM_ObHWvd94_0090__s01",
    "EM_ObHWvd94_0159__s00", "EUNlJU1BuzE_0095__s00", "EUNlJU1BuzE_0262__s00",
    "EUNlJU1BuzE_0044__s01", "EUNlJU1BuzE_0116__s00", "VeU_85bZlrY_0034__s01",
    "VeU_85bZlrY_0129__s04", "VeU_85bZlrY_0126__s00", "o8RjAmBtyZo_0177__s01",
    "o8RjAmBtyZo_0208__s02", "o8RjAmBtyZo_0208__s00", "o8RjAmBtyZo_0065__s00",
    "vEtfty4Cc6Y_0277__s00", "vEtfty4Cc6Y_0063__s01", "vEtfty4Cc6Y_0190__s00",
    "vEtfty4Cc6Y_0059__s00", "z0zSgR_oie4_0141__s00", "z0zSgR_oie4_0050__s00",
    "z0zSgR_oie4_0230__s00", "z0zSgR_oie4_0241__s00", "EUNlJU1BuzE_0223__s00",
    "z0zSgR_oie4_0218__s00", "4ITcvEa_Acc_0226__s00", "2b65WyiFC9k_0089__s00",
    "BD83pScFukQ_0222__s00",
]


def contrast(raw: np.ndarray, vuv: np.ndarray, bins: np.ndarray) -> float:
    frames = min(raw.shape[0], vuv.size)
    if frames == 0 or not vuv[:frames].any():
        return float("nan")
    low = raw[:frames][vuv[:frames]][:, bins]
    if low.shape[1] < 5:
        return float("nan")
    windows = np.lib.stride_tricks.sliding_window_view(low, 5, axis=1)
    return float((windows.max(axis=2) - windows.min(axis=2)).mean())


def bootstrap_median(values: np.ndarray) -> list[float]:
    rng = np.random.default_rng(0)
    med = [float(np.median(values[rng.integers(0, values.size, values.size)]))
           for _ in range(N_BOOT)]
    return [round(float(np.percentile(med, 2.5)), 4),
            round(float(np.percentile(med, 97.5)), 4)]


def bootstrap_rho(x: np.ndarray, y: np.ndarray) -> list[float]:
    rng = np.random.default_rng(0)
    values = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, x.size, x.size)
        rho = spearmanr(x[idx], y[idx]).statistic
        if np.isfinite(rho):
            values.append(float(rho))
    return [round(float(np.percentile(values, 2.5)), 4),
            round(float(np.percentile(values, 97.5)), 4)]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    cfg = yaml.safe_load(Path(CFG32).read_text(encoding="utf-8"))
    stats = json.loads(Path(cfg["mel"]["normalize_path"]).read_text(encoding="utf-8"))
    mean = np.asarray(stats["mean"], dtype=np.float32)
    std = np.asarray(stats["std"], dtype=np.float32)
    _centers, lo, _hi = band_bins(24000, 1024, 100, 12000.0)
    dataset = TtsDataset(HOLDOUT, cfg, cache_dir=cfg.get("training", {}).get("cache_dir"))
    by_id = {row["id"]: i for i, row in enumerate(dataset.rows)}
    engine = Synthesizer(cfg, P2, device="cpu")
    engine.model.eval()
    engine.vocoder.eval()
    rows = []
    for index, item_id in enumerate(IDS):
        row = dataset.rows[by_id[item_id]]
        item = dataset[by_id[item_id]]
        b = item["mel"].detach().cpu().numpy().astype(np.float32)
        c = predict_c_mel(engine, item["features"], row)
        frames = min(b.shape[0], c.shape[0])
        b, c = b[:frames], c[:frames]
        vuv = frame_vuv(row, item, frames)
        cb = contrast(b * std + mean, vuv, lo)
        cc = contrast(c * std + mean, vuv, lo)
        cr = cc / cb if cb > 1e-12 else float("nan")
        b_wave = render_mel(engine, b, OUT / f"{index:02d}_B.wav", 24000)
        c_wave = render_mel(engine, c, OUT / f"{index:02d}_C.wav", 24000)
        bb = bak(b_wave, 24000)
        cc_bak = bak(c_wave, 24000)
        rows.append({"id": item_id, "contrast_B": round(cb, 6),
                     "contrast_C": round(cc, 6), "CR": round(cr, 6),
                     "bak_B": bb, "bak_C": cc_bak,
                     "d_bak": round(bb - cc_bak, 6)})
        print(json.dumps({"done": index + 1, "total": len(IDS)}), flush=True)
    cr = np.asarray([row["CR"] for row in rows], dtype=float)
    dbak = np.asarray([row["d_bak"] for row in rows], dtype=float)
    median = float(np.median(cr))
    med_ci = bootstrap_median(cr)
    rho = float(spearmanr(1.0 - cr, dbak).statistic)
    rho_ci = bootstrap_rho(1.0 - cr, dbak)
    cond_a = bool(median <= 0.95 and med_ci[1] < 1.0)
    cond_b = bool(rho >= 0.3 and (rho_ci[0] > 0 or rho_ci[1] < 0))
    weird = bool(median > 1.0)
    if weird:
        verdict = "LẠ — CR trung vị >1,0; dừng"
    elif cond_a and cond_b:
        verdict = "ĐẠT — P2 mượt tần số và giải thích BAK"
    elif cond_a:
        verdict = "CHỈ (a) ĐẠT — model mượt nhưng không giải thích BAK; giữ đóng băng"
    else:
        verdict = "KHÔNG ĐẠT — giữ đóng băng"
    result = {"ids": IDS, "rows": rows, "n": len(rows),
              "median_CR": round(median, 6), "median_CR_ci95": med_ci,
              "rho_1mCR_vs_dBAK": round(rho, 6), "rho_ci95": rho_ci,
              "cond_a": cond_a, "cond_b": cond_b, "weird": weird,
              "verdict": verdict, "bootstrap": N_BOOT}
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(json.dumps({key: result[key] for key in
                      ("n", "median_CR", "median_CR_ci95", "rho_1mCR_vs_dBAK",
                       "rho_ci95", "cond_a", "cond_b", "weird", "verdict")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
