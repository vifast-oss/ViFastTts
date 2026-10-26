"""v18.50 — A4: bảng đặc trưng âm tiết A/B/P2 + điểm creak (chưa nối nhãn).

Creak dùng 3 kênh của `eval_creak` (hnr, glottalization, jitter) trên nucleus;
điểm = trung bình z(-hnr)+z(glottal)+z(jitter) trên toàn bộ A/B/P2.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import torch
import yaml
from scipy.signal import stft

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.v1845_a4_confirm import CFG32, HOLDOUT, P2, band_bins
from vifasttts.data.dataset import TtsDataset
from vifasttts.data.features import extract_features
from vifasttts.infer import Synthesizer

KEY = Path("artifacts/bench/v1850_mark/key.json")
OUT = Path("artifacts/bench/v1850_features")
STOP_CODAS = {"P", "T", "C", "CH", "K"}
TONES_CREAK = {"NGA", "NANG"}


def flatness(path: Path, start_frame: int, frames: int) -> float:
    import soundfile as sf

    wave, _sr = sf.read(path, dtype="float32")
    wave = np.asarray(wave).reshape(-1)
    _f, _t, spec = stft(wave, fs=24000, nperseg=1024, noverlap=768, boundary=None, padded=False)
    freq = np.linspace(0, 12000, spec.shape[0])
    band = (freq >= 2000) & (freq <= 8000)
    mag = np.abs(spec[band]) + 1e-12
    flat = np.exp(np.mean(np.log(mag), axis=0)) / np.mean(mag, axis=0)
    lo = max(0, start_frame)
    hi = min(flat.size, lo + max(frames, 1))
    return float(np.mean(flat[lo:hi])) if hi > lo else float("nan")


def contrast(raw: np.ndarray, start: int, frames: int, bins: np.ndarray) -> float:
    lo = max(0, start)
    hi = min(raw.shape[0], lo + max(frames, 1))
    if hi - lo < 1 or bins.size < 5:
        return float("nan")
    low = raw[lo:hi][:, bins]
    windows = np.lib.stride_tricks.sliding_window_view(low, 5, axis=1)
    return float((windows.max(axis=2) - windows.min(axis=2)).mean())


def gt_windows(row: dict) -> list[tuple[int, int]]:
    seg = row["seg_durations"]
    gaps = list(row.get("gaps") or [])
    cursor = int(row.get("lead_frames") or 0)
    out = []
    for k, (o, m, n, c) in enumerate(seg):
        out.append((cursor + int(o) + int(m), int(n)))
        cursor += int(o) + int(m) + int(n) + int(c)
        if k < len(gaps):
            cursor += int(gaps[k])
    return out


def pred_windows(engine: Synthesizer, item: dict) -> tuple[list[tuple[int, int]], list[int]]:
    with torch.no_grad():
        out = engine.model(item["features"].unsqueeze(0), gate_threshold=0.5)
    pred_durations = [int(x) for x in out["durations"][0].tolist()]
    slots = [int(x) for x in out["slot_durations"][0].tolist()]
    cursor = slots[0]
    windows = []
    for k in range((len(slots) - 1) // 5):
        o, m, n, c, gap = slots[1 + 5 * k:6 + 5 * k]
        windows.append((cursor + o + m, n))
        cursor += o + m + n + c + gap
    return windows, pred_durations


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    cfg = yaml.safe_load(Path(CFG32).read_text(encoding="utf-8"))
    dataset = TtsDataset(HOLDOUT, cfg, cache_dir=cfg.get("training", {}).get("cache_dir"))
    by_id = {row["id"]: i for i, row in enumerate(dataset.rows)}
    key = json.loads(KEY.read_text(encoding="utf-8"))
    main_items = [x for x in key["items"] if x["kind"] == "main"]
    by_sentence = {}
    for item in main_items:
        by_sentence.setdefault(item["sentence"], {})[item["version"]] = item
    engine = Synthesizer(cfg, P2, device="cpu")
    engine.model.eval()
    _centers, lo, _hi = band_bins(24000, 1024, 100, 12000.0)
    table = []
    for sentence, versions in by_sentence.items():
        i = by_id[sentence]
        row = dataset.rows[i]
        item = dataset[i]
        p2_windows, p2_durations = pred_windows(engine, item)
        windows = {"A": gt_windows(row), "B": gt_windows(row), "P2": p2_windows}
        per = {}
        for version in ("A", "B", "P2"):
            path = Path(versions[version]["path"])
            feats = extract_features(path, cfg)
            mel = np.asarray(feats["mel"].cpu(), dtype=np.float32)
            f0 = np.asarray(feats["f0"].cpu(), dtype=float).reshape(-1)
            vuv = np.asarray(feats["vuv"].cpu(), dtype=float).reshape(-1) > 0.5
            hnr = np.asarray(feats["hnr"].cpu(), dtype=float).reshape(-1)
            glot = np.asarray(feats["glottalization"].cpu(), dtype=float).reshape(-1)
            jitter = np.asarray(feats["jitter"].cpu(), dtype=float).reshape(-1)
            rows = []
            for k, (start, frames) in enumerate(windows[version]):
                end = min(start + frames, mel.shape[0])
                if start >= end:
                    continue
                f_end = min(end, f0.size)
                seg_f0 = f0[start:f_end][vuv[start:f_end]]
                syl = row["syllables"][k]
                abstract = syl.get("abstract", {})
                raw = syl.get("raw", "")
                rows.append({
                    "index": k + 1, "text": syl.get("normalized", raw),
                    "hnr": float(np.mean(hnr[start:min(end, hnr.size)])),
                    "glottalization": float(np.mean(glot[start:min(end, glot.size)])),
                    "jitter": float(np.mean(jitter[start:min(end, jitter.size)])),
                    "flatness_2_8k": flatness(path, start, frames),
                    "contrast": contrast(mel, start, frames, lo),
                    "f0_hz": float(np.median(seg_f0)) if seg_f0.size else None,
                    "coda_stop": bool(abstract.get("coda") in STOP_CODAS),
                    "tone": abstract.get("tone"), "oov": syl.get("status") != "VALID",
                    "abbrev_number": bool(re.fullmatch(r"[A-Z0-9.%]+", raw)),
                    **({"duration_pred": p2_durations[k],
                        "duration_gt": int(row["durations"][k]),
                        "duration_ratio": round(p2_durations[k]
                                                / max(int(row["durations"][k]), 1), 4)}
                       if version == "P2" and k < len(p2_durations) else {}),
                })
            per[version] = rows
        # creak z trên toàn bộ A/B/P2
        channels = {"hnr": [], "glottalization": [], "jitter": []}
        for rows_v in per.values():
            for row_syl in rows_v:
                for ch, vals in channels.items():
                    vals.append(row_syl[ch])
        stats = {ch: (float(np.mean(v)), float(np.std(v) + 1e-9)) for ch, v in channels.items()}
        for rows_v in per.values():
            for row_syl in rows_v:
                z_hnr = (row_syl["hnr"] - stats["hnr"][0]) / stats["hnr"][1]
                z_g = (row_syl["glottalization"] - stats["glottalization"][0]) / stats["glottalization"][1]
                z_j = (row_syl["jitter"] - stats["jitter"][0]) / stats["jitter"][1]
                row_syl["creak"] = round(float(-z_hnr + z_g + z_j), 4)
        # F0 jump P2
        for k, row_syl in enumerate(per["P2"]):
            jumps = []
            for other in (k - 1, k + 1):
                if 0 <= other < len(per["P2"]):
                    a, b = row_syl.get("f0_hz"), per["P2"][other].get("f0_hz")
                    if a and b:
                        jumps.append(abs(1200 * np.log2(b / a)))
            row_syl["f0_jump_cents"] = round(max(jumps), 2) if jumps else None
        table.append({"sentence": sentence, "n": len(per["P2"]),
                      "A": per["A"], "B": per["B"], "P2": per["P2"]})
        print(json.dumps({"done": sentence, "n": len(per["P2"])}), flush=True)
    (OUT / "table.json").write_text(json.dumps({"creak_stats": stats, "table": table},
                                               ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"sentences": len(table), "creak_stats": stats}, ensure_ascii=False,
                     indent=1))


if __name__ == "__main__":
    main()
