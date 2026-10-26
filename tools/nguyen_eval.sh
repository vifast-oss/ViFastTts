#!/bin/bash
# N0 — đo checkpoint small ngochuyen trên val/holdout + demo. Chạy sau khi train xong.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
RUN=runs/acoustic_ngochuyen
CFG=$RUN/resolved_config.json
BEST=$RUN/best.pt
LAST=$RUN/last.pt
TRAIN=data/ngochuyen/manifests/train_dur_seg_slot4.jsonl
VAL=data/ngochuyen/manifests/val_dur_seg_slot4.jsonl
HOLD=data/ngochuyen/manifests/holdout_dur_seg_slot4.jsonl
CACHE=cache/ngochuyen_v2
F0=data/ngochuyen/f0_stats_v2.json
OUT=artifacts/ngochuyen/eval
mkdir -p "$OUT"
[ -f "$BEST" ] || { echo "thiếu $BEST"; exit 2; }
[ -f "$LAST" ] || LAST=$BEST

for spec in "$BEST|best" "$LAST|last"; do
  ckpt=${spec%%|*}; tag=${spec##*|}
  [ -f "$OUT/tf_${tag}.json" ] && continue
  $PY tools/eval_acoustic.py --config "$CFG" --checkpoint "$ckpt" --mode tf_seg \
    --manifest "$VAL" --clips 300 --cache-dir "$CACHE" --f0-stats "$F0" --device mps \
    --out "$OUT/tf_${tag}.json"
done

if [ ! -f "$OUT/free_best.json" ]; then
  $PY tools/eval_acoustic.py --config "$CFG" --checkpoint "$BEST" --mode free \
    --manifest "$HOLD" --clips 80 --cache-dir "$CACHE" --f0-stats "$F0" --device mps --no-cer \
    --out "$OUT/free_best.json"
fi

if [ ! -f "$OUT/creak_best.json" ]; then
  $PY tools/eval_creak.py --config "$CFG" --checkpoint "$BEST" --manifest "$VAL" \
    --cache-dir "$CACHE" --f0-stats "$F0" --clips 80 --device cpu --out "$OUT/creak_best.json"
fi

if [ ! -f "$OUT/demo_new.ok" ]; then
  $PY tools/steady_demo.py --config "$CFG" --checkpoint "$BEST" \
    --texts artifacts/ngochuyen/demo_texts.json --out artifacts/listen_ngochuyen/new \
    --device mps --clips 24 --sharpen-alpha 1.5
  touch "$OUT/demo_new.ok"
fi
echo "DONE → $OUT"
