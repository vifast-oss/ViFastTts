"""v18.46 — A4: tách cơ chế dải thấp trên 120 câu (80 cũ + 40 dài).

(a) C_lo_f: B làm mượt theo TRỤC TẦN SỐ, cửa sổ chọn theo độ tương phản phổ (không BAK).
(b) C_lo_m: C dải thấp + mean_t(B)-mean_t(C) theo từng bin/câu.
Chạy C, C_lo, C_lo_f, C_lo_m; R so với C_lo.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
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
    predict_c_mel,
    render_mel,
)
from tools.v1845_a5_smoothing import frame_vuv
from vifasttts.data.dataset import TtsDataset
from vifasttts.infer import Synthesizer

A43 = json.loads(Path("artifacts/bench/v1843_a4/result.json").read_text(encoding="utf-8"))
A45 = json.loads(Path("artifacts/bench/v1845_a4_new/result.json").read_text(encoding="utf-8"))
A5 = Path("artifacts/bench/v1845_a5")
A2 = json.loads(Path("artifacts/bench/v1846_a2_long/result.json").read_text(encoding="utf-8"))
OUT = Path("artifacts/bench/v1846_a4_mechanism")
WINDOW = OUT / "window.json"
MELS = OUT / "mels120.npz"
LONG_DIR = Path("artifacts/bench/v1846_a2_long")


def load_120() -> tuple[list[dict], dict]:
    cfg = yaml.safe_load(Path(CFG32).read_text(encoding="utf-8"))
    hop = int(cfg["mel"]["hop_length"])
    sr = int(cfg.get("sample_rate", 24000))
    old_meta = json.loads((A5 / "window.json").read_text(encoding="utf-8"))["items"]
    arrays = np.load(A5 / "mels.npz")
    items = []
    for index, meta in enumerate(old_meta):
        items.append({"id": meta["id"], "set": meta["set"], "index": meta["index"],
                      "b": arrays[f"{index}_b"], "c": arrays[f"{index}_c"],
                      "vuv": arrays[f"{index}_vuv"],
                      "seconds": None})
    dataset = TtsDataset(HOLDOUT, cfg, cache_dir=cfg.get("training", {}).get("cache_dir"))
    by_id = {row["id"]: i for i, row in enumerate(dataset.rows)}
    engine = Synthesizer(cfg, P2, device="cpu")
    engine.model.eval()
    engine.vocoder.eval()
    for index, item_id in enumerate(A2["rows"]):
        row = dataset.rows[by_id[item_id]]
        item = dataset[by_id[item_id]]
        b = item["mel"].detach().cpu().numpy().astype(np.float32)
        c = predict_c_mel(engine, item["features"], row)
        frames = min(b.shape[0], c.shape[0])
        items.append({"id": item_id, "set": "long", "index": index,
                      "b": b[:frames], "c": c[:frames],
                      "vuv": frame_vuv(row, item, frames),
                      "seconds": round((row["frame_range"][1] - row["frame_range"][0])
                                       * hop / sr, 3)})
    # seconds cho old từ manifest
    rows = {json.loads(line)["id"]: json.loads(line)
            for line in Path(HOLDOUT).read_text(encoding="utf-8").splitlines() if line.strip()}
    for item in items:
        if item["seconds"] is None:
            row = rows[item["id"]]
            item["seconds"] = round((row["frame_range"][1] - row["frame_range"][0])
                                    * hop / sr, 3)
    return items, cfg


def smooth_bins(mel: np.ndarray, window: int, bins: np.ndarray) -> np.ndarray:
    out = mel.copy()
    pad = window // 2
    low = mel[:, bins]
    padded = np.pad(low, ((0, 0), (pad, pad)), mode="edge")
    csum = np.cumsum(padded, axis=1)
    csum = np.hstack([np.zeros((csum.shape[0], 1), dtype=csum.dtype), csum])
    out[:, bins] = (csum[:, window:] - csum[:, :-window]) / window
    return out


def contrast(raw: np.ndarray, vuv: np.ndarray, bins: np.ndarray) -> float:
    frames = min(raw.shape[0], vuv.size)
    if frames == 0 or not vuv[:frames].any():
        return float("nan")
    low = raw[:frames][vuv[:frames]][:, bins]
    if low.shape[1] < 5:
        return float("nan")
    windows = np.lib.stride_tricks.sliding_window_view(low, 5, axis=1)
    values = windows.max(axis=2) - windows.min(axis=2)
    return float(values.mean())


def select_window() -> None:
    items, cfg = load_120()
    stats = json.loads(Path(cfg["mel"]["normalize_path"]).read_text(encoding="utf-8"))
    mean = np.asarray(stats["mean"], dtype=np.float32)
    std = np.asarray(stats["std"], dtype=np.float32)
    centers, lo, _hi = band_bins(24000, 1024, 100, 12000.0)
    target_c = []
    for item in items:
        raw_c = item["c"] * std + mean
        target_c.append(contrast(raw_c, item["vuv"], lo))
    target = float(np.nanmean(target_c))
    candidates = []
    for w in range(3, 20, 2):
        values = []
        for item in items:
            raw_b = item["b"] * std + mean
            smoothed = smooth_bins(raw_b, w, lo)
            values.append(contrast(smoothed, item["vuv"], lo))
        got = float(np.nanmean(values))
        rel = abs(got - target) / target if target > 1e-12 else 999.0
        candidates.append({"window": w, "contrast": round(got, 6),
                           "relative_error": round(rel, 6)})
    best = min(candidates, key=lambda x: x["relative_error"])
    approx = best["relative_error"] > 0.05
    OUT.mkdir(parents=True, exist_ok=True)
    arrays = {}
    for i, item in enumerate(items):
        for key in ("b", "c", "vuv"):
            arrays[f"{i}_{key}"] = item[key]
    np.savez_compressed(MELS, **arrays)
    window = {"target_c_contrast": round(target, 6), "chosen": best,
              "approximate": bool(approx), "tolerance_rel": 0.05,
              "low_bins": {"n": int(lo.size),
                           "center_first_last": [round(float(centers[lo[0]]), 1),
                                                 round(float(centers[lo[-1]]), 1)]},
              "items": [{"id": item["id"], "set": item["set"], "index": item["index"],
                         "seconds": item["seconds"]} for item in items],
              "note": "chọn theo độ tương phản phổ; chưa chấm BAK"}
    WINDOW.write_text(json.dumps(window, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"target": window["target_c_contrast"], "chosen": best,
                      "approximate": approx}, ensure_ascii=False, indent=1))


def score() -> None:
    window = json.loads(WINDOW.read_text(encoding="utf-8"))
    w = int(window["chosen"]["window"])
    arrays = np.load(MELS)
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
        b_f = smooth_bins(b, w, lo)
        c_lo_f = c.copy()
        c_lo_f[:, lo] = b_f[:, lo]
        c_lo_m = c.copy()
        c_lo_m[:, lo] = c[:, lo] + (b[:, lo].mean(axis=0) - c[:, lo].mean(axis=0))
        vals = {}
        for name, mel in (("C_lo", c_lo), ("C_lo_f", c_lo_f), ("C_lo_m", c_lo_m)):
            wave = render_mel(engine, mel, OUT / f"{index:02d}_{name}.wav", 24000)
            vals[name] = bak(wave, 24000)
        rows.append({"id": item["id"], "set": item["set"], **vals})
        print(json.dumps({"done": index + 1, "total": len(items)}), flush=True)
    # BAK C từ wav có sẵn
    c_vals = []
    for item in items:
        if item["set"] == "long":
            path = LONG_DIR / f"{item['index']:02d}_C.wav"
        elif item["set"] == "new":
            path = Path("artifacts/bench/v1845_a4_new") / f"{item['index']:02d}_C.wav"
        else:
            path = Path("artifacts/bench/v1843_a4") / f"{item['index']:02d}_C.wav"
        c_vals.append(bak(__import__("soundfile").read(path, dtype="float32")[0], 24000))
    b_vals = ([row["metrics"]["B"]["bak"] for row in A43["rows"]]
              + list(A45["baks"]["B"]) + [A2["means"]["B"]] * len(A2["rows"]))
    c_mean = float(np.mean(c_vals))
    b_mean = float(np.mean(b_vals))
    delta = b_mean - c_mean
    means = {name: float(np.mean([row[name] for row in rows]))
             for name in ("C_lo", "C_lo_f", "C_lo_m")}
    r_lo = (means["C_lo"] - c_mean) / delta if abs(delta) > 1e-12 else None
    r_f = (means["C_lo_f"] - c_mean) / delta if abs(delta) > 1e-12 else None
    r_m = (means["C_lo_m"] - c_mean) / delta if abs(delta) > 1e-12 else None
    main_f = r_f is not None and r_lo is not None and r_f <= 0.3 * r_lo
    main_m = r_m is not None and r_lo is not None and r_m >= 0.7 * r_lo
    weird = ((r_f is not None and r_lo is not None and r_f > r_lo + 0.1)
             or (r_m is not None and r_lo is not None and r_m > r_lo + 0.1))
    if weird:
        branch, status = "LẠ — một biến thể tốt hơn C_lo >0,1", "DỪNG, BÁO"
    elif main_f and main_m:
        branch, status = "CẢ HAI — mượt tần số + lệch mức", "TIẾP"
    elif main_f:
        branch, status = "MƯỢT TẦN SỐ CHÍNH", "TIẾP"
    elif main_m:
        branch, status = "LỆCH MỨC CHÍNH", "TIẾP"
    else:
        branch, status = "KHÔNG XÁC ĐỊNH", "BÁO"
    result = {"window": w, "approximate": window["approximate"],
              "means": {"B": round(b_mean, 6), "C": round(c_mean, 6),
                        **{name: round(value, 6) for name, value in means.items()}},
              "delta_ac": round(delta, 6),
              "recovery": {"C_lo": r_lo, "C_lo_f": r_f, "C_lo_m": r_m},
              "main": {"frequency_smoothing": main_f, "level_offset": main_m},
              "rows": rows, "verdict": {"branch": branch, "status": status}}
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(json.dumps({key: result[key] for key in
                      ("means", "delta_ac", "recovery", "main", "verdict")},
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
