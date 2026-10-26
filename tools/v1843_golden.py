"""v18.43 — A6: golden set, kiểm tất định, baseline chống tái phát.

Chế độ:
  --determinism        chạy 2 lần trong cùng tiến trình + 2 tiến trình riêng cho PyTorch CPU/ONNX CPU;
                       PyTorch CPU không bit-exact => DỪNG (vi phạm tất định); ONNX không bit-exact
                       => ghi cờ tolerance.
  --build-fast         tạo baseline fast (3 câu) trong `eval/baselines/`.
  --check-fast         kiểm baseline fast (dùng bởi pytest).
  --build-full         baseline đầy đủ 20 câu, marker `slow`, có BAK + UTMOS 5 seed.
  --emit-once RUNTIME  chạy một lần, in JSON hash (dùng cho kiểm tiến trình riêng).

Không đổi production. Mọi ngưỡng đã đăng ký trước ở V1842.A6 + V1842b.4.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import yaml

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("VIFASTT_INTRA_THREADS", "2")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

from scipy.signal import resample_poly

from vifasttts.frontend.pipeline import parse_text
from vifasttts.infer import Synthesizer
from vifasttts.runtime.onnx_engine import OnnxAcousticModel, synthesize_onnx

CFG32 = "configs/small_codelung_v32.yaml"
P2 = "artifacts/listen_small_filt/adv_progress_p2/_ckpt/step_02000.pt"
ACOUSTIC = "artifacts/onnx/v1837/p2ema_acoustic.onnx"
VOCODER = "artifacts/onnx/v1837/vocos_pretrained_vocoder.onnx"
BASE_DIR = Path("eval/golden/v1843")
FAST_JSON = BASE_DIR / "v1843_golden_fast.json"
FAST_NPZ = BASE_DIR / "v1843_golden_fast.npz"
FULL_JSON = BASE_DIR / "v1843_golden_full.json"
OUT = Path("artifacts/bench/v1843_golden")

TOLERANCE = {"mel_max_abs": 1e-5, "wav_max_abs": 1e-4}
UTMOS_SEEDS = (0, 1, 2, 3, 4)

FAST_TEXTS = [
    ("oov", "John và XYZ đang ở Hà Nội."),
    ("number_abbrev", "Năm 2026, GDP tăng 7,5% so với quý trước."),
    ("punctuation", "Hôm nay, trời đẹp; gió mát, nắng nhẹ — chúng tôi đi dạo, rồi về nhà."),
]

FULL_TEXTS = list(FAST_TEXTS)
_drift = json.loads(Path("examples/drift_texts.json").read_text(encoding="utf-8"))
for item in _drift:
    if len(FULL_TEXTS) >= 20:
        break
    FULL_TEXTS.append((item["id"], item["text"]))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def environment() -> dict:
    import onnxruntime as ort

    return {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "onnxruntime": ort.__version__,
        "numpy": np.__version__,
        "platform": platform.platform(),
        "machine": platform.machine(),
    }


def features_of(engine: Synthesizer, text: str) -> np.ndarray:
    parsed = parse_text(text, resolve_oov=True)
    return np.array([[engine.vocabs.encode(item) for item in parsed]], dtype=np.int64)


def run_pt_mel(engine: Synthesizer, text: str) -> np.ndarray:
    features = features_of(engine, text)
    device = next(engine.model.parameters()).device
    with torch.no_grad():
        out = engine.model(torch.from_numpy(features).to(device),
                           speed=torch.tensor([1.0], dtype=torch.float32, device=device),
                           gate_threshold=0.5)
    return out["mel"].detach().cpu().numpy().astype(np.float32)


def run_onnx_mel(acoustic: OnnxAcousticModel, engine: Synthesizer, text: str) -> np.ndarray:
    features = features_of(engine, text)
    return np.asarray(acoustic.run(features, speed=1.0, gate_threshold=0.5)["mel"],
                      dtype=np.float32)


def render_pt(engine: Synthesizer, text: str, path: Path) -> None:
    engine.synthesize(text, path, gate_threshold=0.5, sharpen_alpha=0.0, target_lufs=-16,
                      peak_normalize=False, max_chars=400)


def render_pt_sentence(engine: Synthesizer, text: str, path: Path) -> None:
    engine.synthesize_sentence(text, path, gate_threshold=1.01, sharpen_alpha=0.0,
                               target_lufs=-16, peak_normalize=False, max_chars=400)


def render_onnx(text: str, path: Path) -> None:
    synthesize_onnx(text, ACOUSTIC, path, vocoder_path=VOCODER, provider="cpu",
                    gate_threshold=0.5, target_lufs=-16, peak_normalize=False,
                    max_chars=400, steady=False, sample_rate=24000)


def emit_once(runtime: str, texts: list[tuple[str, str]], out_dir: Path,
              device: str = "cpu") -> dict:
    torch.set_num_threads(2)
    cfg = yaml.safe_load(Path(CFG32).read_text(encoding="utf-8"))
    engine = Synthesizer(cfg, P2, device=device)
    engine.model.eval()
    engine.vocoder.eval()
    acoustic = OnnxAcousticModel(ACOUSTIC, provider="cpu") if runtime == "onnx" else None
    rows = []
    for index, (name, text) in enumerate(texts):
        path = out_dir / f"{runtime}_{index}.wav"
        started = time.perf_counter()
        if runtime == "pytorch":
            mel = run_pt_mel(engine, text)
            render_pt(engine, text, path)
        elif runtime == "onnx":
            mel = run_onnx_mel(acoustic, engine, text)
            render_onnx(text, path)
        else:
            raise ValueError(runtime)
        elapsed = time.perf_counter() - started
        wave, sr = sf.read(path, dtype="float32")
        wave = np.asarray(wave).reshape(-1)
        rows.append({
            "name": name,
            "text": text,
            "mel_sha256": sha256_bytes(mel.tobytes()),
            "wav_sha256": sha256_file(path),
            "mel_shape": list(mel.shape),
            "wav_samples": int(wave.size),
            "sample_rate": int(sr),
            "elapsed": round(elapsed, 4),
            "mel": mel,
            "wave": wave,
        })
    return {"runtime": runtime, "device": device, "rows": rows}


def strip_arrays(result: dict) -> dict:
    return {
        "runtime": result["runtime"],
        "device": result["device"],
        "rows": [{key: row[key] for key in row if key not in ("mel", "wave")}
                 for row in result["rows"]],
    }


def compare_rows(left: dict, right: dict) -> dict:
    rows = []
    for a, b in zip(left["rows"], right["rows"]):
        mel_a, mel_b = np.asarray(a["mel"]), np.asarray(b["mel"])
        wave_a, wave_b = np.asarray(a["wave"]), np.asarray(b["wave"])
        mel_equal = mel_a.shape == mel_b.shape and np.array_equal(mel_a, mel_b)
        wave_equal = wave_a.shape == wave_b.shape and np.array_equal(wave_a, wave_b)
        mel_max = (float(np.max(np.abs(mel_a.astype(np.float64) - mel_b.astype(np.float64))))
                   if mel_a.shape == mel_b.shape else None)
        wave_max = (float(np.max(np.abs(wave_a.astype(np.float64) - wave_b.astype(np.float64))))
                    if wave_a.shape == wave_b.shape else None)
        rows.append({
            "name": a["name"],
            "mel_equal": bool(mel_equal),
            "wav_equal": bool(wave_equal),
            "mel_max_abs": mel_max,
            "wav_max_abs": wave_max,
            "mel_ok": bool(mel_equal or (mel_max is not None
                                         and mel_max <= TOLERANCE["mel_max_abs"])),
            "wav_ok": bool(wave_equal or (wave_max is not None
                                          and wave_max <= TOLERANCE["wav_max_abs"])),
        })
    return {
        "bit_exact_mel": all(row["mel_equal"] for row in rows),
        "bit_exact_wav": all(row["wav_equal"] for row in rows),
        "within_tolerance": all(row["mel_ok"] and row["wav_ok"] for row in rows),
        "rows": rows,
    }


def determinism() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "tmp"
    tmp.mkdir(exist_ok=True)
    result = {"tolerance": TOLERANCE, "runtimes": {}}
    for runtime in ("pytorch", "onnx"):
        first = emit_once(runtime, FAST_TEXTS, tmp)
        second = emit_once(runtime, FAST_TEXTS, tmp)
        same_process = compare_rows(first, second)
        # 2 tiến trình riêng, in JSON hash
        hash_runs = []
        for run in range(2):
            out_json = tmp / f"{runtime}_proc_{run}.json"
            proc = subprocess.run(
                [sys.executable, __file__, "--emit-once", runtime, str(out_json)],
                capture_output=True, text=True, env=dict(os.environ, VIFASTT_INTRA_THREADS="2"),
                timeout=600, check=False,
            )
            if proc.returncode != 0:
                hash_runs.append({"run": run, "error": proc.returncode,
                                  "stderr": proc.stderr[-800:]})
            else:
                hash_runs.append({"run": run, **json.loads(out_json.read_text(encoding="utf-8"))})
        separate = None
        if all("error" not in item for item in hash_runs):
            left, right = hash_runs[0], hash_runs[1]
            separate = {
                "bit_exact_mel": all(a["mel_sha256"] == b["mel_sha256"]
                                     for a, b in zip(left["rows"], right["rows"])),
                "bit_exact_wav": all(a["wav_sha256"] == b["wav_sha256"]
                                     for a, b in zip(left["rows"], right["rows"])),
            }
        result["runtimes"][runtime] = {
            "same_process": same_process,
            "separate_process": separate,
        }
    # MPS: chỉ tolerance, không vào fast test
    if torch.backends.mps.is_available():
        try:
            first = emit_once("pytorch", FAST_TEXTS, tmp, device="mps")
            second = emit_once("pytorch", FAST_TEXTS, tmp, device="mps")
            result["mps"] = {"available": True, **compare_rows(first, second)}
        except RuntimeError as exc:
            result["mps"] = {"available": True, "error": repr(exc)}
    else:
        result["mps"] = {"available": False}
    result["ok"] = True
    for runtime, value in result["runtimes"].items():
        if runtime == "pytorch" and not (
            value["same_process"]["bit_exact_mel"]
            and value["same_process"]["bit_exact_wav"]
        ):
            result["ok"] = False
            result["violation"] = "PyTorch CPU không bit-exact trong cùng tiến trình"
        if (runtime == "pytorch" and value["separate_process"] is not None
                and not (value["separate_process"]["bit_exact_mel"]
                         and value["separate_process"]["bit_exact_wav"])):
            result["ok"] = False
            result["violation"] = "PyTorch CPU không bit-exact giữa 2 tiến trình"
    (OUT / "determinism.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    return result


def build_fast() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "tmp_fast"
    tmp.mkdir(exist_ok=True)
    det_path = OUT / "determinism.json"
    if det_path.exists():
        det = json.loads(det_path.read_text(encoding="utf-8"))
    else:
        det = determinism()
    arrays = {}
    baseline = {
        "kind": "fast",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "environment": environment(),
        "texts": [{"name": name, "text": text} for name, text in FAST_TEXTS],
        "tolerance": TOLERANCE,
        "runtimes": {},
    }
    for runtime in ("pytorch", "onnx"):
        result = emit_once(runtime, FAST_TEXTS, tmp)
        rows = []
        for index, row in enumerate(result["rows"]):
            arrays[f"{runtime}_{index}_mel"] = row["mel"]
            arrays[f"{runtime}_{index}_wav"] = row["wave"]
            rows.append({key: row[key] for key in row if key not in ("mel", "wave")})
        d = det["runtimes"][runtime]
        bit_exact = bool(d["same_process"]["bit_exact_mel"]
                         and d["same_process"]["bit_exact_wav"]
                         and (d["separate_process"] is None
                              or (d["separate_process"]["bit_exact_mel"]
                                  and d["separate_process"]["bit_exact_wav"])))
        baseline["runtimes"][runtime] = {"bit_exact": bit_exact, "rows": rows}
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(FAST_NPZ, **arrays)
    FAST_JSON.write_text(json.dumps(baseline, ensure_ascii=False, indent=1), encoding="utf-8")
    return baseline


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


def build_full() -> dict:
    import utmosv2

    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "tmp_full"
    tmp.mkdir(exist_ok=True)
    torch.manual_seed(42)
    np.random.seed(42)
    random.seed(42)
    utmos = utmosv2.create_model(pretrained=True, config="fusion_stage3", fold=0, seed=42,
                                 device="cpu")
    cfg = yaml.safe_load(Path(CFG32).read_text(encoding="utf-8"))
    engine = Synthesizer(cfg, P2, device="cpu")
    engine.model.eval()
    engine.vocoder.eval()
    onnx_acoustic = OnnxAcousticModel(ACOUSTIC, provider="cpu")
    baseline = {
        "kind": "full",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "environment": environment(),
        "texts": [{"name": name, "text": text} for name, text in FULL_TEXTS],
        "variants": {},
    }
    variants = [("pytorch_chunk", "pytorch"), ("pytorch_sentence", "pytorch"),
                ("onnx_chunk", "onnx")]
    for label, runtime in variants:
        rows = []
        for index, (name, text) in enumerate(FULL_TEXTS):
            path = tmp / f"{label}_{index}.wav"
            if label == "pytorch_chunk":
                mel = run_pt_mel(engine, text)
                render_pt(engine, text, path)
            elif label == "pytorch_sentence":
                mel = None
                render_pt_sentence(engine, text, path)
            else:
                mel = run_onnx_mel(onnx_acoustic, engine, text)
                render_onnx(text, path)
            wave, sr = sf.read(path, dtype="float32")
            wave = np.asarray(wave).reshape(-1)
            row = {
                "name": name,
                "text": text,
                "wav_sha256": sha256_file(path),
                "wav_samples": int(wave.size),
                "sample_rate": int(sr),
                "bak": score_bak(wave, sr),
                "utmos": [score_utmos(utmos, path, seed) for seed in UTMOS_SEEDS],
            }
            if mel is not None:
                row["mel_sha256"] = sha256_bytes(np.asarray(mel, dtype=np.float32).tobytes())
                row["mel_shape"] = list(np.asarray(mel).shape)
            rows.append(row)
        baseline["variants"][label] = {"runtime": runtime, "rows": rows}
    FULL_JSON.write_text(json.dumps(baseline, ensure_ascii=False, indent=1), encoding="utf-8")
    return baseline


def check_fast(skip_onnx: bool = False) -> dict:
    baseline = json.loads(FAST_JSON.read_text(encoding="utf-8"))
    if baseline["environment"] != environment():
        return {"ok": False, "reason": "môi trường đổi, cập nhật baseline kèm mã quyết định",
                "baseline_environment": baseline["environment"],
                "current_environment": environment()}
    arrays = np.load(FAST_NPZ)
    tmp = OUT / "tmp_check"
    tmp.mkdir(exist_ok=True)
    details = []
    started = time.perf_counter()
    runtimes = ("pytorch",) if skip_onnx else ("pytorch", "onnx")
    for runtime in runtimes:
        result = emit_once(runtime, FAST_TEXTS, tmp)
        expected = baseline["runtimes"][runtime]
        for index, row in enumerate(result["rows"]):
            exp = expected["rows"][index]
            mel_ok = row["mel_sha256"] == exp["mel_sha256"]
            wav_ok = row["wav_sha256"] == exp["wav_sha256"]
            if not expected["bit_exact"]:
                mel_ref = arrays[f"{runtime}_{index}_mel"]
                wav_ref = arrays[f"{runtime}_{index}_wav"]
                mel_ok = mel_ok or (row["mel"].shape == mel_ref.shape
                                    and float(np.max(np.abs(row["mel"] - mel_ref)))
                                    <= TOLERANCE["mel_max_abs"])
                wav_ok = wav_ok or (row["wave"].shape == wav_ref.shape
                                    and float(np.max(np.abs(row["wave"] - wav_ref)))
                                    <= TOLERANCE["wav_max_abs"])
            details.append({"runtime": runtime, "name": row["name"],
                            "mel_ok": bool(mel_ok), "wav_ok": bool(wav_ok),
                            "bit_exact": expected["bit_exact"]})
    elapsed = time.perf_counter() - started
    result = {"ok": all(item["mel_ok"] and item["wav_ok"] for item in details),
              "elapsed_seconds": round(elapsed, 2), "details": details,
              "under_30s": elapsed < 30.0}
    if skip_onnx:
        result["onnx_skipped"] = "V1844.A1 đóng băng ONNX"
    return result


def emit_once_cli(runtime: str, out_json: Path) -> None:
    tmp = OUT / "tmp_emit"
    tmp.mkdir(parents=True, exist_ok=True)
    result = emit_once(runtime, FAST_TEXTS, tmp)
    out_json.write_text(json.dumps(strip_arrays(result), ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(json.dumps(strip_arrays(result), ensure_ascii=False, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--determinism", action="store_true")
    group.add_argument("--build-fast", action="store_true")
    group.add_argument("--check-fast", action="store_true")
    group.add_argument("--build-full", action="store_true")
    group.add_argument("--emit-once", choices=("pytorch", "onnx"))
    parser.add_argument("--skip-onnx", action="store_true",
                        help="V1844.A1: bỏ phần ONNX trong fast test")
    parser.add_argument("out_json", nargs="?")
    args = parser.parse_args()
    if args.determinism:
        result = determinism()
        print(json.dumps({"ok": result["ok"], "violation": result.get("violation")},
                         ensure_ascii=False, indent=1))
    elif args.build_fast:
        print(json.dumps({"built": str(FAST_JSON)}, ensure_ascii=False, indent=1))
        build_fast()
    elif args.check_fast:
        print(json.dumps(check_fast(skip_onnx=args.skip_onnx), ensure_ascii=False, indent=1))
    elif args.build_full:
        print(json.dumps({"built": str(FULL_JSON)}, ensure_ascii=False, indent=1))
        build_full()
    elif args.emit_once:
        if not args.out_json:
            parser.error("--emit-once cần đường dẫn JSON")
        emit_once_cli(args.emit_once, Path(args.out_json))


if __name__ == "__main__":
    main()
