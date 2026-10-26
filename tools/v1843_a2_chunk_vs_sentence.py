"""v18.43 — A2: đo chunk vs sentence (P2 PyTorch), BAK + UTMOS 5 seed, bootstrap ghép cặp.

Luật đã đăng ký trước (V1842.A2 + V1842b.3):
- 30 câu có dấu câu; hai mode; chuẩn −16 LUFS.
- Sentence thắng khi ĐỦ ba điều kiện:
  1. CI95 ΔUTMOS (sentence − chunk) > 0.
  2. ΔBAK điểm ≥ −0,05.
  3. Cận dưới CI95 ΔBAK ≥ −0,10.
- Trượt bất kỳ điều kiện nào => hợp đồng = chunk.
- Đặc biệt: ΔBAK CI95 > 0 nhưng ΔUTMOS không đạt => "lạ có ích", báo, không tự chọn.
- Đối chứng âm: cùng audio chunk, hai bộ seed UTMOS khác nhau; CI95 không chứa 0 => phép đo hỏng.

Không đổi production.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import yaml
from scipy.signal import resample_poly

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("VIFASTT_INTRA_THREADS", "2")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

from vifasttts.infer import Synthesizer

CFG32 = "configs/small_codelung_v32.yaml"
P2 = "artifacts/listen_small_filt/adv_progress_p2/_ckpt/step_02000.pt"
OUT = Path("artifacts/bench/v1843_a2")
SEEDS_MAIN = (0, 1, 2, 3, 4)
SEEDS_NEG = (5, 6, 7, 8, 9)
N_BOOT = 10000


def load_texts(n: int = 30) -> list[dict]:
    data = json.loads(Path("examples/drift_texts.json").read_text(encoding="utf-8"))
    if len(data) < n:
        raise RuntimeError(f"cần {n} câu, chỉ có {len(data)}")
    return [{"id": item["id"], "text": item["text"]} for item in data[:n]]


def score_bak(wave: np.ndarray, sr: int = 24000) -> float:
    from speechmos import dnsmos

    wave16 = resample_poly(np.asarray(wave, dtype=np.float64), 16000, sr).astype(np.float32)
    return round(float(dnsmos.run(wave16, sr=16000)["bak_mos"]), 4)


def score_utmos(model, path: Path, seed: int, device: str = "cpu") -> float:
    np.random.seed(seed)
    random.seed(seed)
    torch.manual_seed(seed)
    with torch.no_grad():
        value = model.predict(input_path=str(path), device=device, num_repetitions=1,
                              remove_silent_section=True, verbose=False)
    return round(float(value), 4)


def paired_bootstrap(values: np.ndarray, n_boot: int = N_BOOT, seed: int = 0) -> dict:
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, values.size, size=(n_boot, values.size))
    means = values[draws].mean(axis=1)
    return {
        "mean": round(float(values.mean()), 4),
        "ci95": [round(float(np.percentile(means, 2.5)), 4),
                 round(float(np.percentile(means, 97.5)), 4)],
        "n": int(values.size),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    texts = load_texts(args.limit)
    cfg = yaml.safe_load(Path(CFG32).read_text(encoding="utf-8"))
    engine = Synthesizer(cfg, P2, device="cpu")
    engine.model.eval()
    engine.vocoder.eval()

    import utmosv2

    torch.manual_seed(42)
    np.random.seed(42)
    random.seed(42)
    utmos = utmosv2.create_model(pretrained=True, config="fusion_stage3", fold=0, seed=42,
                                 device=args.device)

    rows = []
    started = time.perf_counter()
    for index, item in enumerate(texts):
        chunk_path = OUT / f"chunk_{index:02d}.wav"
        sentence_path = OUT / f"sentence_{index:02d}.wav"
        engine.synthesize(item["text"], chunk_path, gate_threshold=0.5, sharpen_alpha=0.0,
                          target_lufs=-16, peak_normalize=False, max_chars=400)
        engine.synthesize_sentence(item["text"], sentence_path, gate_threshold=1.01,
                                   sharpen_alpha=0.0, target_lufs=-16, peak_normalize=False,
                                   max_chars=400)
        chunk_wave, sr = sf.read(chunk_path, dtype="float32")
        sentence_wave, _ = sf.read(sentence_path, dtype="float32")
        chunk_wave = np.asarray(chunk_wave).reshape(-1)
        sentence_wave = np.asarray(sentence_wave).reshape(-1)
        row = {
            "id": item["id"],
            "text": item["text"],
            "chunk_seconds": round(float(chunk_wave.size / sr), 4),
            "sentence_seconds": round(float(sentence_wave.size / sr), 4),
            "chunk_bak": score_bak(chunk_wave, sr),
            "sentence_bak": score_bak(sentence_wave, sr),
            "chunk_utmos": [score_utmos(utmos, chunk_path, seed, args.device)
                            for seed in SEEDS_MAIN],
            "sentence_utmos": [score_utmos(utmos, sentence_path, seed, args.device)
                               for seed in SEEDS_MAIN],
            "chunk_utmos_neg": [score_utmos(utmos, chunk_path, seed, args.device)
                                for seed in SEEDS_NEG],
        }
        row["d_utmos"] = round(float(np.mean(row["sentence_utmos"])
                                     - np.mean(row["chunk_utmos"])), 4)
        row["d_bak"] = round(float(row["sentence_bak"] - row["chunk_bak"]), 4)
        row["d_utmos_neg"] = round(float(np.mean(row["chunk_utmos_neg"])
                                         - np.mean(row["chunk_utmos"])), 4)
        rows.append(row)
        print(json.dumps({"done": index + 1, "total": len(texts), "id": item["id"]},
                         ensure_ascii=False), flush=True)

    d_utmos = np.array([row["d_utmos"] for row in rows])
    d_bak = np.array([row["d_bak"] for row in rows])
    d_neg = np.array([row["d_utmos_neg"] for row in rows])
    utmos_ci = paired_bootstrap(d_utmos)
    bak_ci = paired_bootstrap(d_bak)
    neg_ci = paired_bootstrap(d_neg)

    cond_utmos = utmos_ci["ci95"][0] > 0
    cond_bak_point = bak_ci["mean"] >= -0.05
    cond_bak_lower = bak_ci["ci95"][0] >= -0.10
    sentence_wins = bool(cond_utmos and cond_bak_point and cond_bak_lower)
    special = bool(bak_ci["ci95"][0] > 0 and not cond_utmos)
    negative_control_ok = bool(neg_ci["ci95"][0] <= 0 <= neg_ci["ci95"][1])

    if not negative_control_ok:
        verdict = "PHÉP ĐO HỎNG — đối chứng âm CI95 không chứa 0; dừng, báo"
    elif sentence_wins:
        verdict = "SENTENCE THẮNG — hợp đồng = sentence; ONNX phải port sentence dùng chung"
    elif special:
        verdict = "LẠ CÓ ÍCH — sentence ít rè hơn rõ nhưng UTMOS không đạt; báo A0, không tự chọn"
    else:
        verdict = "CHUNK — hợp đồng = chunk; sentence chỉ là công cụ PyTorch"

    result = {
        "criteria": {
            "n": len(rows),
            "lufs": -16,
            "seeds_main": list(SEEDS_MAIN),
            "seeds_neg": list(SEEDS_NEG),
            "bootstrap": N_BOOT,
            "sentence_wins": "CI95 dUTMOS > 0 AND dBak >= -0.05 AND CI95 dBak lower >= -0.10",
        },
        "environment": {"torch": torch.__version__, "device": args.device,
                        "p2": P2, "seconds": round(time.perf_counter() - started, 1)},
        "rows": rows,
        "summary": {
            "d_utmos": utmos_ci,
            "d_bak": bak_ci,
            "negative_control": neg_ci,
            "negative_control_ok": negative_control_ok,
            "cond_utmos": cond_utmos,
            "cond_bak_point": cond_bak_point,
            "cond_bak_lower": cond_bak_lower,
            "sentence_wins": sentence_wins,
            "special_useful": special,
            "verdict": verdict,
        },
    }
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
