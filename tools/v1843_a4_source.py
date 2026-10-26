"""v18.43 — A4: chẩn đoán nguồn rè 3 tầng (A/B/C/C') trên 40 câu holdout.

Đăng ký trước (V1842.A4 + V1842b.2):
- A = wav gốc; B = Vocos(mel từ wav gốc); C = Vocos(mel P2, thời lượng gốc nếu hỗ trợ);
  C' = Vocos(mel g1_1k, cùng cách). Tất cả chuẩn −16 LUFS.
- Đo BAK, nhiễu khoảng lặng (dB RMS), spectral flatness 2–8 kHz ở frame hữu thanh.
- Δvoc = BAK(A) − BAK(B); Δac = BAK(B) − BAK(C).
- Nhánh: vocoder / acoustic / cả hai / dữ liệu / D (không phát hiện nguồn).
- Kiểm tra đầu vào bắt buộc: mel config khớp Vocos; tool C không-TF khớp CLI trong ngưỡng parity.

Không đổi production, không train.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import yaml
from scipy.signal import resample_poly, stft

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("VIFASTT_INTRA_THREADS", "2")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

from vifasttts.data.dataset import TtsDataset
from vifasttts.infer import Synthesizer, _apply_target_lufs, write_wav
from vifasttts.runtime.onnx_engine import read_metadata
from vifasttts.runtime.postprocess import postprocess

CFG32 = "configs/small_codelung_v32.yaml"
P2 = "artifacts/listen_small_filt/adv_progress_p2/_ckpt/step_02000.pt"
G1 = "runs/v1830_g1/ckpt_1000.pt"
VOCODER = "artifacts/onnx/v1837/vocos_pretrained_vocoder.onnx"
HOLDOUT = "data/codelung/v32/holdout_clean_v2_dur_seg_slot4.jsonl"
OUT = Path("artifacts/bench/v1843_a4")
N_ROWS = 40

# Ngưỡng parity E2E hiện hành (v18.40).
E2E = {"max_abs": 2e-3, "rmse": 2e-4, "rms_ratio_min": 0.99, "rms_ratio_max": 1.01}
A4 = {"delta": 0.15, "delta_close": 0.03, "bak_data": 3.8, "aux_noise_db": 3.0,
      "aux_flat_rel": 0.20, "nonmonotone": 0.10}


def load_rows(n: int = N_ROWS) -> list[dict]:
    rows = [json.loads(line) for line in Path(HOLDOUT).read_text(encoding="utf-8").splitlines()
            if line.strip()]
    rows = [row for row in rows
            if row.get("frame_range") and any(gap >= 3 for gap in row.get("gaps", []))
            and Path(row["audio_path"]).exists()]
    if len(rows) < n:
        raise RuntimeError(f"cần {n} row holdout có pause, nhận {len(rows)}")
    # Chọn trải đều theo thứ tự manifest, không dùng câu train/val.
    step = max(1, len(rows) // n)
    picked = rows[::step][:n]
    if len(picked) < n:
        picked = rows[:n]
    return picked


def mel_config_check(cfg: dict) -> dict:
    mel = cfg["mel"]
    meta = read_metadata(VOCODER)
    expected = {"sample_rate": 24000, "n_fft": 1024, "hop_length": 256, "n_mels": 100,
                "f_min": 0, "f_max": 12000}
    actual = {
        "sample_rate": int(cfg.get("sample_rate", 24000)),
        "n_fft": int(mel["n_fft"]),
        "hop_length": int(mel["hop_length"]),
        "n_mels": int(mel["n_mels"]),
        "f_min": int(mel["f_min"]),
        "f_max": int(mel["f_max"]),
    }
    onnx = {
        "sample_rate": int(meta["sample_rate"]) if meta.get("sample_rate") else None,
        "n_fft": int(meta["n_fft"]) if meta.get("n_fft") else None,
        "hop_length": int(meta["hop_length"]) if meta.get("hop_length") else None,
        "n_mels": int(meta["n_mels"]) if meta.get("n_mels") else None,
    }
    checks = {
        "config_matches_vocos_expected": actual == expected,
        "onnx_metadata_matches_config": all(onnx[key] == actual[key]
                                            for key in ("sample_rate", "n_fft",
                                                        "hop_length", "n_mels")),
        "log_magnitude": bool(mel.get("log_magnitude", True)),
        "log_floor_mode": mel.get("log_floor_mode"),
        "norm": mel.get("norm"),
    }
    return {"expected": expected, "config": actual, "onnx_metadata": onnx,
            "checks": checks, "ok": all(checks[key] for key in
                                        ("config_matches_vocos_expected",
                                         "onnx_metadata_matches_config",
                                         "log_magnitude"))}


def read_audio(path: str | Path, sample_rate: int = 24000) -> np.ndarray:
    wave, sr = sf.read(path, dtype="float32")
    wave = np.asarray(wave).reshape(-1)
    if sr != sample_rate:
        wave = resample_poly(wave, sample_rate, sr).astype(np.float32)
    return wave


def normalize_lufs(wave: np.ndarray, sample_rate: int = 24000) -> np.ndarray:
    wave = postprocess(np.asarray(wave, dtype=np.float32), sample_rate)
    return np.asarray(_apply_target_lufs(wave, sample_rate, -16.0), dtype=np.float32)


def cut_original(row: dict, sample_rate: int = 24000, hop: int = 256) -> np.ndarray:
    wave = read_audio(row["audio_path"], sample_rate)
    start, end = (int(x) for x in row["frame_range"])
    return wave[start * hop:end * hop]


def render_mel(engine: Synthesizer, mel: np.ndarray, path: Path,
               sample_rate: int = 24000) -> np.ndarray:
    tensor = torch.from_numpy(np.asarray(mel, dtype=np.float32)).unsqueeze(0)
    with torch.no_grad():
        wave = engine.vocoder(tensor)[0].detach().cpu().numpy()
    wave = normalize_lufs(wave, sample_rate)
    write_wav(path, wave, sample_rate)
    return wave


def render_forward(engine: Synthesizer, features: torch.Tensor, path: Path,
                   sample_rate: int = 24000) -> np.ndarray:
    """Đường C không teacher-forcing: model tự dự đoán thời lượng."""
    with torch.no_grad():
        out = engine.model(features.unsqueeze(0), speed=torch.tensor([1.0]),
                           gate_threshold=0.5)
    mel = out["mel"][0].detach().cpu().numpy()
    return render_mel(engine, mel, path, sample_rate)


def render_tf(engine: Synthesizer, features: torch.Tensor, row: dict, path: Path,
              sample_rate: int = 24000) -> np.ndarray:
    """Đường C/C' teacher-forcing: durations/gaps/lead/seg_durations gốc."""
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
    mel = out["mel"][0].detach().cpu().numpy()
    return render_mel(engine, mel, path, sample_rate)


