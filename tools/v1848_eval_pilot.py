"""v18.48 — A4/A5: chấm PILOT vs CONTROL (và P2 tham chiếu) trên 40 câu V1847.A2.

TF: BAK, CR, L1 mel. Chunk: BAK. Bootstrap theo câu 10.000.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import yaml

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

OUT = Path("artifacts/bench/v1848_eval")
PILOT = Path("runs/v1848_pilot/last.pt")
CONTROL = Path("runs/v1848_control/last.pt")
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
N_BOOT = 10000


def contrast(raw: np.ndarray, vuv: np.ndarray, bins: np.ndarray) -> float:
    frames = min(raw.shape[0], vuv.size)
    if frames == 0 or not vuv[:frames].any():
        return float("nan")
    low = raw[:frames][vuv[:frames]][:, bins]
    if low.shape[1] < 5:
        return float("nan")
    windows = np.lib.stride_tricks.sliding_window_view(low, 5, axis=1)
    return float((windows.max(axis=2) - windows.min(axis=2)).mean())


def bootstrap_mean(values: np.ndarray) -> list[float]:
    rng = np.random.default_rng(0)
    means = [float(values[rng.integers(0, values.size, values.size)].mean())
             for _ in range(N_BOOT)]
    return [round(float(np.percentile(means, 2.5)), 4),
            round(float(np.percentile(means, 97.5)), 4)]


def bootstrap_median(values: np.ndarray) -> list[float]:
    rng = np.random.default_rng(0)
    med = [float(np.median(values[rng.integers(0, values.size, values.size)]))
           for _ in range(N_BOOT)]
    return [round(float(np.percentile(med, 2.5)), 4),
            round(float(np.percentile(med, 97.5)), 4)]


def load_engine(cfg: dict, checkpoint: Path | None, ema: dict | None = None) -> Synthesizer:
    engine = Synthesizer(cfg, str(checkpoint or P2), device="cpu")
    if ema is not None:
        missing, unexpected = engine.model.load_state_dict(ema, strict=False)
        if missing or unexpected:
            raise RuntimeError(f"EMA load lệch: missing={missing[:3]} unexpected={unexpected[:3]}")
    engine.model.eval()
    engine.vocoder.eval()
    return engine


def evaluate_model(engine: Synthesizer, dataset: TtsDataset, by_id: dict, cfg: dict,
                   label: str) -> list[dict]:
    stats = json.loads(Path(cfg["mel"]["normalize_path"]).read_text(encoding="utf-8"))
    mean = np.asarray(stats["mean"], dtype=np.float32)
    std = np.asarray(stats["std"], dtype=np.float32)
    _centers, lo, _hi = band_bins(24000, 1024, 100, 12000.0)
    rows = []
    for index, item_id in enumerate(IDS):
        row = dataset.rows[by_id[item_id]]
        item = dataset[by_id[item_id]]
        b_mel = item["mel"].detach().cpu().numpy().astype(np.float32)
        c_mel = predict_c_mel(engine, item["features"], row)
        frames = min(b_mel.shape[0], c_mel.shape[0])
        b_mel, c_mel = b_mel[:frames], c_mel[:frames]
        vuv = frame_vuv(row, item, frames)
        cr = (contrast(c_mel * std + mean, vuv, lo)
              / max(contrast(b_mel * std + mean, vuv, lo), 1e-12))
        tf_wave = render_mel(engine, c_mel, OUT / f"{label}_{index:02d}_TF.wav", 24000)
        chunk_path = OUT / f"{label}_{index:02d}_chunk.wav"
        engine.synthesize(row["text"], chunk_path, gate_threshold=0.5, sharpen_alpha=0.0,
                          target_lufs=-16, peak_normalize=False, max_chars=400)
        chunk_wave, _ = sf.read(chunk_path, dtype="float32")
        rows.append({"id": item_id, "tf_bak": bak(tf_wave, 24000),
                     "chunk_bak": bak(np.asarray(chunk_wave).reshape(-1), 24000),
                     "cr": round(float(cr), 6),
                     "l1_mel": round(float(np.mean(np.abs(c_mel - b_mel))), 6)})
        print(json.dumps({"model": label, "done": index + 1, "total": len(IDS)}),
              flush=True)
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    cfg = yaml.safe_load(Path(CFG32).read_text(encoding="utf-8"))
    dataset = TtsDataset(HOLDOUT, cfg, cache_dir=cfg.get("training", {}).get("cache_dir"))
    by_id = {row["id"]: i for i, row in enumerate(dataset.rows)}
    models = {
        "P2": load_engine(cfg, None),
        "CONTROL": load_engine(cfg, CONTROL, torch.load(CONTROL, map_location="cpu",
                                                        weights_only=False)["ema"]),
        "PILOT": load_engine(cfg, PILOT, torch.load(PILOT, map_location="cpu",
                                                    weights_only=False)["ema"]),
    }
    results = {name: evaluate_model(engine, dataset, by_id, cfg, name)
               for name, engine in models.items()}
    def arr(name, key):
        return np.asarray([row[key] for row in results[name]], dtype=float)
    delta_tf = arr("PILOT", "tf_bak") - arr("CONTROL", "tf_bak")
    delta_chunk = arr("PILOT", "chunk_bak") - arr("CONTROL", "chunk_bak")
    delta_cr = arr("PILOT", "cr") - arr("CONTROL", "cr")
    tf_ci = bootstrap_mean(delta_tf)
    chunk_ci = bootstrap_mean(delta_chunk)
    cr_ci = bootstrap_median(delta_cr)
    p2_tf = float(arr("P2", "tf_bak").mean())
    ctl_tf = float(arr("CONTROL", "tf_bak").mean())
    pilot_tf = float(arr("PILOT", "tf_bak").mean())
    p2_cr = float(np.median(arr("P2", "cr")))
    ctl_cr = float(np.median(arr("CONTROL", "cr")))
    pilot_cr = float(np.median(arr("PILOT", "cr")))
    l1_p = float(arr("PILOT", "l1_mel").mean())
    l1_c = float(arr("CONTROL", "l1_mel").mean())
    a4_1 = bool(delta_tf.mean() >= 0.05 and tf_ci[0] > 0)
    a4_2 = bool(pilot_cr > ctl_cr and cr_ci[0] > 0)
    a4_3 = bool(pilot_cr <= 1.05)
    a4 = a4_1 and a4_2 and a4_3
    weird = []
    if delta_tf.mean() > 0 and chunk_ci[1] < 0:
        weird.append("TF tăng nhưng chunk giảm (CI trên <0)")
    if l1_p > 1.10 * l1_c:
        weird.append("L1 mel PILOT tăng >10%")
    if pilot_cr > 1.05:
        weird.append("CR PILOT >1,05")
    if ctl_tf - p2_tf >= 0.05:
        weird.append("CONTROL tự tăng BAK ≥0,05 so P2")
    if delta_tf.mean() < 0 and tf_ci[1] < 0:
        verdict = "ĐÓNG hướng mượt tần số — pilot giảm BAK"
    elif not a4 and tf_ci[0] <= 0 <= tf_ci[1]:
        verdict = "KHÔNG KẾT LUẬN — đóng băng, không thử w khác"
    elif a4 and not weird:
        verdict = "ĐẠT — chờ A0, chưa đổi production"
    elif a4 and weird:
        verdict = "ĐẠT A4 nhưng A5 LẠ — dừng, báo"
    else:
        verdict = "KHÔNG ĐẠT — đóng băng"
    result = {
        "ids": IDS, "n": len(IDS),
        "summary": {
            "P2": {"tf_bak": round(p2_tf, 6), "cr_median": round(p2_cr, 6)},
            "CONTROL": {"tf_bak": round(ctl_tf, 6), "cr_median": round(ctl_cr, 6),
                        "chunk_bak": round(float(arr("CONTROL", "chunk_bak").mean()), 6),
                        "l1_mel": round(l1_c, 6)},
            "PILOT": {"tf_bak": round(pilot_tf, 6), "cr_median": round(pilot_cr, 6),
                      "chunk_bak": round(float(arr("PILOT", "chunk_bak").mean()), 6),
                      "l1_mel": round(l1_p, 6)},
        },
        "delta": {"tf_bak": round(float(delta_tf.mean()), 6), "tf_ci95": tf_ci,
                  "chunk_bak": round(float(delta_chunk.mean()), 6), "chunk_ci95": chunk_ci,
                  "cr_median": round(pilot_cr - ctl_cr, 6), "cr_ci95": cr_ci,
                  "l1_rel": round((l1_p - l1_c) / max(l1_c, 1e-12), 6)},
        "gates": {"a4_1_bak": a4_1, "a4_2_cr": a4_2, "a4_3_cr_cap": a4_3,
                  "a4_pass": a4, "a5_weird": weird},
        "verdict": verdict,
        "rows": results,
    }
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(json.dumps({key: result[key] for key in
                      ("summary", "delta", "gates", "verdict")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
