"""tools/bench_external_zerotts.py — benchmark ZeroTTS (MIT, 202M, ONNX CPU) trên cùng text.

ZeroTTS là baseline mở mới cho tiếng Việt; khác giọng với N0 nên chỉ so CER/RTF,
không so mel/F0 với model nội bộ.

  .venv/bin/python tools/bench_external_zerotts.py \
    --texts artifacts/ngochuyen/fresh_texts.json \
    --out artifacts/bench_n0/external_zerotts.json

Cần model local đã tải bằng snapshot_download (xem docs/BENCHMARK_N0.md).
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
    parser.add_argument("--model-dir", default="/private/tmp/opencode/zerotts_model")
    parser.add_argument("--voice", default="maichi")
    parser.add_argument("--wav-dir", default="")
    parser.add_argument("--whisper", default="small")
    args = parser.parse_args()

    import numpy as np
    import soundfile as sf
    from audit_real_cer import _cer, _transcribe
    from faster_whisper import WhisperModel
    from zerotts import ZeroTTS

    rows = json.loads(Path(args.texts).read_text(encoding="utf-8"))
    out = Path(args.out)
    wav_dir = Path(args.wav_dir) if args.wav_dir else out.parent / "wav_zerotts"
    wav_dir.mkdir(parents=True, exist_ok=True)
    tts = ZeroTTS.from_pretrained(args.model_dir)
    whisper = WhisperModel(args.whisper, device="cpu", compute_type="int8")

    items = []
    total_audio = 0.0
    total_time = 0.0
    for row in rows:
        rid = str(row["id"])
        path = wav_dir / f"{rid}.wav"
        started = time.perf_counter()
        audio = np.asarray(tts.synthesize(str(row["text"]), voice=args.voice)).squeeze()
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
        print(f"[zerotts] {rid} · {duration:.2f}s · RTF {elapsed / max(duration, 1e-9):.3f} · CER {cer:.3f}",
              flush=True)

    result = {
        "name": "ZeroTTS",
        "model": "zeroweight-ai/ZeroTTS",
        "license": "MIT",
        "parameters": "202M",
        "voice": args.voice,
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
