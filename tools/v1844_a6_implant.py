"""v18.44 — A6: chẩn đoán vị trí rè bằng cấy ghép mel oracle (không train).

Lấy mel C (P2, teacher-forcing) và mel B (mel gốc), thay từng phần bằng B, vocode, chấm BAK
trên đúng 40 câu A4. Chạy C_all/C_none trước; chỉ chạy biến thể nếu đối chứng đạt.

Biến thể: C_nuc, C_onc, C_sil, C_hi, C_lo. C_f0 chỉ chạy nếu model hỗ trợ TF F0
(model hiện không nhận f0 đầu vào => ghi rõ, bỏ qua).

Recovery(X) = (BAK(X) - BAK(C)) / Δac. Chính khi >= 0,5.
GV ratio = var_theo_thời_gian(C) / var_theo_thời_gian(B) theo 3 dải, frame hữu thanh.
"""

from __future__ import annotations

import argparse
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
A4 = Path("artifacts/bench/v1843_a4/result.json")
OUT = Path("artifacts/bench/v1844_a6_implant")
N_ROWS = 40

A6 = {"recovery_main": 0.5, "control_tol": 0.02, "complement_min": 0.5,
      "complement_max": 1.5, "gv_low": 0.8, "freq_split_hz": 4000.0}
BANDS = (("<1k", 0.0, 1000.0), ("1-4k", 1000.0, 4000.0), (">4k", 4000.0, 12000.0))


