"""v18.45 — A4: xác nhận C_lo trên 40 câu held-out MỚI (khác A4 V18.43).

Chạy C_none, C_all, C_lo, C_hi. Recovery gộp = (mean BAK(X) - mean BAK(C)) / Δac.
CI95 bootstrap theo câu 10.000 lần, lấy tử và mẫu trên cùng mẫu câu.
Không dùng tỉ số từng câu; báo thêm median hiệu BAK(C_lo) - BAK(C).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import torch
import yaml
from scipy.signal import resample_poly

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("VIFASTT_INTRA_THREADS", "2")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

from vifasttts.data.dataset import TtsDataset
from vifasttts.data.features import mel_filterbank
from vifasttts.infer import Synthesizer, _apply_target_lufs, write_wav
from vifasttts.runtime.postprocess import postprocess

CFG32 = "configs/small_codelung_v32.yaml"
P2 = "artifacts/listen_small_filt/adv_progress_p2/_ckpt/step_02000.pt"
HOLDOUT = "data/codelung/v32/holdout_clean_v2_dur_seg_slot4.jsonl"
OUT = Path("artifacts/bench/v1845_a4_new")
N_BOOT = 10000

NEW_IDS = [
    "2b65WyiFC9k_0004__s02", "2b65WyiFC9k_0069__s00", "2b65WyiFC9k_0154__s00",
    "2b65WyiFC9k_0237__s02", "4ITcvEa_Acc_0014__s00", "4ITcvEa_Acc_0055__s01",
    "4ITcvEa_Acc_0142__s00", "4ITcvEa_Acc_0193__s02", "BD83pScFukQ_0002__s01",
    "BD83pScFukQ_0097__s00", "BD83pScFukQ_0214__s00", "BD83pScFukQ_0315__s00",
    "EM_ObHWvd94_0002__s00", "EM_ObHWvd94_0085__s03", "EM_ObHWvd94_0177__s00",
    "EM_ObHWvd94_0259__s00", "EUNlJU1BuzE_0002__s00", "EUNlJU1BuzE_0085__s03",
    "EUNlJU1BuzE_0173__s01", "EUNlJU1BuzE_0259__s02", "VeU_85bZlrY_0034__s00",
    "VeU_85bZlrY_0037__s00", "VeU_85bZlrY_0037__s04", "VeU_85bZlrY_0129__s01",
    "o8RjAmBtyZo_0002__s00", "o8RjAmBtyZo_0075__s02", "o8RjAmBtyZo_0130__s01",
    "o8RjAmBtyZo_0178__s01", "vEtfty4Cc6Y_0005__s00", "vEtfty4Cc6Y_0068__s00",
    "vEtfty4Cc6Y_0162__s03", "vEtfty4Cc6Y_0239__s04", "z0zSgR_oie4_0001__s00",
    "z0zSgR_oie4_0059__s01", "z0zSgR_oie4_0138__s04", "z0zSgR_oie4_0204__s00",
    "BD83pScFukQ_0002__s02", "vEtfty4Cc6Y_0005__s01", "2b65WyiFC9k_0004__s03",
    "z0zSgR_oie4_0001__s02",
]

A4 = {"delta_min": 0.15, "recovery_min": 0.5, "ci_lower_min": 0.3,
      "sum_min": 0.5, "sum_max": 1.5, "control_tol": 0.02}


def normalize_lufs(wave: np.ndarray, sample_rate: int = 24000) -> np.ndarray:
    wave = postprocess(np.asarray(wave, dtype=np.float32), sample_rate)
    return np.asarray(_apply_target_lufs(wave, sample_rate, -16.0), dtype=np.float32)


def render_mel(engine: Synthesizer, mel: np.ndarray, path: Path,
               sample_rate: int = 24000) -> np.ndarray:
    tensor = torch.from_numpy(np.asarray(mel, dtype=np.float32)).unsqueeze(0)
    with torch.no_grad():
        wave = engine.vocoder(tensor)[0].detach().cpu().numpy()
    wave = normalize_lufs(wave, sample_rate)
    write_wav(path, wave, sample_rate)
    return wave


def predict_c_mel(engine: Synthesizer, features: torch.Tensor, row: dict) -> np.ndarray:
    n = features.size(0)
    durations = torch.tensor(row["durations"], dtype=torch.long)
    gaps = list(row.get("gaps") or [])
    if len(gaps) == n - 1:
        gaps = gaps + [0]
    gaps_t = torch.tensor(gaps[:n], dtype=torch.long)
    lead = torch.tensor([int(row.get("lead_frames") or 0)], dtype=torch.long)
    seg = torch.tensor(row["seg_durations"], dtype=torch.long)
    with torch.no_grad():
        out = engine.model(features.unsqueeze(0), durations=durations.unsqueeze(0),
                           seg_durations=seg.unsqueeze(0), gaps=gaps_t.unsqueeze(0),
                           lead=lead)
    return out["mel"][0].detach().cpu().numpy()


def bak(wave: np.ndarray, sample_rate: int = 24000) -> float:
    from speechmos import dnsmos

    wave16 = resample_poly(np.asarray(wave, dtype=np.float64), 16000, sample_rate).astype(np.float32)
    return round(float(dnsmos.run(wave16, sr=16000)["bak_mos"]), 6)


def band_bins(sample_rate: int = 24000, n_fft: int = 1024, n_mels: int = 100,
              f_max: float = 12000.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    bank = mel_filterbank(sample_rate, n_fft, n_mels, 0.0, f_max, norm=None).numpy()
    freqs = np.arange(n_fft // 2 + 1) * (sample_rate / n_fft)
    centers = np.array([(row * freqs).sum() / row.sum() if row.sum() > 0 else 0.0
                        for row in bank])
    return centers, np.where(centers <= 4000.0)[0], np.where(centers > 4000.0)[0]


def replace_bins(c_mel: np.ndarray, b_mel: np.ndarray, bins: np.ndarray) -> np.ndarray:
    out = c_mel.copy()
    out[:, bins] = b_mel[:, bins]
    return out


def bootstrap_recovery(values: dict[str, np.ndarray], n_boot: int = N_BOOT,
                       seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    n = len(values["C"])
    out = {name: [] for name in values}
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        means = {name: float(values[name][idx].mean()) for name in values}
        delta = means["B"] - means["C"]
        for name in ("C_lo", "C_hi"):
            out[name].append((means[name] - means["C"]) / delta if abs(delta) > 1e-12 else np.nan)
    return {name: [round(float(np.percentile(out[name], 2.5)), 4),
                   round(float(np.percentile(out[name], 97.5)), 4)]
            for name in ("C_lo", "C_hi")}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    cfg = yaml.safe_load(Path(CFG32).read_text(encoding="utf-8"))
    sample_rate = int(cfg.get("sample_rate", 24000))
    dataset = TtsDataset(HOLDOUT, cfg, cache_dir=cfg.get("training", {}).get("cache_dir"))
    index_by_id = {row["id"]: index for index, row in enumerate(dataset.rows)}
    rows = [dataset.rows[index_by_id[item]] for item in NEW_IDS]
    engine = Synthesizer(cfg, P2, device="cpu")
    engine.model.eval()
    engine.vocoder.eval()
    _centers, lo_bins, hi_bins = band_bins(sample_rate, int(cfg["mel"]["n_fft"]),
                                          int(cfg["mel"]["n_mels"]), float(cfg["mel"]["f_max"]))

    baks = {name: [] for name in ("B", "C", "C_all", "C_none", "C_lo", "C_hi")}
    for count, row in enumerate(rows):
        item = dataset[index_by_id[row["id"]]]
        b_mel = item["mel"].detach().cpu().numpy().astype(np.float32)
        c_mel = predict_c_mel(engine, item["features"], row)
        frames = min(b_mel.shape[0], c_mel.shape[0])
        b_mel, c_mel = b_mel[:frames], c_mel[:frames]
        variants = {
            "B": b_mel,
            "C": c_mel,
            "C_all": b_mel.copy(),
            "C_none": c_mel.copy(),
            "C_lo": replace_bins(c_mel, b_mel, lo_bins),
            "C_hi": replace_bins(c_mel, b_mel, hi_bins),
        }
        for name, mel in variants.items():
            wave = render_mel(engine, mel, OUT / f"{count:02d}_{name}.wav", sample_rate)
            baks[name].append(bak(wave, sample_rate))
        print(json.dumps({"done": count + 1, "total": len(rows), "id": row["id"]}),
              flush=True)

    means = {name: float(np.mean(values)) for name, values in baks.items()}
    delta = means["B"] - means["C"]
    values = {name: np.asarray(baks[name], dtype=float) for name in baks}
    ci = bootstrap_recovery(values)
    recovery = {name: (means[name] - means["C"]) / delta if abs(delta) > 1e-12 else None
                for name in ("C_lo", "C_hi")}
    median_diff_lo = float(np.median(values["C_lo"] - values["C"]))
    controls_ok = (abs(means["C_all"] - means["B"]) <= A4["control_tol"]
                   and abs(means["C_none"] - means["C"]) <= A4["control_tol"])
    sum_lo_hi = (recovery["C_lo"] or 0) + (recovery["C_hi"] or 0)

    if not controls_ok:
        branch, status = "LẠ — đối chứng lệch", "DỪNG, BÁO"
    elif delta < A4["delta_min"]:
        branch, status = "KHÔNG XÁC NHẬN ĐƯỢC — Δac < 0,15", "BÁO"
    elif recovery["C_hi"] >= A4["recovery_min"] and recovery["C_lo"] < A4["recovery_min"]:
        branch, status = "LẠ — C_hi chính trong khi C_lo không", "DỪNG, BÁO"
    elif not (A4["sum_min"] <= sum_lo_hi <= A4["sum_max"]):
        branch, status = "LẠ — tổng lo+hi ngoài [0,5; 1,5]", "DỪNG, BÁO"
    elif (recovery["C_lo"] >= A4["recovery_min"]
          and ci["C_lo"][0] >= A4["ci_lower_min"]):
        branch, status = "ĐẠT — C_lo xác nhận", "TIẾP"
    else:
        branch, status = "KHÔNG ĐẠT — C_lo chưa xác nhận", "BÁO"

    result = {
        "criteria": A4,
        "rows": NEW_IDS,
        "baks": {name: [round(v, 6) for v in values[name]] for name in values},
        "means": {name: round(means[name], 6) for name in means},
        "delta_ac": round(delta, 6),
        "recovery": {name: round(value, 4) if value is not None else None
                     for name, value in recovery.items()},
        "recovery_ci95": ci,
        "median_diff_C_lo_minus_C": round(median_diff_lo, 4),
        "sum_lo_hi": round(sum_lo_hi, 4),
        "controls_ok": bool(controls_ok),
        "verdict": {"branch": branch, "status": status},
    }
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(json.dumps({key: result[key] for key in
                      ("means", "delta_ac", "recovery", "recovery_ci95",
                       "median_diff_C_lo_minus_C", "sum_lo_hi", "verdict")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
