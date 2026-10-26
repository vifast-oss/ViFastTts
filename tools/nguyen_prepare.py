"""N0 — lọc, chia split và dựng corpus MFA cho `ngochuyen_voice`.

- Không sửa audio gốc; manifest mới trong `data/ngochuyen/`.
- Lọc: parse VALID, không OOV frontend, không mã trộn chữ+số, không trùng audio/text,
  tốc độ đọc hợp lý, peak <0,95.
- Chia 90/5/5 theo hash văn bản (tất định, không rò rỉ câu trùng).
- Corpus MFA: symlink WAV + `.lab` bằng `text_norm`.

Chạy:
    .venv/bin/python tools/nguyen_prepare.py
"""

from __future__ import annotations

import argparse
import dataclasses
import enum
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from vifasttts.frontend.pipeline import parse_text
from vifasttts.types import ParseStatus

OUT = Path("data/ngochuyen")
SEED = 42
VAL_FRAC = 0.05
HOLDOUT_FRAC = 0.05


def jsonable(value):
    """Dataclass/enum → JSON thuần (giữ mã tone/status như manifest cũ)."""
    if isinstance(value, enum.Enum):
        return value.value
    if dataclasses.is_dataclass(value):
        return {field.name: jsonable(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--meta", default="data/ngochuyen/meta_raw.jsonl")
    parser.add_argument("--out-dir", default=str(OUT))
    parser.add_argument("--min-rate", type=float, default=2.5)
    parser.add_argument("--max-rate", type=float, default=6.0)
    args = parser.parse_args()
    out = Path(args.out_dir)
    rows = [json.loads(line) for line in Path(args.meta).read_text(encoding="utf-8").splitlines()
            if line.strip()]
    filters: Counter = Counter()
    seen_audio: set[str] = set()
    seen_text: set[str] = set()
    kept = []
    for row in rows:
        if row.get("duplicate_of"):
            filters["audio_trùng"] += 1
            continue
        if row["audio_sha256"] in seen_audio:
            filters["audio_trùng"] += 1
            continue
        if row["n_bad"] != 0:
            filters["parse_không_sạch"] += 1
            continue
        if row["has_mixed_alnum"]:
            filters["mã_trộn_chữ_số"] += 1
            continue
        if not (2.0 <= row["duration"] <= 20.0):
            filters["ngoài_2_20s"] += 1
            continue
        if not (args.min_rate <= row["speech_rate"] <= args.max_rate):
            filters["tốc_độ_bất_thường"] += 1
            continue
        if row["peak"] >= 0.95 or row["clip_ratio"] > 0:
            filters["clip"] += 1
            continue
        if not row["text_norm"].strip():
            filters["text_rỗng"] += 1
            continue
        text_key = row["text_norm"]
        if text_key in seen_text:
            filters["text_trùng"] += 1
            continue
        seen_audio.add(row["audio_sha256"])
        seen_text.add(text_key)
        kept.append(row)

    # Chia theo hash văn bản: độc lập với thứ tự shard, tất định.
    for row in kept:
        row["_key"] = hashlib.sha1((str(SEED) + row["text_norm"]).encode("utf-8")).hexdigest()
    kept.sort(key=lambda r: r["_key"])
    n_val = round(len(kept) * VAL_FRAC)
    n_hold = round(len(kept) * HOLDOUT_FRAC)
    split_of: dict[str, str] = {}
    for index, row in enumerate(kept):
        split = "val" if index < n_val else ("holdout" if index < n_val + n_hold else "train")
        split_of[row["id"]] = split

    (out / "splits").mkdir(parents=True, exist_ok=True)
    (out / "mfa_corpus").mkdir(parents=True, exist_ok=True)
    stats = {"seed": SEED, "filters": dict(filters), "splits": {}}
    words: set[str] = set()
    by_split: dict[str, list[dict]] = defaultdict(list)
    for row in kept:
        split = split_of[row["id"]]
        text = row["text_fixed"]
        parsed = parse_text(text)
        syllables = []
        for syllable in parsed:
            if syllable.status != ParseStatus.VALID:
                raise RuntimeError(f"{row['id']}: syllable không VALID sau lọc")
            syllables.append(jsonable(syllable))
        clip = {
            "id": row["id"],
            "audio_path": row["wav"],
            "parent": row["id"],
            "text": text,
            "text_norm": row["text_norm"],
            "duration": row["duration"],
            "syllables": syllables,
            "source": "pnnbao-ump/ngochuyen_voice",
            "split": split,
        }
        by_split[split].append(clip)
        words.update(row["text_norm"].split())
        wav_link = out / "mfa_corpus" / f"{row['id']}.wav"
        if not wav_link.exists():
            os.symlink(Path(row["wav"]).resolve(), wav_link)
        (out / "mfa_corpus" / f"{row['id']}.lab").write_text(row["text_norm"] + "\n", encoding="utf-8")

    for split, group in by_split.items():
        group.sort(key=lambda r: r["id"])
        path = out / "splits" / f"{split}.jsonl"
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in group) + "\n",
                        encoding="utf-8")
        stats["splits"][split] = {
            "clips": len(group),
            "hours": round(sum(r["duration"] for r in group) / 3600, 3),
            "syllables": sum(len(r["syllables"]) for r in group),
        }
    stats["kept"] = len(kept)
    stats["kept_hours"] = round(sum(r["duration"] for r in kept) / 3600, 3)
    stats["mfa_words"] = len(words)
    (out / "prepare_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1),
                                            encoding="utf-8")
    (out / "mfa_words.txt").write_text("\n".join(sorted(words)) + "\n", encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
