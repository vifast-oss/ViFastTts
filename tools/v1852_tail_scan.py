"""v18.52 — quét bộ dò đuôi trên segment; ghi JSONL từng segment.

Không tổng hợp tỉ lệ ở bước này (theo V18.52.B3).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from vifasttts.data.tail_detect import measure_tail, tail_start_frame

MANIFESTS = [
    ("train", "data/codelung/v32/train_clean_v2_dur_seg_slot4.jsonl"),
    ("holdout", "data/codelung/v32/holdout_clean_v2_dur_seg_slot4.jsonl"),
]
OUT = Path("artifacts/bench/v1852_tail/scan.jsonl")
HOP = 256
SR = 24000


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = 0
    with out.open("w", encoding="utf-8") as handle:
        for split, path in MANIFESTS:
            rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
                    if line.strip()]
            for row in rows:
                if args.limit and done >= args.limit:
                    break
                start, end = (int(x) for x in row["frame_range"])
                wav, sr = sf.read(row["audio_path"], dtype="float32")
                wav = np.asarray(wav).reshape(-1)
                if sr != SR:
                    raise RuntimeError(f"{row['audio_path']}: sr {sr} != {SR}")
                segment = wav[start * HOP:end * HOP]
                tail = tail_start_frame(int(row.get("lead_frames") or 0),
                                        row["durations"], row["gaps"])
                metrics = measure_tail(segment, SR, tail * HOP, HOP)
                handle.write(json.dumps({
                    "id": row["id"], "split": split, "parent": row["parent"],
                    "seconds": round(segment.size / SR, 4),
                    "tail_start": tail, "n_syllables": len(row["durations"]),
                    "last_duration": int(row["durations"][-1]),
                    "last_text": row["syllables"][-1].get("normalized", ""),
                    **metrics,
                }, ensure_ascii=False) + "\n")
                done += 1
                if done % 200 == 0:
                    print(json.dumps({"done": done}), flush=True)
            if args.limit and done >= args.limit:
                break
    print(json.dumps({"done": done, "out": str(out)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