def frame_rms_db(wave: np.ndarray, n_fft: int = 1024, hop: int = 256) -> np.ndarray:
    if wave.size < n_fft:
        return np.array([], dtype=np.float32)
    frames = np.lib.stride_tricks.sliding_window_view(wave, n_fft)[::hop]
    rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1) + 1e-12)
    return (20.0 * np.log10(rms + 1e-12)).astype(np.float32)


def pause_frame_indices(row: dict) -> np.ndarray:
    n = len(row["durations"])
    gaps = list(row.get("gaps") or [])
    if len(gaps) == n - 1:
        gaps = gaps + [0]
    cursor = int(row.get("lead_frames") or 0)
    indices = []
    for duration, gap in zip(row["durations"], gaps[:n]):
        cursor += int(duration)
        if gap >= 3:
            indices.extend(range(cursor, cursor + int(gap)))
        cursor += int(gap)
    return np.asarray(indices, dtype=np.int64)


def spectral_flatness(wave: np.ndarray, vuv: np.ndarray, sample_rate: int = 24000,
                      n_fft: int = 1024, hop: int = 256) -> float:
    if wave.size < n_fft:
        return float("nan")
    freq, _time, spec = stft(wave, fs=sample_rate, nperseg=n_fft, noverlap=n_fft - hop,
                             boundary=None, padded=False)
    band = (freq >= 2000) & (freq <= 8000)
    mag = np.abs(spec[band]) + 1e-12
    flat = np.exp(np.mean(np.log(mag), axis=0)) / np.mean(mag, axis=0)
    voiced = np.asarray(vuv, dtype=bool)
    count = min(flat.size, voiced.size)
    if count == 0 or not voiced[:count].any():
        return float("nan")
    return float(np.mean(flat[:count][voiced[:count]]))


