"""v18.49 — A2: tái lập chunk PILOT vs CONTROL trên 40 câu mới.

`--generate`: sinh WAV chunk + CR TF + metadata (chưa chấm BAK).
`--score`: chấm BAK, ΔBAK/ΔCR + bootstrap, verdict.
"""

from __future__ import annotations

import argparse
import hashlib
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
)
from tools.v1845_a5_smoothing import frame_vuv
from vifasttts.data.dataset import TtsDataset
from vifasttts.infer import Synthesizer

PILOT = Path("runs/v1848_pilot/last.pt")
CONTROL = Path("runs/v1848_control/last.pt")
OUT = Path("artifacts/bench/v1849_a2_chunk")
N_BOOT = 10000
IDS = [
    "2b65WyiFC9k_0299__s00", "2b65WyiFC9k_0093__s00", "2b65WyiFC9k_0151__s00",
    "2b65WyiFC9k_0165__s00", "4ITcvEa_Acc_0098__s02", "4ITcvEa_Acc_0029__s00",
    "4ITcvEa_Acc_0097__s01", "4ITcvEa_Acc_0214__s00", "BD83pScFukQ_0045__s00",
    "BD83pScFukQ_0037__s00", "BD83pScFukQ_0300__s00", "BD83pScFukQ_0161__s00",
    "EM_ObHWvd94_0345__s00", "EM_ObHWvd94_0349__s00", "EM_ObHWvd94_0006__s00",
    "EM_ObHWvd94_0114__s00", "EUNlJU1BuzE_0224__s00", "EUNlJU1BuzE_0113__s01",
    "EUNlJU1BuzE_0181__s00", "EUNlJU1BuzE_0101__s00", "o8RjAmBtyZo_0088__s02",
    "o8RjAmBtyZo_0194__s01", "o8RjAmBtyZo_0110__s01", "o8RjAmBtyZo_0099__s01",
    "vEtfty4Cc6Y_0102__s00", "vEtfty4Cc6Y_0257__s01", "vEtfty4Cc6Y_0033__s01",
    "vEtfty4Cc6Y_0030__s00", "z0zSgR_oie4_0056__s00", "z0zSgR_oie4_0078__s00",
    "z0zSgR_oie4_0246__s00", "z0zSgR_oie4_0099__s00", "EUNlJU1BuzE_0272__s00",
    "z0zSgR_oie4_0239__s00", "2b65WyiFC9k_0035__s00", "EM_ObHWvd94_0087__s01",
    "4ITcvEa_Acc_0092__s01", "BD83pScFukQ_0082__s01", "vEtfty4Cc6Y_0008__s02",
    "o8RjAmBtyZo_0084__s01",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def contrast(raw: np.ndarray, vuv: np.ndarray, bins: np.ndarray) -> float:
    frames = min(raw.shape[0], vuv.size)
    if frames == 0 or not vuv[:frames].any():
        return float("nan")
    low = raw[:frames][vuv[:frames]][:, bins]
    if low.shape[1] < 5:
        return float("nan")
    windows = np.lib.stride_tricks.sliding_window_view(low, 5, axis=1)
    return float((windows.max(axis=2) - windows.min(axis=2)).mean())


def engine_for(state_path: Path, cfg: dict) -> tuple[Synthesizer, dict]:
    state = torch.load(state_path, map_location="cpu", weights_only=False)
    if int(state.get("step", -1)) != 2000:
        raise RuntimeError(f"{state_path}: step {state.get('step')} != 2000")
    engine = Synthesizer(cfg, P2, device="cpu")
    missing, unexpected = engine.model.load_state_dict(state["ema"], strict=False)
    if missing or unexpected:
        raise RuntimeError(f"{state_path}: EMA lệch {missing[:3]} / {unexpected[:3]}")
    engine.model.eval()
    engine.vocoder.eval()
    return engine, state


def generate() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pilot").mkdir(exist_ok=True)
    (OUT / "control").mkdir(exist_ok=True)
    torch.set_num_threads(2)
    cfg = yaml.safe_load(Path(CFG32).read_text(encoding="utf-8"))
    stats = json.loads(Path(cfg["mel"]["normalize_path"]).read_text(encoding="utf-8"))
    mean = np.asarray(stats["mean"], dtype=np.float32)
    std = np.asarray(stats["std"], dtype=np.float32)
    _centers, lo, _hi = band_bins(24000, 1024, 100, 12000.0)
    dataset = TtsDataset(HOLDOUT, cfg, cache_dir=cfg.get("training", {}).get("cache_dir"))
    by_id = {row["id"]: i for i, row in enumerate(dataset.rows)}
    engines = {"pilot": engine_for(PILOT, cfg), "control": engine_for(CONTROL, cfg)}
    rows = []
    for index, item_id in enumerate(IDS):
        row = dataset.rows[by_id[item_id]]
        item = dataset[by_id[item_id]]
        b_mel = item["mel"].detach().cpu().numpy().astype(np.float32)
        vuv = frame_vuv(row, item, b_mel.shape[0])
        entry = {"id": item_id, "text": row["text"]}
        for name, (engine, _state) in engines.items():
            path = OUT / name / f"{index:02d}.wav"
            engine.synthesize(row["text"], path, gate_threshold=0.5, sharpen_alpha=0.0,
                              target_lufs=-16, peak_normalize=False, max_chars=400)
            c_mel = predict_c_mel(engine, item["features"], row)
            frames = min(b_mel.shape[0], c_mel.shape[0])
            cr = (contrast(c_mel[:frames] * std + mean, vuv[:frames], lo)
                  / max(contrast(b_mel[:frames] * std + mean, vuv[:frames], lo), 1e-12))
            entry[f"{name}_cr"] = round(float(cr), 6)
        rows.append(entry)
        print(json.dumps({"done": index + 1, "total": len(IDS)}), flush=True)
    pilot_run = json.loads(Path("runs/v1848_pilot/run.json").read_text())
    control_run = json.loads(Path("runs/v1848_control/run.json").read_text())
    meta = {
        "ids": IDS,
        "checkpoints": {
            "pilot": {"path": str(PILOT), "sha256": sha256(PILOT),
                      "step": 2000, "contrast_weight": pilot_run["args"]["contrast_weight"]},
            "control": {"path": str(CONTROL), "sha256": sha256(CONTROL),
                        "step": 2000, "contrast_weight": control_run["args"]["contrast_weight"]},
        },
        "rows": rows,
        "note": "WAV chunk -16 LUFS; CR TF tính từ cùng EMA; chưa chấm BAK.",
    }
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    print(json.dumps({"checkpoints": meta["checkpoints"], "n": len(rows)},
                     ensure_ascii=False, indent=1))


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


def score() -> None:
    meta = json.loads((OUT / "meta.json").read_text(encoding="utf-8"))
    pilot = []
    control = []
    for index, row in enumerate(meta["rows"]):
        p_wave, _ = sf.read(OUT / "pilot" / f"{index:02d}.wav", dtype="float32")
        c_wave, _ = sf.read(OUT / "control" / f"{index:02d}.wav", dtype="float32")
        pilot.append(bak(np.asarray(p_wave).reshape(-1), 24000))
        control.append(bak(np.asarray(c_wave).reshape(-1), 24000))
    pilot = np.asarray(pilot, dtype=float)
    control = np.asarray(control, dtype=float)
    delta_bak = pilot - control
    cr_pilot = np.asarray([row["pilot_cr"] for row in meta["rows"]], dtype=float)
    cr_control = np.asarray([row["control_cr"] for row in meta["rows"]], dtype=float)
    delta_cr = cr_pilot - cr_control
    bak_ci = bootstrap_mean(delta_bak)
    cr_ci = bootstrap_median(delta_cr)
    d_bak = float(delta_bak.mean())
    d_cr = float(np.median(delta_cr))
    if d_cr <= 0:
        verdict = "LẠ — ΔCR ≤ 0, checkpoint sai"
    elif bak_ci[0] > 0 and cr_ci[0] > 0:
        verdict = "ĐẠT — tái lập chunk + cơ chế CR"
    elif bak_ci[1] < 0:
        verdict = "ĐÓNG L_con — chunk giảm"
    else:
        verdict = "KHÔNG TÁI LẬP — CI chứa 0; đóng băng"
    result = {
        "ids": meta["ids"], "checkpoints": meta["checkpoints"],
        "n": len(meta["rows"]),
        "summary": {"pilot_bak": round(float(pilot.mean()), 6),
                    "control_bak": round(float(control.mean()), 6),
                    "pilot_cr_median": round(float(np.median(cr_pilot)), 6),
                    "control_cr_median": round(float(np.median(cr_control)), 6)},
        "delta": {"bak": round(d_bak, 6), "bak_ci95": bak_ci,
                  "cr_median": round(d_cr, 6), "cr_ci95": cr_ci},
        "expected_bak_range": [0.03, 0.06],
        "verdict": verdict,
    }
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(json.dumps({key: result[key] for key in
                      ("summary", "delta", "expected_bak_range", "verdict")},
                     ensure_ascii=False, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--generate", action="store_true")
    group.add_argument("--score", action="store_true")
    args = parser.parse_args()
    if args.generate:
        generate()
    else:
        score()


if __name__ == "__main__":
    main()
