"""v18.51 — A1/A2: ASR timestamp kiểm click cấy + đếm dư đầu/giữa/cuối 20 câu V18.50.

ASR: faster-whisper 1.2.1, model `small`, int8, language vi, word_timestamps.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

KEY = Path("artifacts/bench/v1850_mark/key.json")
ANSWERS = Path("artifacts/bench/v1850_mark/answers.csv")
MANIFEST = Path("data/codelung/v32/holdout_clean_v2_dur_seg_slot4.jsonl")
OUT = Path("artifacts/bench/v1851_asr")
SR = 24000


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", str(text)).lower()
    return re.sub(r"[^\w\sÀ-ỹ]", " ", text).strip()


def syllables(text: str) -> list[str]:
    return [x for x in normalize(text).split() if x]


def edit_distance(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(ref: list[str], hyp: list[str]) -> float:
    return edit_distance(ref, hyp) / max(len(ref), 1)


def transcribe_words(model, path: Path) -> list[dict]:
    wave, sr = sf.read(path, dtype="float32")
    wave = np.asarray(wave).reshape(-1)
    if sr != 16000:
        wave = resample_poly(wave.astype(np.float64), 16000, sr).astype(np.float32)
    segments, _info = model.transcribe(
        wave, language="vi", beam_size=5, word_timestamps=True,
        vad_filter=False, condition_on_previous_text=False,
    )
    words = []
    for seg in segments:
        for word in seg.words or []:
            parts = syllables(word.word)
            if not parts:
                continue
            span = (word.end - word.start) / len(parts)
            for k, part in enumerate(parts):
                words.append({"text": part, "start": word.start + k * span,
                              "end": word.start + (k + 1) * span})
    return words


def match(label: list[str], hyp: list[str]) -> dict:
    matcher = SequenceMatcher(a=label, b=hyp, autojunk=False)
    ops = matcher.get_opcodes()
    start_extra, mid_extra, end_extra = [], [], []
    missing = []
    for tag, i1, i2, j1, j2 in ops:
        if tag == "insert":
            if i1 == 0:
                start_extra.extend(hyp[j1:j2])
            elif i1 >= len(label):
                end_extra.extend(hyp[j1:j2])
            else:
                mid_extra.extend(hyp[j1:j2])
        elif tag == "delete":
            missing.extend(label[i1:i2])
        elif tag == "replace":
            missing.extend(label[i1:i2])
            if i1 == 0:
                start_extra.extend(hyp[j1:j2])
            elif i1 >= len(label):
                end_extra.extend(hyp[j1:j2])
            else:
                mid_extra.extend(hyp[j1:j2])
    return {"start_extra": start_extra, "mid_extra": mid_extra,
            "end_extra": end_extra, "missing": missing,
            "cer": round(cer(label, hyp), 4)}


def main() -> None:
    from faster_whisper import WhisperModel

    OUT.mkdir(parents=True, exist_ok=True)
    key = json.loads(KEY.read_text(encoding="utf-8"))
    rows = {json.loads(line)["id"]: json.loads(line)
            for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line.strip()}
    answers = {}
    import csv

    with ANSWERS.open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            answers[row["item_id"]] = {
                "clicked": [int(x) for x in (row.get("syllables") or "").split(";") if x],
                "mismatch": int((row.get("mismatch") or "0").strip() or 0)}
    model = WhisperModel("small", device="cpu", compute_type="int8")
    # A1 — 3 mục cấy
    a1 = []
    for item in [x for x in key["items"] if x["kind"] == "artificial"]:
        words = transcribe_words(model, Path(item["path"]))
        sent = item["sentence"]
        info = key["artificial_positions"][sent]
        target = int(info["target"])
        burst = float(info["start"])
        clicked = answers.get(item["id"], {}).get("clicked", [])
        def at(idx: int, words=words) -> dict | None:
            if not words:
                return None
            return words[min(max(idx - 1, 0), len(words) - 1)]
        target_word = at(target)
        clicked_times = [{"index": idx, **at(idx)} for idx in clicked if at(idx)]
        a1.append({"id": item["id"], "sentence": sent, "target_index": target,
                   "burst_seconds": burst,
                   "asr_target": target_word,
                   "clicked": clicked, "clicked_times": clicked_times,
                   "target_matches_asr": bool(target_word and abs(target_word["start"] - burst) < 0.5),
                   "clicked_near_burst": bool(any(abs(x["start"] - burst) <= 0.5
                                                  for x in clicked_times))})
    # A2 — 20 câu A
    by_parent = {}
    for row in rows.values():
        by_parent.setdefault(row["parent"], []).append(row)
    for values in by_parent.values():
        values.sort(key=lambda r: int(r["frame_range"][0]))
    a2 = []
    for item in [x for x in key["items"] if x["kind"] == "main" and x["version"] == "A"]:
        sent = item["sentence"]
        row = rows[sent]
        words = transcribe_words(model, Path(item["path"]))
        label = [s["normalized"] for s in row["syllables"]]
        hyp = [w["text"] for w in words]
        match_info = match(label, hyp)
        end_extra = match_info["end_extra"]
        next_head = []
        next_id = None
        current_end = int(row["frame_range"][1])
        for other in by_parent.get(row["parent"], []):
            if int(other["frame_range"][0]) >= current_end and other["id"] != sent:
                next_id = other["id"]
                next_head = [s["normalized"] for s in other["syllables"][:15]]
                break
        tail_cer = cer(next_head, end_extra) if next_head and end_extra else None
        a2.append({"id": sent, "n_label": len(label), "n_asr": len(hyp),
                   "start_extra": match_info["start_extra"],
                   "mid_extra": match_info["mid_extra"],
                   "end_extra": end_extra, "missing": match_info["missing"],
                   "cer": match_info["cer"], "next_id": next_id,
                   "tail_vs_next_head_cer": round(tail_cer, 4) if tail_cer is not None else None,
                   "ear_mismatch": bool(answers.get(item["id"], {}).get("mismatch"))})
        print(json.dumps({"done": sent}), flush=True)
    # A2 verdict
    mismatch = [x for x in a2 if x["ear_mismatch"]]
    tail_ok = [x for x in mismatch
               if x["end_extra"] and x["tail_vs_next_head_cer"] is not None
               and x["tail_vs_next_head_cer"] <= 0.3]
    tail_frac = len(tail_ok) / max(len(mismatch), 1)
    asr_mismatch = [x for x in a2 if x["cer"] > 0.05 or x["start_extra"] or x["end_extra"]]
    agree = sum(1 for x in a2 if bool(x["ear_mismatch"]) == bool(x["cer"] > 0.05 or x["end_extra"]))
    result = {
        "asr": {"package": "faster-whisper 1.2.1", "model": "small", "compute_type": "int8"},
        "a1": a1, "a2": a2,
        "a2_summary": {"mismatch_sentences": len(mismatch), "tail_extra": len(tail_ok),
                       "tail_fraction": round(tail_frac, 4),
                       "asr_mismatch": len(asr_mismatch),
                       "ear_asr_agree": agree, "n": len(a2),
                       "verdict": ("LỆCH MỐC CUỐI" if tail_frac >= 0.7
                                   else "CHƯA ĐỦ BẰNG CHỨNG LỆCH MỐC CUỐI")},
    }
    (OUT / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print(json.dumps(result["a2_summary"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