def score_bak(wave: np.ndarray, sample_rate: int = 24000) -> float:
    from speechmos import dnsmos

    wave16 = resample_poly(np.asarray(wave, dtype=np.float64), 16000, sample_rate).astype(np.float32)
    return round(float(dnsmos.run(wave16, sr=16000)["bak_mos"]), 4)


def row_metrics(wave: np.ndarray, row: dict, vuv: np.ndarray,
                sample_rate: int = 24000) -> dict:
    rms = frame_rms_db(wave)
    pause_idx = pause_frame_indices(row)
    pause_idx = pause_idx[pause_idx < rms.size]
    noise = float(np.median(rms[pause_idx])) if pause_idx.size else float("nan")
    flat = spectral_flatness(wave, vuv, sample_rate)
    return {"bak": score_bak(wave, sample_rate), "pause_rms_db": round(noise, 3),
            "flatness_2_8k": round(flat, 6) if np.isfinite(flat) else None,
            "seconds": round(float(wave.size / sample_rate), 3)}


def stats(values: list[float]) -> dict:
    arr = np.asarray([value for value in values if value is not None and np.isfinite(value)],
                     dtype=float)
    if arr.size == 0:
        return {"n": 0}
    return {"n": int(arr.size), "mean": round(float(arr.mean()), 4),
            "median": round(float(np.median(arr)), 4),
            "min": round(float(arr.min()), 4), "max": round(float(arr.max()), 4)}


