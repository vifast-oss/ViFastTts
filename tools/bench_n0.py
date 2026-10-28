"""tools/bench_n0.py — chấm nhiều checkpoint N0 trên CÙNG một bộ test đóng băng.

Một lệnh chạy:
  - tf_seg: mel z/dB, VUV, duration, F0 theo thanh
  - free: CER-100, pause F1, length ratio, mel speech
  - creak: HNR/jitter/glottalization theo thanh
  - tone paths: accuracy A (thật) / B (copy) / C (free-run)

Ví dụ:
  .venv/bin/python tools/bench_n0.py \
    --manifest data/ngochuyen/bench/bench200.jsonl \
    --out artifacts/bench_n0 \
    --model small=runs/acoustic_ngochuyen_q/resolved_config.json=runs/acoustic_ngochuyen_q/init_q.pt \
    --model base40=runs/acoustic_ngochuyen_base/resolved_config.json=runs/acoustic_ngochuyen_base/best.pt

Không chấm A/B tai người; dùng `tools/ab_base_vs_small.py` cho phần đó.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: list[str], label: str) -> dict:
    print(f"[bench] {label}: {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)
    out = Path(command[command.index("--out") + 1])
    return json.loads(out.read_text(encoding="utf-8"))


def _mean(value: object) -> float | None:
    if isinstance(value, dict):
        raw = value.get("mean", value.get("median"))
        return float(raw) if isinstance(raw, (int, float)) else None
    return float(value) if isinstance(value, (int, float)) else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--model", action="append", required=True,
                        help="name=config=checkpoint (lặp lại được)")
    parser.add_argument("--cache-dir", default="cache/ngochuyen_v2")
    parser.add_argument("--f0-stats", default="data/ngochuyen/f0_stats_v2.json")
    parser.add_argument("--tone-ruler", default="artifacts/ngochuyen/tone_ruler/tone_ruler.pt")
    parser.add_argument("--vocoder", default="artifacts/pretrained/vocos-mel-24khz/pytorch_model.bin")
    parser.add_argument("--tf-clips", type=int, default=200)
    parser.add_argument("--free-clips", type=int, default=100)
    parser.add_argument("--creak-clips", type=int, default=80)
    parser.add_argument("--tone-clips", type=int, default=60)
    parser.add_argument("--device", default="mps")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    manifest = Path(args.manifest)
    if not manifest.exists():
        raise SystemExit(f"Thiếu manifest: {manifest}")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {
        "manifest": str(manifest),
        "manifest_sha256": _sha256(manifest),
        "clips": {"tf": args.tf_clips, "free": args.free_clips,
                  "creak": args.creak_clips, "tone": args.tone_clips},
        "models": {},
    }

    for spec in args.model:
        try:
            name, config, checkpoint = spec.split("=", 2)
        except ValueError as error:
            raise SystemExit(f"--model phải có dạng name=config=checkpoint: {spec}") from error
        if not Path(config).exists() or not Path(checkpoint).exists():
            raise SystemExit(f"Thiếu config/checkpoint cho {name}")
        base = out / name
        base.mkdir(parents=True, exist_ok=True)

        tf_out = base / "tf.json"
        free_out = base / "free.json"
        creak_out = base / "creak.json"
        tone_out = base / "tone.json"
        if args.force or not tf_out.exists():
            _run([sys.executable, "tools/eval_acoustic.py", "--config", config,
                  "--checkpoint", checkpoint, "--mode", "tf_seg", "--manifest", str(manifest),
                  "--clips", str(args.tf_clips), "--cache-dir", args.cache_dir,
                  "--f0-stats", args.f0_stats, "--device", args.device, "--out", str(tf_out)],
                 f"{name}/tf")
        if args.force or not free_out.exists():
            _run([sys.executable, "tools/eval_acoustic.py", "--config", config,
                  "--checkpoint", checkpoint, "--mode", "free", "--manifest", str(manifest),
                  "--clips", str(args.free_clips), "--cache-dir", args.cache_dir,
                  "--f0-stats", args.f0_stats, "--device", args.device, "--out", str(free_out)],
                 f"{name}/free+CER")
        if args.force or not creak_out.exists():
            _run([sys.executable, "tools/eval_creak.py", "--config", config,
                  "--checkpoint", checkpoint, "--manifest", str(manifest),
                  "--cache-dir", args.cache_dir, "--f0-stats", args.f0_stats,
                  "--clips", str(args.creak_clips), "--device", "cpu", "--out", str(creak_out)],
                 f"{name}/creak")
        if args.force or not tone_out.exists():
            _run([sys.executable, "tools/eval_tone_paths.py", "--manifest", str(manifest),
                  "--config", config, "--checkpoint", checkpoint,
                  "--vocoder", args.vocoder, "--ruler", args.tone_ruler,
                  "--f0-stats", args.f0_stats, "--cache-dir", args.cache_dir,
                  "--clips", str(args.tone_clips), "--device", "cpu", "--out", str(tone_out)],
                 f"{name}/tone")

        tf = json.loads(tf_out.read_text(encoding="utf-8"))
        free = json.loads(free_out.read_text(encoding="utf-8"))
        creak = json.loads(creak_out.read_text(encoding="utf-8"))
        tone = json.loads(tone_out.read_text(encoding="utf-8"))
        paths = tone.get("paths", {}) if isinstance(tone, dict) else {}
        summary["models"][name] = {
            "config": config,
            "checkpoint": checkpoint,
            "checkpoint_sha256": _sha256(Path(checkpoint)),
            "tf": {
                "mel_z": _mean(tf.get("mel_l1_z")),
                "mel_db": _mean(tf.get("mel_mae_db_speech")),
                "vuv": _mean(tf.get("vuv_accuracy")),
                "duration_mae_ms": tf.get("duration_mae_ms"),
                "f0_rmse_cents": tf.get("f0_rmse_cents_by_tone"),
            },
            "free": {
                "cer": _mean(free.get("cer")),
                "mel_db_speech": _mean(free.get("mel_mae_db_speech")),
                "pause_f1": free.get("pause_f1"),
                "length_ratio": _mean(free.get("length_ratio")),
                "rtf": free.get("rtf"),
            },
            "creak": creak.get("groups"),
            "tone": {
                "A": paths.get("A", {}).get("accuracy"),
                "B": paths.get("B", {}).get("accuracy"),
                "C": paths.get("C", {}).get("accuracy"),
            },
        }
        print(f"[bench] xong {name}", flush=True)

    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [
        "# N0 internal benchmark",
        "",
        f"- Manifest: `{manifest}`",
        f"- SHA256: `{summary['manifest_sha256']}`",
        "",
        "| Model | mel z | mel dB | CER | pause F1 | tone C |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, item in summary["models"].items():
        lines.append(
            f"| {name} | {item['tf']['mel_z']:.4f} | {item['tf']['mel_db']:.3f} | "
            f"{item['free']['cer']} | {item['free']['pause_f1']} | {item['tone']['C']} |"
        )
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[bench] report: {out / 'REPORT.md'}", flush=True)


if __name__ == "__main__":
    main()