def load_rows(n: int = N_ROWS) -> list[dict]:
    rows = [json.loads(line) for line in Path(HOLDOUT).read_text(encoding="utf-8").splitlines()
            if line.strip()]
    rows = [row for row in rows
            if row.get("frame_range") and any(gap >= 3 for gap in row.get("gaps", []))
            and Path(row["audio_path"]).exists()]
    step = max(1, len(rows) // n)
    picked = rows[::step][:n]
    if len(picked) < n:
        picked = rows[:n]
    return picked


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


def frame_masks(row: dict, frames: int) -> dict:
    n = len(row["durations"])
    gaps = list(row.get("gaps") or [])
    if len(gaps) == n - 1:
        gaps = gaps + [0]
    lead = int(row.get("lead_frames") or 0)
    nuc = np.zeros(frames, dtype=bool)
    onc = np.zeros(frames, dtype=bool)
    sil = np.zeros(frames, dtype=bool)
    sil[:min(lead, frames)] = True
    cursor = lead
    for index in range(n):
        duration = int(row["durations"][index])
        gap = int(gaps[index]) if index < len(gaps) else 0
        segments = row.get("seg_durations")
        if segments and len(segments[index]) == 4:
            onset, medial, nucleus, coda = (int(value) for value in segments[index])
            if onset + medial + nucleus + coda != duration:
                onset, medial, nucleus, coda = 0, 0, duration, 0
        else:
            onset, medial, nucleus, coda = 0, 0, duration, 0
        start = cursor
        end_nuc = start + onset + medial + nucleus
        if start < frames:
            onc[start:min(start + onset, frames)] = True
            nuc[min(start + onset + medial, frames):min(end_nuc, frames)] = True
            onc[min(end_nuc, frames):min(end_nuc + coda, frames)] = True
        cursor = start + duration + gap
        sil[min(end_nuc + coda, frames):min(cursor, frames)] = True
    return {"nuc": nuc, "onc": onc, "sil": sil}


def bak(wave: np.ndarray, sample_rate: int = 24000) -> float:
    from speechmos import dnsmos

    wave16 = resample_poly(np.asarray(wave, dtype=np.float64), 16000, sample_rate).astype(np.float32)
    return round(float(dnsmos.run(wave16, sr=16000)["bak_mos"]), 6)


def band_bins(sample_rate: int = 24000, n_fft: int = 1024, n_mels: int = 100,
              f_max: float = 12000.0) -> tuple[np.ndarray, dict]:
    bank = mel_filterbank(sample_rate, n_fft, n_mels, 0.0, f_max, norm=None)
    weights = bank.numpy()
    freqs = np.arange(n_fft // 2 + 1) * (sample_rate / n_fft)
    centers = []
    for row in weights:
        mass = row.sum()
        centers.append(float((row * freqs).sum() / mass) if mass > 0 else 0.0)
    centers = np.asarray(centers)
    bands = {name: np.where((centers >= low) & (centers < high))[0]
             for name, low, high in BANDS}
    return centers, bands


def gv_ratio(c_mel: np.ndarray, b_mel: np.ndarray, voiced: np.ndarray,
             bands: dict) -> dict:
    out = {}
    frames = min(c_mel.shape[0], b_mel.shape[0], voiced.size)
    if frames == 0:
        return {name: None for name in bands}
    c = c_mel[:frames]
    b = b_mel[:frames]
    mask = voiced[:frames]
    if not mask.any():
        return {name: None for name in bands}
    for name, bins in bands.items():
        if bins.size == 0:
            out[name] = None
            continue
        c_var = float(np.var(c[mask][:, bins], axis=0).mean())
        b_var = float(np.var(b[mask][:, bins], axis=0).mean())
        out[name] = round(c_var / b_var, 4) if b_var > 1e-12 else None
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=N_ROWS)
    parser.add_argument("--skip-controls", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    cfg = yaml.safe_load(Path(CFG32).read_text(encoding="utf-8"))
    sample_rate = int(cfg.get("sample_rate", 24000))

    a4 = json.loads(A4.read_text(encoding="utf-8"))
    a4_ids = [row["id"] for row in a4["rows"]]
    rows = load_rows(args.rows)
    by_id = {row["id"]: row for row in rows}
    rows = [by_id[item] for item in a4_ids if item in by_id]
    dataset = TtsDataset(HOLDOUT, cfg, cache_dir=cfg.get("training", {}).get("cache_dir"))
    index_by_id = {row["id"]: index for index, row in enumerate(dataset.rows)}

    engine = Synthesizer(cfg, P2, device="cpu")
    engine.model.eval()
    engine.vocoder.eval()
    centers, bands = band_bins(sample_rate, int(cfg["mel"]["n_fft"]),
                               int(cfg["mel"]["n_mels"]), float(cfg["mel"]["f_max"]))
    hi_bins = np.where(centers > A6["freq_split_hz"])[0]
    lo_bins = np.where(centers <= A6["freq_split_hz"])[0]

    # Chuẩn bị mel B/C + mask một lần
    prepared = []
    for count, row in enumerate(rows):
        item = dataset[index_by_id[row["id"]]]
        b_mel = item["mel"].detach().cpu().numpy().astype(np.float32)
        c_mel = predict_c_mel(engine, item["features"], row)
        frames = min(b_mel.shape[0], c_mel.shape[0])
        b_mel, c_mel = b_mel[:frames], c_mel[:frames]
        masks = frame_masks(row, frames)
        vuv = np.asarray(item.get("vuv", torch.zeros(item["features"].size(0))).cpu()).reshape(-1)
        durations = row["durations"]
        gaps = list(row.get("gaps") or [])
        if len(gaps) == len(durations) - 1:
            gaps = gaps + [0]
        frame_vuv = [False] * int(row.get("lead_frames") or 0)
        for index, (duration, gap) in enumerate(zip(durations, gaps[:len(durations)])):
            frame_vuv.extend([bool(vuv[index] > 0.5)] * int(duration))
            frame_vuv.extend([False] * int(gap))
        frame_vuv = np.asarray(frame_vuv[:frames], dtype=bool)
        prepared.append({"id": row["id"], "b": b_mel, "c": c_mel, "masks": masks,
                         "vuv": frame_vuv})

    variants = {
        "C_none": lambda p: p["c"].copy(),
        "C_all": lambda p: p["b"].copy(),
        "C_nuc": lambda p: _replace_frames(p["c"], p["b"], p["masks"]["nuc"]),
        "C_onc": lambda p: _replace_frames(p["c"], p["b"], p["masks"]["onc"]),
        "C_sil": lambda p: _replace_frames(p["c"], p["b"], p["masks"]["sil"]),
        "C_hi": lambda p: _replace_bins(p["c"], p["b"], hi_bins),
        "C_lo": lambda p: _replace_bins(p["c"], p["b"], lo_bins),
    }

    results = {}
    for name, fn in variants.items():
        if name in ("C_nuc", "C_onc", "C_sil") and any(
                not (p["masks"]["nuc"].any() or p["masks"]["onc"].any() or p["masks"]["sil"].any())
                for p in prepared):
            pass
        values = []
        for count, p in enumerate(prepared):
            mel = fn(p)
            wave = render_mel(engine, mel, OUT / f"{count:02d}_{name}.wav", sample_rate)
            values.append(bak(wave, sample_rate))
        results[name] = {"mean": round(float(np.mean(values)), 6),
                         "rows": [round(v, 6) for v in values]}

    b_mean = results["C_all"]["mean"]
    c_mean = results["C_none"]["mean"]
    a4_b = [row["metrics"]["B"]["bak"] for row in a4["rows"]]
    a4_c = [row["metrics"]["C"]["bak"] for row in a4["rows"]]
    a4_b_mean = float(np.mean(a4_b))
    a4_c_mean = float(np.mean(a4_c))
    a4_delta = a4_b_mean - a4_c_mean
    delta_ac = b_mean - c_mean
    control_ok = (abs(b_mean - a4_b_mean) <= A6["control_tol"]
                  and abs(c_mean - a4_c_mean) <= A6["control_tol"])
    # Đối chứng thực chất: C_all phải khớp B của A4, C_none khớp C của A4.
    if not control_ok or abs(delta_ac - a4_delta) > 0.02:
        print(json.dumps({"stop": "đối chứng C_all/C_none lệch", "b_mean": b_mean,
                          "c_mean": c_mean, "a4_b_mean": a4_b_mean,
                          "a4_c_mean": a4_c_mean, "delta_ac": delta_ac,
                          "a4_delta": a4_delta}, ensure_ascii=False, indent=1))
        raise SystemExit(2)

    recovery = {name: round((results[name]["mean"] - c_mean) / delta_ac, 4)
                for name in ("C_nuc", "C_onc", "C_sil", "C_hi", "C_lo")}
    gv = {}
    for name, p in zip([row["id"] for row in rows], prepared):
        gv[name] = gv_ratio(p["c"], p["b"], p["vuv"], bands)
    gv_mean = {}
    for band in bands:
        values = [value[band] for value in gv.values() if value[band] is not None]
        gv_mean[band] = round(float(np.mean(values)), 4) if values else None

    mains = [name for name, value in recovery.items() if value >= A6["recovery_main"]]
    sum_frame = recovery["C_nuc"] + recovery["C_onc"] + recovery["C_sil"]
    sum_freq = recovery["C_hi"] + recovery["C_lo"]
    weird = (abs(results["C_all"]["mean"] - b_mean) > A6["control_tol"]
             or abs(results["C_none"]["mean"] - c_mean) > A6["control_tol"]
             or not (A6["complement_min"] <= sum_frame <= A6["complement_max"])
             or not (A6["complement_min"] <= sum_freq <= A6["complement_max"]))
    oversmooth = any(value is not None and value < A6["gv_low"] for value in gv_mean.values()) \
        and any(name in ("C_hi", "C_lo") for name in mains)

    if weird:
        branch = "LẠ — DỪNG, BÁO"
    elif mains:
        branch = "CHÍNH: " + ", ".join(mains)
    else:
        branch = "PHÂN TÁN — không thành phần nào >= 0,5"

    result = {
        "criteria": A6,
        "rows": [row["id"] for row in rows],
        "freq_bins": {"split_hz": A6["freq_split_hz"],
                      "center_hz_first_last": [round(float(centers[0]), 1),
                                               round(float(centers[-1]), 1)],
                      "n_hi": int(hi_bins.size), "n_lo": int(lo_bins.size),
                      "hi_first_last": [round(float(centers[hi_bins[0]]), 1),
                                        round(float(centers[hi_bins[-1]]), 1)]
                      if hi_bins.size else None},
        "f0_teacher_forcing": {"supported": False,
                               "reason": "model.forward không nhận f0/durations F0; F0 do variance head dự đoán"},
        "controls": {"C_all": results["C_all"]["mean"], "B": b_mean,
                     "C_none": results["C_none"]["mean"], "C": c_mean,
                     "a4_b_mean": round(a4_b_mean, 4), "a4_c_mean": round(a4_c_mean, 4),
                     "delta_ac": round(delta_ac, 4), "a4_delta_ac": round(a4_delta, 4),
                     "ok": bool(control_ok and abs(delta_ac - a4_delta) <= 0.02)},
        "variants": results,
        "recovery": recovery,
        "complement_sums": {"nuc+onc+sil": round(sum_frame, 4),
                            "hi+lo": round(sum_freq, 4)},
        "gv_ratio": {"per_sentence": gv, "mean": gv_mean,
                     "over_smoothing_supported": bool(oversmooth)},
        "verdict": {"branch": branch, "mains": mains, "weird": bool(weird),
                    "status": "DỪNG, BÁO" if weird else "TIẾP"},
    }
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(json.dumps({key: result[key] for key in
                      ("controls", "recovery", "complement_sums", "gv_ratio", "verdict",
                       "freq_bins")}, ensure_ascii=False, indent=1))


def _replace_frames(c_mel: np.ndarray, b_mel: np.ndarray, mask: np.ndarray) -> np.ndarray:
    out = c_mel.copy()
    frames = min(out.shape[0], mask.size)
    out[:frames][mask[:frames]] = b_mel[:frames][mask[:frames]]
    return out


def _replace_bins(c_mel: np.ndarray, b_mel: np.ndarray, bins: np.ndarray) -> np.ndarray:
    out = c_mel.copy()
    if bins.size:
        out[:, bins] = b_mel[:, bins]
    return out


if __name__ == "__main__":
    main()