def non_tf_parity(engine: Synthesizer, texts: list[str], tmp: Path) -> dict:
    """Tool C không-TF phải khớp CLI cùng mode trong ngưỡng E2E hiện hành."""
    rows = []
    for index, text in enumerate(texts):
        cli_path = tmp / f"parity_cli_{index}.wav"
        tool_path = tmp / f"parity_tool_{index}.wav"
        engine.synthesize(text, cli_path, gate_threshold=0.5, sharpen_alpha=0.0,
                          target_lufs=-16, peak_normalize=False, max_chars=400)
        parsed = engine.vocabs
        from vifasttts.frontend.pipeline import parse_text

        features = torch.tensor([[parsed.encode(item) for item in parse_text(text,
                                                                             resolve_oov=True)]],
                                dtype=torch.long)
        render_forward(engine, features[0], tool_path)
        ref, _sr_ref = sf.read(cli_path, dtype="float32")
        got, _sr_got = sf.read(tool_path, dtype="float32")
        ref = np.asarray(ref).reshape(-1)
        got = np.asarray(got).reshape(-1)
        same_shape = ref.shape == got.shape
        diff = ref.astype(np.float64) - got.astype(np.float64) if same_shape else None
        rms_ratio = (float(np.sqrt(np.mean(got ** 2)) / max(np.sqrt(np.mean(ref ** 2)), 1e-12))
                     if same_shape else None)
        ok = bool(same_shape and np.max(np.abs(diff)) <= E2E["max_abs"]
                  and np.sqrt(np.mean(diff ** 2)) <= E2E["rmse"]
                  and E2E["rms_ratio_min"] <= rms_ratio <= E2E["rms_ratio_max"])
        rows.append({"text": text, "shape_equal": bool(same_shape),
                     "max_abs": round(float(np.max(np.abs(diff))), 9) if same_shape else None,
                     "rmse": round(float(np.sqrt(np.mean(diff ** 2))), 9) if same_shape else None,
                     "rms_ratio": round(rms_ratio, 9) if rms_ratio is not None else None,
                     "ok": ok})
    return {"criteria": E2E, "rows": rows, "ok": all(row["ok"] for row in rows)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=N_ROWS)
    parser.add_argument("--skip-parity", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "tmp"
    tmp.mkdir(exist_ok=True)
    torch.set_num_threads(2)
    cfg = yaml.safe_load(Path(CFG32).read_text(encoding="utf-8"))
    sample_rate = int(cfg.get("sample_rate", 24000))
    hop = int(cfg["mel"]["hop_length"])

    mel_check = mel_config_check(cfg)
    if not mel_check["ok"]:
        print(json.dumps({"stop": "mel config không khớp Vocos", **mel_check},
                         ensure_ascii=False, indent=1))
        raise SystemExit(2)

    engine = Synthesizer(cfg, P2, device="cpu")
    engine.model.eval()
    engine.vocoder.eval()
    engine_g1 = Synthesizer(cfg, G1, device="cpu")
    engine_g1.model.eval()

    if not args.skip_parity:
        parity = non_tf_parity(engine, ["Xin chào các bạn.", "Hôm nay trời rất đẹp.",
                                        "Chúng ta đi thôi."], tmp)
        if not parity["ok"]:
            print(json.dumps({"stop": "tool C không-TF không khớp CLI", **parity},
                             ensure_ascii=False, indent=1))
            raise SystemExit(3)
    else:
        parity = {"skipped": True}

    rows = load_rows(args.rows)
    dataset = TtsDataset(HOLDOUT, cfg, cache_dir=cfg.get("training", {}).get("cache_dir"))
    index_by_id = {row["id"]: index for index, row in enumerate(dataset.rows)}
    results = []
    for count, row in enumerate(rows):
        index = index_by_id[row["id"]]
        item = dataset[index]
        features = item["features"]
        vuv = np.asarray(item.get("vuv", torch.zeros(features.size(0))).cpu()).reshape(-1)
        # vuv cấp âm tiết -> mask frame đủ timeline (gồm lead + gap = False).
        durations = row["durations"]
        gaps = list(row.get("gaps") or [])
        if len(gaps) == len(durations) - 1:
            gaps = gaps + [0]
        frame_vuv = [False] * int(row.get("lead_frames") or 0)
        for index_syl, (duration, gap) in enumerate(zip(durations, gaps[:len(durations)])):
            frame_vuv.extend([bool(vuv[index_syl] > 0.5)] * int(duration))
            frame_vuv.extend([False] * int(gap))
        frame_vuv = np.asarray(frame_vuv, dtype=bool)
        audio_a = normalize_lufs(cut_original(row, sample_rate, hop), sample_rate)
        path_a = OUT / f"{count:02d}_A.wav"
        write_wav(path_a, audio_a, sample_rate)

        gt_mel = item["mel"].detach().cpu().numpy()
        audio_b = render_mel(engine, gt_mel, OUT / f"{count:02d}_B.wav", sample_rate)
        audio_c = render_tf(engine, features, row, OUT / f"{count:02d}_C.wav", sample_rate)
        audio_cp = render_tf(engine_g1, features, row, OUT / f"{count:02d}_Cp.wav", sample_rate)

        metrics = {
            "A": row_metrics(audio_a, row, frame_vuv, sample_rate),
            "B": row_metrics(audio_b, row, frame_vuv, sample_rate),
            "C": row_metrics(audio_c, row, frame_vuv, sample_rate),
            "C'": row_metrics(audio_cp, row, frame_vuv, sample_rate),
        }
        results.append({"id": row["id"], "parent": row["parent"],
                        "syllables": len(row["durations"]), "metrics": metrics})
        print(json.dumps({"done": count + 1, "total": len(rows), "id": row["id"]},
                         ensure_ascii=False), flush=True)

    bak = {tier: [row["metrics"][tier]["bak"] for row in results]
           for tier in ("A", "B", "C", "C'")}
    noise = {tier: [row["metrics"][tier]["pause_rms_db"] for row in results]
             for tier in ("A", "B", "C", "C'")}
    flat = {tier: [row["metrics"][tier]["flatness_2_8k"] for row in results]
            for tier in ("A", "B", "C", "C'")}
    mean_bak = {tier: float(np.mean(bak[tier])) for tier in bak}
    d_voc = mean_bak["A"] - mean_bak["B"]
    d_ac = mean_bak["B"] - mean_bak["C"]

    def paired_median(left: list[float], right: list[float]) -> float:
        diffs = [b - a for a, b in zip(left, right)
                 if a is not None and b is not None and np.isfinite(a) and np.isfinite(b)]
        return float(np.median(diffs)) if diffs else float("nan")

    def paired_rel(left: list[float], right: list[float]) -> float:
        diffs = [(b - a) / abs(a) for a, b in zip(left, right)
                 if a is not None and b is not None and np.isfinite(a) and np.isfinite(b)
                 and abs(a) > 1e-9]
        return float(np.median(diffs)) if diffs else float("nan")

    noise_a_b = paired_median(noise["A"], noise["B"])
    noise_b_c = paired_median(noise["B"], noise["C"])
    flat_a_b = paired_rel(flat["A"], flat["B"])
    flat_b_c = paired_rel(flat["B"], flat["C"])

    def branch() -> str:
        if d_voc >= A4["delta"] and d_voc >= 2 * d_ac:
            return "vocoder"
        if d_ac >= A4["delta"] and d_ac >= 2 * d_voc:
            return "acoustic"
        if d_voc >= A4["delta"] and d_ac >= A4["delta"]:
            return "both"
        if d_voc < A4["delta"] and d_ac < A4["delta"]:
            return "data" if mean_bak["A"] < A4["bak_data"] else "D"
        return "weird"

    chosen = branch()
    close = (abs(d_voc - A4["delta"]) <= A4["delta_close"]
             or abs(d_ac - A4["delta"]) <= A4["delta_close"]
             or abs(mean_bak["A"] - A4["bak_data"]) <= A4["delta_close"])
    nonmonotone = (mean_bak["B"] > mean_bak["A"] + A4["nonmonotone"]
                   or mean_bak["C"] > mean_bak["B"] + A4["nonmonotone"])
    aux_tier = None
    if chosen == "D":
        if noise_a_b >= A4["aux_noise_db"] or flat_a_b >= A4["aux_flat_rel"]:
            aux_tier = "A→B (vocoder/dữ liệu)"
        elif noise_b_c >= A4["aux_noise_db"] or flat_b_c >= A4["aux_flat_rel"]:
            aux_tier = "B→C (acoustic)"
        if aux_tier:
            chosen = f"D + chỉ số phụ chỉ ra {aux_tier}"

    status = "DỪNG, BÁO" if chosen == "weird" or nonmonotone else "TIẾP"
    summary = {
        "branch": chosen,
        "status": status,
        "close_to_threshold": bool(close),
        "nonmonotone": bool(nonmonotone),
        "d_voc": round(float(d_voc), 4),
        "d_ac": round(float(d_ac), 4),
        "bak_mean": {tier: round(value, 4) for tier, value in mean_bak.items()},
        "noise_median_db": {tier: stats(noise[tier]) for tier in noise},
        "flatness_median": {tier: stats(flat[tier]) for tier in flat},
        "aux": {
            "noise_A_to_B_db": round(noise_a_b, 3),
            "noise_B_to_C_db": round(noise_b_c, 3),
            "flat_A_to_B_rel": round(flat_a_b, 4),
            "flat_B_to_C_rel": round(flat_b_c, 4),
        },
    }

    # 5 câu ví dụ A/B/C để người dùng nghe tham khảo (không dùng để quyết định).
    sample_dir = OUT / "samples"
    sample_dir.mkdir(exist_ok=True)
    links = []
    for index in range(min(5, len(rows))):
        for tier, suffix in (("A", "A"), ("B", "B"), ("C", "C")):
            src = OUT / f"{index:02d}_{suffix}.wav"
            dst = sample_dir / f"{index:02d}_{tier}.wav"
            if src.exists():
                dst.write_bytes(src.read_bytes())
        links.append((index, rows[index]["id"]))
    html = ["<html><meta charset='utf-8'><body><h2>A4 — nghe tham khảo A/B/C</h2>",
            "<p>Không dùng để quyết định; quyết định ở báo cáo số.</p>"]
    for index, item_id in links:
        html.append(f"<h3>{index:02d} — {item_id}</h3>")
        for tier in ("A", "B", "C"):
            html.append(f"<div>{tier}: <audio controls src='{index:02d}_{tier}.wav'></audio></div>")
    html.append("</body></html>")
    (sample_dir / "index.html").write_text("\n".join(html), encoding="utf-8")

    result = {
        "criteria": {"A4": A4, "e2e_parity": E2E, "rows": len(rows)},
        "mel_config": mel_check,
        "non_tf_parity": parity,
        "rows": results,
        "summary": summary,
    }
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
