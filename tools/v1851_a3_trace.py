"""v18.51 — A3: đối chiếu mốc cuối nhãn với ASR timestamp; truy nguyên code.

Không dùng thời lượng gốc để ánh xạ click; chỉ so mốc cuối và tìm offset/drift.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.v1851_asr_audit import transcribe_words

KEY = Path("artifacts/bench/v1850_mark/key.json")
MANIFEST = Path("data/codelung/v32/holdout_clean_v2_dur_seg_slot4.jsonl")
OUT = Path("artifacts/bench/v1851_asr/a3.json")
HOP = 256
SR = 24000


def main() -> None:
    from faster_whisper import WhisperModel

    key = json.loads(KEY.read_text(encoding="utf-8"))
    rows = {json.loads(line)["id"]: json.loads(line)
            for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()}
    items = [x for x in key["items"] if x["kind"] == "main" and x["version"] == "A"]
    model = WhisperModel("small", device="cpu", compute_type="int8")
    out = []
    for item in items:
        row = rows[item["sentence"]]
        words = transcribe_words(model, Path(item["path"]))
        n = len(row["durations"])
        label_end = (int(row.get("lead_frames") or 0) + sum(row["durations"])
                     + sum(row["gaps"][:-1]))
        label_end_s = label_end * HOP / SR
        audio_s = (row["frame_range"][1] - row["frame_range"][0]) * HOP / SR
        last = words[-1] if words else None
        first = words[0] if words else None
        out.append({
            "id": item["sentence"], "n_label": n, "n_asr_words": len(words),
            "label_end_s": round(label_end_s, 3), "audio_s": round(audio_s, 3),
            "asr_first_start": round(first["start"], 3) if first else None,
            "asr_last_end": round(last["end"], 3) if last else None,
            "tail_extra_s": round((last["end"] - label_end_s), 3) if last else None,
            "asr_last_text": last["text"] if last else None,
        })
        print(json.dumps({"done": item["sentence"], "tail": out[-1]["tail_extra_s"]}),
              flush=True)
    tails = np.asarray([x["tail_extra_s"] for x in out if x["tail_extra_s"] is not None])
    durs = np.asarray([x["audio_s"] for x in out if x["tail_extra_s"] is not None])
    corr = float(np.corrcoef(durs, tails)[0, 1]) if tails.size > 2 else None
    result = {
        "asr": "faster-whisper 1.2.1 small int8 beam=5",
        "rows": out,
        "summary": {"n": len(out), "tail_positive": int((tails > 0.1).sum()),
                    "tail_mean_s": round(float(tails.mean()), 3),
                    "tail_median_s": round(float(np.median(tails)), 3),
                    "tail_std_s": round(float(tails.std(ddof=1)), 3),
                    "corr_tail_vs_audio": round(corr, 4) if corr is not None else None,
                    "interpretation": (
                        "offset gần như cố định" if corr is not None and abs(corr) < 0.4
                        else "có xu hướng drift theo độ dài")},
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
