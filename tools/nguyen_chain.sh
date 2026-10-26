#!/bin/bash
# N0 — chain dữ liệu + train acoustic small trên ngochuyen_voice.
# Chạy từ repo root. Không đụng data/codelung, cache cũ, production/ONNX.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
M=data/ngochuyen
MAN=$M/manifests
CFG=configs/small_ngochuyen.yaml
LOG=artifacts/ngochuyen/chain.log
mkdir -p "$MAN" artifacts/ngochuyen runs
say() { echo "[n0] $(date '+%F %H:%M:%S') $*" | tee -a "$LOG"; }

if [ ! -f "$M/.mfa_done" ]; then
  n=$(find "$M/mfa_aligned" -name '*.TextGrid' 2>/dev/null | wc -l | tr -d ' ')
  [ "$n" -gt 6000 ] || { echo "MFA chưa xong ($n TextGrid)"; exit 2; }
  touch "$M/.mfa_done"
fi

# S1 — TextGrid → durations → segment 3–10 s → seg_durations.
for split in train val holdout; do
  if [ ! -f "$MAN/${split}_dur.jsonl" ]; then
    say "S1 $split: mfa_to_durations"
    $PY tools/mfa_to_durations.py --textgrid-dir "$M/mfa_aligned" \
      --manifest "$M/splits/$split.jsonl" --out-dir "$MAN" \
      --report "$MAN/${split}_mfa_report.json" >> "$LOG" 2>&1
  fi
  if [ ! -f "$MAN/${split}_dur_seg.jsonl" ]; then
    say "S1 $split: cut 3–10 s"
    $PY tools/cut_segments.py --manifest "$MAN/${split}_dur.jsonl" --out-dir "$MAN" \
      --min-seconds 3 --max-seconds 10 --max-gap-frames 60 --tail-cap-frames 67 \
      >> "$LOG" 2>&1
  fi
  if [ ! -f "$MAN/${split}_dur_seg_slot4.jsonl" ]; then
    say "S1 $split: seg_durations"
    $PY tools/add_seg_durations.py --manifest "$MAN/${split}_dur_seg.jsonl" \
      --textgrid-dir "$M/mfa_aligned" --parent-dir "$MAN" --out-dir "$MAN" \
      --report "$MAN/${split}_seg_report.json" >> "$LOG" 2>&1
  fi
done

# S1b — audit bất biến + thống kê.
$PY - <<'PY' | tee -a "$LOG"
import json
from pathlib import Path
root=Path('data/ngochuyen/manifests')
for split in ('train','val','holdout'):
    rows=[json.loads(l) for l in (root/f'{split}_dur_seg_slot4.jsonl').read_text().splitlines() if l.strip()]
    seconds=0
    for r in rows:
        T=r['frame_range'][1]-r['frame_range'][0]
        assert T==sum(r['durations'])+sum(r['gaps']), r['id']
        assert len(r['seg_durations'])==len(r['durations']), r['id']
        assert all(sum(x)==d for x,d in zip(r['seg_durations'],r['durations'])), r['id']
        assert max(r['gaps'],default=0)<=60, r['id']
        seconds+=T*256/24000
    print(f'[audit] {split}: {len(rows)} segment · {seconds/3600:.3f} h · bất biến OK')
PY

# S2 — stats (mel trước cache: khoá cache gồm hash file stats).
if [ ! -f "$M/mel_stats.json" ]; then
  say "S2 mel stats"
  $PY tools/compute_mel_stats.py --manifest "$MAN/train_dur.jsonl" --config "$CFG" \
    --out "$M/mel_stats.json" --sample 800 --workers 8 --min-log-energy -6 >> "$LOG" 2>&1
fi
if [ ! -f "$M/f0_stats_v2.json" ]; then
  say "S2 f0 stats"
  $PY tools/compute_f0_stats.py --manifest "$MAN/train_dur.jsonl" --config "$CFG" \
    --out "$M/f0_stats_v2.json" --sample 2000 --workers 8 >> "$LOG" 2>&1
fi

# S3 — cache feature (mỗi clip một lần; segment dùng lại).
for split in train val holdout; do
  if [ ! -f "$M/.cache_$split" ]; then
    say "S3 cache $split"
    .venv/bin/vifasttts cache-features --manifest "$M/splits/$split.jsonl" --config "$CFG" \
      --cache-dir cache/ngochuyen_v2 --workers 8 >> "$LOG" 2>&1
    touch "$M/.cache_$split"
  fi
done

# S4 — train từ đầu 60k.
if [ ! -f "$M/.train_done" ]; then
  say "S4 train 60k"
  if [ -f runs/acoustic_ngochuyen/last.pt ]; then
    .venv/bin/vifasttts train-v2 --config "$CFG" \
      --train-manifest "$MAN/train_dur_seg_slot4.jsonl" \
      --val-manifest "$MAN/val_dur_seg_slot4.jsonl" \
      --output runs/acoustic_ngochuyen --resume runs/acoustic_ngochuyen/last.pt >> "$LOG" 2>&1
  else
    .venv/bin/vifasttts train-v2 --config "$CFG" \
      --train-manifest "$MAN/train_dur_seg_slot4.jsonl" \
      --val-manifest "$MAN/val_dur_seg_slot4.jsonl" \
      --output runs/acoustic_ngochuyen >> "$LOG" 2>&1
  fi
  touch "$M/.train_done"
  say "S4 xong"
fi
say "DONE"
