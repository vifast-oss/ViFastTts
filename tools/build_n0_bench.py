"""tools/build_n0_bench.py — tạo bộ test N0 đóng băng từ holdout.

Mặc định lấy 200 segment holdout **chưa dùng** trong các bộ A/B/download
(`demo_texts`, `ab8_texts`, `fresh_texts`), theo khoảng index cố định.
Ghi manifest JSONL + SHA256 để mọi benchmark dùng đúng cùng một bộ.

  .venv/bin/python tools/build_n0_bench.py \
    --holdout data/ngochuyen/manifests/holdout_dur_seg_slot4.jsonl \
    --start 300 --end 500 --out data/ngochuyen/bench/bench200.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holdout", default=str(ROOT / "data/ngochuyen/manifests/holdout_dur_seg_slot4.jsonl"))
    parser.add_argument("--start", type=int, default=300)
    parser.add_argument("--end", type=int, default=500)
    parser.add_argument("--out", default=str(ROOT / "data/ngochuyen/bench/bench200.jsonl"))
    args = parser.parse_args()

    rows = [json.loads(line) for line in Path(args.holdout).read_text(encoding="utf-8").splitlines()
            if line.strip()]
    selected = rows[args.start:args.end]
    if not selected:
        raise SystemExit("Không có row trong khoảng index đã chọn")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected),
                   encoding="utf-8")
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    hours = sum((row["frame_range"][1] - row["frame_range"][0]) * 256 / 24000 for row in selected) / 3600
    print(json.dumps({"out": str(out), "rows": len(selected), "hours": round(hours, 4),
                      "sha256": digest}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
