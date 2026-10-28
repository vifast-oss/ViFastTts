"""tools/bench_external_vieneu.py — benchmark VieNeu-TTS v3 Turbo trên cùng text.

VieNeu là baseline mở mạnh cho tiếng Việt (Apache-2.0, 131M, 48 kHz, CPU).
Khác giọng với N0 nên chỉ so CER/RTF/nghe, không so mel/F0.

  .venv/bin/python tools/bench_external_vieneu.py \
    --texts artifacts/ngochuyen/fresh_texts.json \
    --out artifacts/bench_n0/external_vieneu_turbo.json
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
    parser.add_argument("--texts", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--mode", default="v3turbo", choices=("v3turbo", "v3nano"))
    parser.add_argument("--wav-dir", default="")
    parser.add_argument("--whisper", default="small")
    args = parser.parse_args()

    import numpy as np
    import soundfile as sf
    from audit_real_cer import _cer, _transcribe
    from faster_whisper import WhisperModel
    from vieneu import Vieneu

    rows = json.loads(Path(args.texts).read_text(encoding="utf-8"))
    out = Path(args.out)
    wav_dir = Path(args.wav_dir) if args.wav_dir else out.parent / f"wav_vieneu_{args.mode}"
    wav_dir.mkdir(parents=True, exist_ok=True)
    tts = Vieneu(mode=args.mode)
    whisper = WhisperModel(args.whisper, device="cpu", compute_type="int8")

    items = []
    total_audio = 0.0
    total_time = 0.0
    for row in rows:
        rid = str(row["id"])
        path = wav_dir / f"{rid}.wav"
        started = time.perf_counter()
        audio = np.asarray(tts.infer(text=str(row["text"]))).squeeze()
        elapsed = time.perf_counter() - started
        sf.write(path, audio, tts.sample_rate)
        duration = len(audio) / tts.sample_rate
        heard = _transcribe(whisper, audio, tts.sample_rate)
        cer = _cer(str(row["text"]), heard)
        total_audio += duration
        total_time += elapsed
        items.append({"id": rid, "text": row["text"], "wav": str(path),
                      "audio_seconds": round(duration, 3), "elapsed_seconds": round(elapsed, 3),
                      "rtf": round(elapsed / max(duration, 1e-9), 4),
                      "cer": round(cer, 4), "whisper": heard})
        print(f"[vieneu-{args.mode}] {rid} · {duration:.2f}s · "
              f"RTF {elapsed / max(duration, 1e-9):.3f} · CER {cer:.3f}", flush=True)

    result = {
        "name": f"VieNeu-{args.mode}",
        "model": "pnnbao-ump/VieNeu-TTS-v3-Turbo" if args.mode == "v3turbo" else "pnnbao-ump/VieNeu-TTS-v3-Nano",
        "license": "Apache-2.0",
        "parameters": "131M" if args.mode == "v3turbo" else "48M",
        "mode": args.mode,
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
