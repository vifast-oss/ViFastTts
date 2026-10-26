"""v18.45 — A5: tách over-smoothing theo thời gian ở dải thấp.

Bước 1 `--select-window`: chọn cửa sổ trung bình trượt (lẻ) CHỈ theo GV ratio, không chấm BAK.
Bước 2 `--score`: dùng cửa sổ đã ghi, render C_lo / C_lo_s trên 80 câu, chấm BAK, verdict.

GV ratio dải = var(mel dải, frame hữu thanh) / var(mel gốc cùng dải). Mục tiêu là GV ratio
của P2 (C/B) cho 2 dải thấp; cửa sổ làm mượt B sao cho khớp ±0,03.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
import yaml

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.v1845_a4_confirm import (
    CFG32,
    HOLDOUT,
    NEW_IDS,
    P2,
    bak,
    band_bins,
    predict_c_mel,
    render_mel,
)
from vifasttts.data.dataset import TtsDataset
from vifasttts.infer import Synthesizer

OLD_A4 = Path("artifacts/bench/v1843_a4/result.json")
NEW_DIR = Path("artifacts/bench/v1845_a4_new")
OUT = Path("artifacts/bench/v1845_a5")
WINDOW_JSON = OUT / "window.json"
MELS_NPZ = OUT / "mels.npz"
N_BOOT = 10000


def frame_vuv(row: dict, item: dict, frames: int) -> np.ndarray:
    vuv = np.asarray(item.get("vuv", torch.zeros(item["features"].size(0))).cpu()).reshape(-1)
    durations = row["durations"]
    gaps = list(row.get("gaps") or [])
    if len(gaps) == len(durations) - 1:
        gaps = gaps + [0]
    out = [False] * int(row.get("lead_frames") or 0)
    for index, (duration, gap) in enumerate(zip(durations, gaps[:len(durations)])):
        out.extend([bool(vuv[index] > 0.5)] * int(duration))
        out.extend([False] * int(gap))
    return np.asarray(out[:frames], dtype=bool)


def load_items() -> list[dict]:
    cfg = yaml.safe_load(Path(CFG32).read_text(encoding="utf-8"))
    dataset = TtsDataset(HOLDOUT, cfg, cache_dir=cfg.get("training", {}).get("cache_dir"))
    by_id = {row["id"]: index for index, row in enumerate(dataset.rows)}
    engine = Synthesizer(cfg, P2, device="cpu")
    engine.model.eval()
    engine.vocoder.eval()
    old = json.loads(OLD_A4.read_text(encoding="utf-8"))["rows"]
    items = []
    for index, row in enumerate(old):
        dataset_row = dataset.rows[by_id[row["id"]]]
        item = dataset[by_id[row["id"]]]
        b_mel = item["mel"].detach().cpu().numpy().astype(np.float32)
        c_mel = predict_c_mel(engine, item["features"], dataset_row)
        frames = min(b_mel.shape[0], c_mel.shape[0])
        items.append({"id": row["id"], "set": "old", "index": index,
                      "b": b_mel[:frames], "c": c_mel[:frames],
                      "vuv": frame_vuv(dataset_row, item, frames)})
    for index, item_id in enumerate(NEW_IDS):
        dataset_row = dataset.rows[by_id[item_id]]
        item = dataset[by_id[item_id]]
        b_mel = item["mel"].detach().cpu().numpy().astype(np.float32)
        c_mel = predict_c_mel(engine, item["features"], dataset_row)
        frames = min(b_mel.shape[0], c_mel.shape[0])
        items.append({"id": item_id, "set": "new", "index": index,
                      "b": b_mel[:frames], "c": c_mel[:frames],
                      "vuv": frame_vuv(dataset_row, item, frames)})
    return items


def band_var(values: np.ndarray, voiced: np.ndarray, bins: np.ndarray) -> float:
    frames = min(values.shape[0], voiced.size)
    if frames == 0 or not voiced[:frames].any() or bins.size == 0:
        return float("nan")
    return float(np.var(values[:frames][voiced[:frames]][:, bins], axis=0).mean())


def smooth_low(values: np.ndarray, window: int, low_bins: np.ndarray) -> np.ndarray:
    out = values.copy()
    pad = window // 2
    low = values[:, low_bins]
    padded = np.pad(low, ((pad, pad), (0, 0)), mode="edge")
    csum = np.cumsum(padded, axis=0)
    csum = np.vstack([np.zeros((1, csum.shape[1]), dtype=csum.dtype), csum])
    out[:, low_bins] = (csum[window:] - csum[:-window]) / window
    return out


def select_window() -> dict:
    items = load_items()
    centers, lo, _hi = band_bins(24000, 1024, 100, 12000.0)
    band_map = {"<1k": np.where(centers < 1000)[0],
                "1-4k": np.where((centers >= 1000) & (centers <= 4000))[0]}
    target = {}
    for name, bins in band_map.items():
        c_vals = [band_var(item["c"], item["vuv"], bins) for item in items]
        b_vals = [band_var(item["b"], item["vuv"], bins) for item in items]
        ratios = [c / b for c, b in zip(c_vals, b_vals) if b > 1e-12 and np.isfinite(c)]
        target[name] = round(float(np.mean(ratios)), 4) if ratios else None
    candidates = []
    for window in range(3, 32, 2):
        achieved = {}
        for name, bins in band_map.items():
            ratios = []
            for item in items:
                smoothed = smooth_low(item["b"], window, lo)
                sv = band_var(smoothed, item["vuv"], bins)
                bv = band_var(item["b"], item["vuv"], bins)
                if bv > 1e-12 and np.isfinite(sv):
                    ratios.append(sv / bv)
            achieved[name] = round(float(np.mean(ratios)), 4) if ratios else None
        diffs = [abs(achieved[name] - target[name]) for name in target
                 if achieved[name] is not None and target[name] is not None]
        max_diff = max(diffs) if diffs else 999.0
        candidates.append({"window": window, "achieved": achieved,
                           "max_abs_diff": round(max_diff, 4)})
    best = min(candidates, key=lambda row: row["max_abs_diff"])
    approximate = best["max_abs_diff"] > 0.03
    OUT.mkdir(parents=True, exist_ok=True)
    arrays = {f"{i}_b": item["b"] for i, item in enumerate(items)}
    arrays.update({f"{i}_c": item["c"] for i, item in enumerate(items)})
    arrays.update({f"{i}_vuv": item["vuv"] for i, item in enumerate(items)})
    np.savez_compressed(MELS_NPZ, **arrays)
    result = {
        "target_gv_ratio": target,
        "chosen": best,
        "approximate": bool(approximate),
        "tolerance": 0.03,
        "low_bin_indices": {"n": int(lo.size),
                            "center_first_last": [round(float(centers[lo[0]]), 1),
                                                  round(float(centers[lo[-1]]), 1)]},
        "items": [{"id": item["id"], "set": item["set"], "index": item["index"]}
                  for item in items],
        "candidates": candidates,
        "note": "Cửa sổ chỉ chọn theo GV; BAK chưa được chấm ở bước này.",
    }
    WINDOW_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"target": target, "chosen": best, "approximate": approximate},
                     ensure_ascii=False, indent=1))


def score() -> None:
    window = json.loads(WINDOW_JSON.read_text(encoding="utf-8"))
    w = int(window["chosen"]["window"])
    arrays = np.load(MELS_NPZ)
    items = window["items"]
    _centers, lo, _hi = band_bins(24000, 1024, 100, 12000.0)
    cfg = yaml.safe_load(Path(CFG32).read_text(encoding="utf-8"))
    engine = Synthesizer(cfg, P2, device="cpu")
    engine.model.eval()
    engine.vocoder.eval()
    rows = []
    for index, item in enumerate(items):
        b = arrays[f"{index}_b"]
        c = arrays[f"{index}_c"]
        c_lo = c.copy()
        c_lo[:, lo] = b[:, lo]
        b_smooth = smooth_low(b, w, lo)
        c_lo_s = c.copy()
        c_lo_s[:, lo] = b_smooth[:, lo]
        values = {}
        for name, mel in (("C", c), ("C_lo", c_lo), ("C_lo_s", c_lo_s)):
            wave = render_mel(engine, mel, OUT / f"{index:02d}_{name}.wav", 24000)
            values[name] = bak(wave, 24000)
        rows.append({"id": item["id"], "set": item["set"], **values})
        print(json.dumps({"done": index + 1, "total": len(items)}), flush=True)
    c_mean = float(np.mean([row["C"] for row in rows]))
    lo_mean = float(np.mean([row["C_lo"] for row in rows]))
    s_mean = float(np.mean([row["C_lo_s"] for row in rows]))
    # Δac dùng B từ dữ liệu A4: lấy BAK(B) từ A4 cũ/mới tương ứng
    old = json.loads(OLD_A4.read_text(encoding="utf-8"))["rows"]
    old_bak = [row["metrics"]["B"]["bak"] for row in old]
    new = json.loads((NEW_DIR / "result.json").read_text(encoding="utf-8"))
    new_bak = new["baks"]["B"]
    b_mean = float(np.mean(old_bak + new_bak))
    delta = b_mean - c_mean
    rec_lo = (lo_mean - c_mean) / delta if abs(delta) > 1e-12 else None
    rec_s = (s_mean - c_mean) / delta if abs(delta) > 1e-12 else None
    ratio = rec_s / rec_lo if rec_lo and abs(rec_lo) > 1e-12 else None
    if ratio is None:
        verdict, status = "KHÔNG TÍNH ĐƯỢC", "BÁO"
    elif rec_s > rec_lo + 0.1:
        verdict, status = "LẠ — C_lo_s tốt hơn C_lo > 0,1", "DỪNG, BÁO"
    elif ratio <= 0.3:
        verdict, status = "OVER-SMOOTHING CHÍNH", "TIẾP"
    elif ratio >= 0.7:
        verdict, status = "KHÔNG PHẢI OVER-SMOOTHING", "BÁO"
    else:
        verdict, status = "HỖN HỢP", "TIẾP"
    result = {"window": w, "approximate": window["approximate"],
              "means": {"B": round(b_mean, 6), "C": round(c_mean, 6),
                        "C_lo": round(lo_mean, 6), "C_lo_s": round(s_mean, 6)},
              "delta_ac": round(delta, 6), "recovery": {"C_lo": rec_lo, "C_lo_s": rec_s},
              "ratio_s_over_lo": ratio, "rows": rows,
              "verdict": {"branch": verdict, "status": status}}
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(json.dumps({key: result[key] for key in
                      ("means", "delta_ac", "recovery", "ratio_s_over_lo", "verdict")},
                     ensure_ascii=False, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--select-window", action="store_true")
    group.add_argument("--score", action="store_true")
    args = parser.parse_args()
    if args.select_window:
        select_window()
    else:
        score()


if __name__ == "__main__":
    main()
