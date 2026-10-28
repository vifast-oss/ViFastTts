"""tools/bench_text_tts.py — benchmark text-only (không cần audio thật) cho model nội bộ.

Sinh WAV từ `texts.json` (list `{id,text}`), đo:
  - RTF = thời gian tổng hợp / thời lượng audio
  - CER = khoảng cách ký tự giữa text gốc và Whisper transcript
  - audio duration

Dùng cùng bộ text với `bench_external_zerotts.py` để so sánh công bằng ở mức
đọc đúng chữ / tốc độ; không so mel vì khác giọng.

  .venv/bin/python tools/bench_text_tts.py --name small \
    --config runs/acoustic_ngochuyen_q/resolved_config.json \
    --checkpoint runs/acoustic_ngochuyen_q/init_q.pt \
    --texts artifacts/ngochuyen/fresh_texts.json \
    --out artifacts/bench_n0/text_small.json --device mps --sharpen-alpha 0
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--texts", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--wav-dir", default="")
    parser.add_argument("--device", default="mps")
    parser.add_argument("--sharpen-alpha", type=float, default=0.0)
    parser.add_argument("--whisper", default="small")
    args = parser.parse_args()

    import soundfile as sf
    import yaml
    from audit_real_cer import _cer, _transcribe
    from faster_whisper import WhisperModel

    from vifasttts.infer import Synthesizer

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    rows = json.loads(Path(args.texts).read_text(encoding="utf-8"))
    out = Path(args.out)
    wav_dir = Path(args.wav_dir) if args.wav_dir else out.parent / f"wav_{args.name}"
    wav_dir.mkdir(parents=True, exist_ok=True)
    engine = Synthesizer(config, args.checkpoint, device=args.device)
    whisper = WhisperModel(args.whisper, device="cpu", compute_type="int8")

    items = []
    total_audio = 0.0
    total_time = 0.0
    for row in rows:
        rid = str(row["id"])
        path = wav_dir / f"{rid}.wav"
        started = time.perf_counter()
        engine.synthesize(str(row["text"]), path, sharpen_alpha=args.sharpen_alpha)
        elapsed = time.perf_counter() - started
        data, rate = sf.read(path, dtype="float32")
        duration = len(data) / rate
        heard = _transcribe(whisper, data, rate)
        cer = _cer(str(row["text"]), heard)
        total_audio += duration
        total_time += elapsed
        items.append({"id": rid, "text": row["text"], "wav": str(path),
                      "audio_seconds": round(duration, 3), "elapsed_seconds": round(elapsed, 3),
                      "rtf": round(elapsed / max(duration, 1e-9), 4),
                      "cer": round(cer, 4), "whisper": heard})
        print(f"[{args.name}] {rid} · {duration:.2f}s · RTF {elapsed / max(duration, 1e-9):.3f} · CER {cer:.3f}",
              flush=True)

    result = {
        "name": args.name,
        "config": args.config,
        "checkpoint": args.checkpoint,
        "sharpen_alpha": args.sharpen_alpha,
        "clips": len(items),
        "audio_seconds": round(total_audio, 3),
        "elapsed_seconds": round(total_time, 3),
        "rtf": round(total_time / max(total_audio, 1e-9), 4),
        "cer_mean": round(sum(item["cer"] for item in items) / max(len(items), 1), 4),
        "items": items,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {out}")


if __name__ == "__main__":
    main()
