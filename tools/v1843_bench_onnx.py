"""v18.43 — A3: benchmark ONNX vs PyTorch (chunk mode, CPU 2 thread).

Đăng ký trước (V1842.A3):
- Máy M6, CPU, 2 thread; câu ngắn ~8 âm tiết, vừa ~40, dài ~250; mỗi loại 5 câu.
- Warmup 3, đo 20 lần; cold start 5 lần (tiến trình mới); peak RSS 5 lần.
- ĐẠT khi p95 ONNX <= 1,2x PyTorch ở MỌI loại câu VÀ ít nhất một:
  cold start <= 0,5x; peak RSS <= 0,6x; dung lượng cài <= 0,3x.
- Trượt => đóng nhánh ONNX (trừ khi có nhu cầu triển khai không PyTorch).
- Lạ: CV latency > 15%; ONNX nhanh hơn > 10x; output ONNX khác hash parity.

Chạy một mình trên máy yên tĩnh. Không đổi production.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch
import yaml

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ.setdefault("VIFASTT_INTRA_THREADS", "2")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

from vifasttts.infer import Synthesizer
from vifasttts.runtime.onnx_engine import read_metadata, synthesize_onnx

CFG32 = "configs/small_codelung_v32.yaml"
P2 = "artifacts/listen_small_filt/adv_progress_p2/_ckpt/step_02000.pt"
ACOUSTIC = "artifacts/onnx/v1837/p2ema_acoustic.onnx"
VOCODER = "artifacts/onnx/v1837/vocos_pretrained_vocoder.onnx"
CANDIDATE = "configs/onnx_candidate_v1841.json"
PARITY_DIR = Path("artifacts/bench/v1840_onnx_parity")
OUT = Path("artifacts/bench/v1843_bench")
VENV_ROOT = Path("/private/tmp/opencode/v1843_install")

CRITERIA = {
    "latency_p95_ratio_max": 1.2,
    "cold_start_ratio_max": 0.5,
    "peak_rss_ratio_max": 0.6,
    "install_size_ratio_max": 0.3,
    "cv_latency_max": 0.15,
    "onnx_speedup_suspicious": 10.0,
    "warmup": 3,
    "reps": 20,
    "cold_runs": 5,
    "buckets": ("short", "mid", "long"),
}

TEXTS = {
    "short": [
        "Xin chào các bạn.",
        "Hôm nay trời rất đẹp.",
        "Tôi đang ăn cơm.",
        "Bạn khỏe không?",
        "Chúng ta đi thôi.",
    ],
    "mid": [
        "Hôm nay trời đẹp, gió mát và nắng nhẹ. Chúng tôi đi dạo quanh hồ, ngắm cảnh và trò chuyện vui vẻ.",
        "Buổi sáng, tôi thức dậy sớm, uống một ly nước, rồi mở cửa sổ để đón ánh nắng và không khí trong lành.",
        "Cô giáo bước vào lớp, chào học sinh, rồi bắt đầu bài giảng về lịch sử và văn hóa của đất nước.",
        "Trên đường về nhà, tôi ghé qua chợ, mua rau, cá và một ít trái cây để chuẩn bị bữa tối cho gia đình.",
        "Sau khi làm xong bài tập, bạn nên nghỉ ngơi, đi dạo một chút, và chuẩn bị cho ngày mai thật tốt.",
    ],
    "long": [],
}

_BASE_LONG = (
    "Trong những năm gần đây, cuộc sống ở thành phố thay đổi rất nhanh. "
    "Nhiều con đường mới được mở, các tòa nhà cao tầng mọc lên, và người dân có thêm nhiều lựa chọn đi lại. "
    "Tuy vậy, không phải ai cũng dễ thích nghi với nhịp sống mới. "
    "Có người vui vì công việc thuận lợi hơn, có người lo vì chi phí sinh hoạt tăng. "
    "Buổi tối, các quán cà phê ven đường vẫn đông, tiếng nói cười hòa với tiếng xe cộ. "
    "Ai cũng mong tìm được một khoảng lặng riêng sau một ngày dài. "
)
for _i in range(5):
    TEXTS["long"].append((_BASE_LONG * 4).replace("Trong", f"Trong ngày {_i + 1},", 1))


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def env_report() -> dict:
    import onnxruntime as ort

    try:
        load = os.getloadavg()
    except OSError:
        load = (None, None, None)
    try:
        therm = subprocess.run(["pmset", "-g", "therm"], capture_output=True, text=True,
                               timeout=10, check=False).stdout.strip().splitlines()
    except (OSError, subprocess.SubprocessError):
        therm = []
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "onnxruntime": ort.__version__,
        "numpy": np.__version__,
        "cpu_count": os.cpu_count(),
        "torch_threads": torch.get_num_threads(),
        "onnx_intra_threads": os.environ.get("VIFASTT_INTRA_THREADS"),
        "loadavg_before": [round(x, 3) if x is not None else None for x in load],
        "thermal": therm,
    }


def verify_hashes() -> dict:
    candidate = json.loads(Path(CANDIDATE).read_text(encoding="utf-8"))
    acoustic_sha = sha256(ACOUSTIC)
    vocoder_sha = sha256(VOCODER)
    acoustic_meta = read_metadata(ACOUSTIC)
    vocoder_meta = read_metadata(VOCODER)
    ok = (
        acoustic_sha == candidate["acoustic"]["sha256"]
        and vocoder_sha == candidate["vocoder"]["sha256"]
        and acoustic_meta.get("mel_hash") == vocoder_meta.get("mel_hash")
        and acoustic_meta.get("mel_hash") == candidate["acoustic"]["mel_hash"]
    )
    return {
        "acoustic_sha256": acoustic_sha,
        "vocoder_sha256": vocoder_sha,
        "expected_acoustic_sha256": candidate["acoustic"]["sha256"],
        "expected_vocoder_sha256": candidate["vocoder"]["sha256"],
        "acoustic_mel_hash": acoustic_meta.get("mel_hash"),
        "vocoder_mel_hash": vocoder_meta.get("mel_hash"),
        "ok": bool(ok),
    }


def verify_parity_output(tmp: Path) -> dict:
    """Chạy đúng cấu hình parity trên input đầu tiên, so hash WAV với artifact v18.40."""
    items = json.loads((PARITY_DIR / "inputs.json").read_text(encoding="utf-8"))
    if not items:
        return {"ok": False, "reason": "items.json rỗng"}
    text = items[0]["text"]
    path = tmp / "parity_check.wav"
    synthesize_onnx(text, ACOUSTIC, path, vocoder_path=VOCODER, provider="cpu", gate_threshold=0.5,
                    target_lufs=None, peak_normalize=False, max_chars=400, steady=False,
                    sample_rate=24000)
    got = sha256(path)
    ref_path = PARITY_DIR / "00_onnx.wav"
    if not ref_path.exists():
        return {"ok": False, "reason": "thiếu 00_onnx.wav", "got": got}
    ref = sha256(ref_path)
    return {"ok": got == ref, "got": got, "ref": ref, "text": text}


def measure_latency(texts: dict[str, list[str]], tmp: Path, reps: int, warmup: int) -> dict:
    cfg = yaml.safe_load(Path(CFG32).read_text(encoding="utf-8"))
    engine = Synthesizer(cfg, P2, device="cpu")
    engine.model.eval()
    engine.vocoder.eval()
    results: dict[str, dict] = {}
    for bucket in CRITERIA["buckets"]:
        if bucket not in texts:
            continue
        per_runtime = {"pytorch": [], "onnx": [], "durations": {"pytorch": [], "onnx": []}}
        per_sentence = []
        for index, text in enumerate(texts[bucket]):
            pt_path = tmp / f"{bucket}_{index}_pt.wav"
            onnx_path = tmp / f"{bucket}_{index}_onnx.wav"
            local = {"pytorch": [], "onnx": [], "durations": {"pytorch": [], "onnx": []}}
            for _ in range(warmup):
                engine.synthesize(text, pt_path, gate_threshold=0.5, sharpen_alpha=0.0,
                                  target_lufs=-16, peak_normalize=False, max_chars=400)
                synthesize_onnx(text, ACOUSTIC, onnx_path, vocoder_path=VOCODER, provider="cpu",
                                gate_threshold=0.5, target_lufs=-16, peak_normalize=False,
                                max_chars=400, steady=False, sample_rate=24000)
            for _ in range(reps):
                start = time.perf_counter()
                samples, sr = engine.synthesize(
                    text, pt_path, gate_threshold=0.5, sharpen_alpha=0.0,
                    target_lufs=-16, peak_normalize=False, max_chars=400)
                elapsed_pt = time.perf_counter() - start
                local["pytorch"].append(elapsed_pt)
                local["durations"]["pytorch"].append(samples / sr)

                start = time.perf_counter()
                samples, sr = synthesize_onnx(
                    text, ACOUSTIC, onnx_path, vocoder_path=VOCODER, provider="cpu",
                    gate_threshold=0.5, target_lufs=-16, peak_normalize=False,
                    max_chars=400, steady=False, sample_rate=24000)
                elapsed_onnx = time.perf_counter() - start
                local["onnx"].append(elapsed_onnx)
                local["durations"]["onnx"].append(samples / sr)
            sentence_row = {"index": index, "syllables": len(text.split())}
            for runtime in ("pytorch", "onnx"):
                values = np.array(local[runtime], dtype=float)
                sentence_row[runtime] = {
                    "p50": round(float(np.percentile(values, 50)), 6),
                    "p95": round(float(np.percentile(values, 95)), 6),
                    "cv": round(float(values.std(ddof=1) / values.mean()), 6),
                }
                per_runtime[runtime].extend(local[runtime])
                per_runtime["durations"][runtime].extend(local["durations"][runtime])
            sentence_row["ratio_p95"] = round(
                sentence_row["onnx"]["p95"] / sentence_row["pytorch"]["p95"], 6)
            per_sentence.append(sentence_row)
        row = {"per_sentence": per_sentence}
        for runtime in ("pytorch", "onnx"):
            values = np.array(per_runtime[runtime], dtype=float)
            durations = np.array(per_runtime["durations"][runtime], dtype=float)
            row[runtime] = {
                "n": int(values.size),
                "p50": round(float(np.percentile(values, 50)), 6),
                "p95": round(float(np.percentile(values, 95)), 6),
                "mean": round(float(values.mean()), 6),
                "std": round(float(values.std(ddof=1)), 6),
                "cv_pooled_across_sentences": round(float(values.std(ddof=1) / values.mean()), 6),
                "audio_seconds_p50": round(float(np.percentile(durations, 50)), 6),
                "rtf_p50": round(float(np.percentile(values, 50)
                                       / max(np.percentile(durations, 50), 1e-9)), 6),
            }
        row["ratio_p95"] = round(row["onnx"]["p95"] / row["pytorch"]["p95"], 6)
        row["cv_max_per_sentence"] = max(
            sentence[runtime]["cv"] for sentence in per_sentence
            for runtime in ("pytorch", "onnx"))
        row["cv_pooled_max"] = max(row["pytorch"]["cv_pooled_across_sentences"],
                                   row["onnx"]["cv_pooled_across_sentences"])
        results[bucket] = row
    return results


def parse_time_output(stderr: str) -> dict:
    out = {}
    for line in stderr.splitlines():
        text = line.strip()
        if text.endswith("maximum resident set size"):
            out["max_rss_bytes"] = int(text.split()[0])
        elif text.endswith("real") and len(text.split()) >= 5:
            out["real"] = float(text.split()[0])
        elif text.endswith("peak memory footprint"):
            out["peak_memory_bytes"] = int(text.split()[0])
    return out


def cold_start(tmp: Path, runs: int) -> dict:
    env = dict(os.environ, VIFASTT_INTRA_THREADS="2", OMP_NUM_THREADS="2", MKL_NUM_THREADS="2")
    text = TEXTS["short"][0]
    commands = {
        "pytorch": [
            ".venv/bin/vifasttts", "synthesize", "--config", CFG32, "--checkpoint", P2,
            "--text", text, "--output", str(tmp / "cold_pt.wav"), "--device", "cpu",
            "--target-lufs", "-16",
        ],
        "onnx": [
            ".venv/bin/vifasttts", "synthesize-onnx", "--acoustic", ACOUSTIC,
            "--vocoder", VOCODER, "--text", text, "--output", str(tmp / "cold_onnx.wav"),
            "--provider", "cpu", "--target-lufs", "-16",
        ],
    }
    result = {}
    for runtime, command in commands.items():
        rows = []
        for _ in range(runs):
            start = time.perf_counter()
            proc = subprocess.run(["/usr/bin/time", "-l", *command], capture_output=True,
                                  text=True, env=env, timeout=600, check=False)
            wall = time.perf_counter() - start
            if proc.returncode != 0:
                rows.append({"wall": wall, "error": proc.returncode,
                             "stderr": proc.stderr[-800:]})
                continue
            parsed = parse_time_output(proc.stderr)
            rows.append({"wall": wall, **parsed})
        walls = [row["wall"] for row in rows if "error" not in row]
        rss = [row["max_rss_bytes"] for row in rows
               if "error" not in row and "max_rss_bytes" in row]
        result[runtime] = {
            "runs": [{"wall": round(row["wall"], 6),
                      "max_rss_bytes": row.get("max_rss_bytes"),
                      "peak_memory_bytes": row.get("peak_memory_bytes"),
                      **({"error": row["error"]} if "error" in row else {})}
                     for row in rows],
            "wall_p50": round(float(np.median(walls)), 6) if walls else None,
            "rss_p50": int(np.median(rss)) if rss else None,
        }
    if result["pytorch"]["wall_p50"] and result["onnx"]["wall_p50"]:
        result["wall_ratio"] = round(result["onnx"]["wall_p50"] / result["pytorch"]["wall_p50"], 6)
    if result["pytorch"]["rss_p50"] and result["onnx"]["rss_p50"]:
        result["rss_ratio"] = round(result["onnx"]["rss_p50"] / result["pytorch"]["rss_p50"], 6)
    return result


def venv_size(path: Path) -> dict:
    if not path.exists():
        return {"exists": False}
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                pass
    spec = subprocess.run([str(path / "bin" / "python"), "-c",
                           "import importlib.util as u; print(bool(u.find_spec('torch')))"],
                          capture_output=True, text=True, check=False)
    packages = subprocess.run([str(path / "bin" / "pip"), "list", "--format=json"],
                              capture_output=True, text=True, check=False)
    try:
        count = len(json.loads(packages.stdout))
    except (json.JSONDecodeError, TypeError):
        count = None
    return {
        "exists": True,
        "bytes": total,
        "gb": round(total / 2**30, 3),
        "has_torch": spec.stdout.strip() == "True",
        "packages": count,
    }


def install_size() -> dict:
    """Hai venv sạch: `.[onnx]` và `.[train]` (đại diện PyTorch inference)."""
    VENV_ROOT.mkdir(parents=True, exist_ok=True)
    result = {}
    for label, extra in (("onnx", ".[onnx]"), ("train", ".[train]")):
        path = VENV_ROOT / label
        if path.exists():
            shutil.rmtree(path)
        subprocess.run([".venv/bin/python", "-m", "venv", str(path)], check=True)
        start = time.perf_counter()
        proc = subprocess.run([str(path / "bin" / "pip"), "install", "--no-input", "-q", extra],
                              cwd=_ROOT, capture_output=True, text=True, timeout=3600,
                              check=False)
        elapsed = time.perf_counter() - start
        result[label] = {
            "extra": extra,
            "install_seconds": round(elapsed, 1),
            "returncode": proc.returncode,
            "stderr_tail": proc.stderr[-500:] if proc.returncode else "",
            **venv_size(path),
        }
    if result.get("onnx", {}).get("gb") and result.get("train", {}).get("gb"):
        result["size_ratio"] = round(result["onnx"]["gb"] / result["train"]["gb"], 6)
    return result


def mps_reference(texts: dict[str, list[str]], tmp: Path) -> dict:
    if not torch.backends.mps.is_available():
        return {"available": False}
    cfg = yaml.safe_load(Path(CFG32).read_text(encoding="utf-8"))
    engine = Synthesizer(cfg, P2, device="mps")
    engine.model.eval()
    engine.vocoder.eval()
    out = {}
    for bucket in CRITERIA["buckets"]:
        values = []
        for index, text in enumerate(texts[bucket]):
            path = tmp / f"mps_{bucket}_{index}.wav"
            for _ in range(2):
                engine.synthesize(text, path, gate_threshold=0.5, sharpen_alpha=0.0,
                                  target_lufs=-16, peak_normalize=False, max_chars=400)
            for _ in range(10):
                start = time.perf_counter()
                engine.synthesize(text, path, gate_threshold=0.5, sharpen_alpha=0.0,
                                  target_lufs=-16, peak_normalize=False, max_chars=400)
                values.append(time.perf_counter() - start)
        arr = np.array(values)
        out[bucket] = {"p50": round(float(np.percentile(arr, 50)), 6),
                       "p95": round(float(np.percentile(arr, 95)), 6),
                       "n": int(arr.size)}
    return {"available": True, "buckets": out}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--skip-mps", action="store_true")
    parser.add_argument("--skip-cold", action="store_true")
    parser.add_argument("--reps", type=int, default=CRITERIA["reps"])
    parser.add_argument("--warmup", type=int, default=CRITERIA["warmup"])
    parser.add_argument("--buckets", default="short,mid,long",
                        help="danh sách bucket, vd 'short,mid' để đo lại một phần")
    parser.add_argument("--out", default="result.json")
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "tmp"
    tmp.mkdir(exist_ok=True)
    torch.set_num_threads(2)
    buckets = [bucket.strip() for bucket in args.buckets.split(",") if bucket.strip()]
    unknown = [bucket for bucket in buckets if bucket not in TEXTS]
    if unknown:
        parser.error(f"bucket không hợp lệ: {unknown}")
    texts_subset = {bucket: TEXTS[bucket] for bucket in buckets}
    partial = set(buckets) != set(CRITERIA["buckets"])

    report = {
        "criteria": CRITERIA,
        "partial_buckets": buckets if partial else None,
        "environment": env_report(),
        "hash_check": verify_hashes(),
        "parity_output_check": verify_parity_output(tmp),
        "texts": {bucket: {"count": len(texts), "syllables": [len(t.split()) for t in texts]}
                  for bucket, texts in texts_subset.items()},
    }
    (OUT / "preflight.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    if not report["hash_check"]["ok"]:
        print(json.dumps({"stop": "hash model ONNX không khớp candidate", **report["hash_check"]},
                         ensure_ascii=False, indent=1))
        raise SystemExit(2)
    if not report["parity_output_check"].get("ok"):
        print(json.dumps({"stop": "hash output ONNX không khớp parity", **report["parity_output_check"]},
                         ensure_ascii=False, indent=1))
        raise SystemExit(3)

    report["latency"] = measure_latency(texts_subset, tmp, args.reps, args.warmup)
    if not args.skip_cold:
        report["cold_start"] = cold_start(tmp, CRITERIA["cold_runs"])
    if not args.skip_install:
        report["install_size"] = install_size()
    if not args.skip_mps:
        try:
            report["mps_reference"] = mps_reference(texts_subset, tmp)
        except RuntimeError as exc:
            report["mps_reference"] = {"available": True, "error": repr(exc)}
    report["environment"]["loadavg_after"] = [round(x, 3) for x in os.getloadavg()]

    latency = report["latency"]
    latency_ok = all(row["ratio_p95"] <= CRITERIA["latency_p95_ratio_max"]
                     for row in latency.values())
    cold_ratio = report.get("cold_start", {}).get("wall_ratio")
    rss_ratio = report.get("cold_start", {}).get("rss_ratio")
    size_ratio = report.get("install_size", {}).get("size_ratio")
    secondary = {
        "cold_start": cold_ratio is not None and cold_ratio <= CRITERIA["cold_start_ratio_max"],
        "peak_rss": rss_ratio is not None and rss_ratio <= CRITERIA["peak_rss_ratio_max"],
        "install_size": size_ratio is not None and size_ratio <= CRITERIA["install_size_ratio_max"],
    }
    suspicious = []
    if any(row["cv_max_per_sentence"] > CRITERIA["cv_latency_max"]
           for row in latency.values()):
        suspicious.append("CV latency lặp lại trong từng câu > 15%")
    if any(row["pytorch"]["p95"] / max(row["onnx"]["p95"], 1e-9)
           > CRITERIA["onnx_speedup_suspicious"] for row in latency.values()):
        suspicious.append("ONNX nhanh hơn > 10x")
    if report.get("install_size", {}).get("onnx", {}).get("has_torch"):
        suspicious.append("venv .[onnx] kéo torch")

    report["verdict"] = {
        "partial": partial,
        "latency_p95_ok": bool(latency_ok),
        "secondary": secondary,
        "pass": bool(latency_ok and any(secondary.values()) and not suspicious and not partial),
        "close_branch": bool(not partial and not (latency_ok and any(secondary.values()))
                             and not suspicious),
        "suspicious": suspicious,
        "note": "ĐẠT = p95 <= 1,2x ở mọi bucket VÀ ít nhất một tiêu chí phụ; "
                "TRƯỢT => đóng nhánh ONNX (trừ khi có nhu cầu không PyTorch).",
    }
    out_path = OUT / args.out
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"criteria": CRITERIA, "latency": latency,
                      "cold_start": report.get("cold_start"),
                      "install_size": report.get("install_size"),
                      "verdict": report["verdict"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
