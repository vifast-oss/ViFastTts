#!/usr/bin/env bash
# Deploy ViFastTts demo lên host jp (docker trực tiếp trên jp, không dùng LXD).
#
#   ./deploy/vifasttts_web/deploy-jp.sh
#
# Yêu cầu trên host jp:
#   - docker + docker compose plugin
#   - network ngoài tên `coolify` để Traefik nhận label
#   - /opt/vifasttts đã tồn tại, có models/ (acoustic.onnx, vocoder.onnx),
#     data/ và downloads/ — deploy KHÔNG xoá các thư mục này.
#
# Build context cần: app.py, static/, configs/, src/ (package `vifasttts` ở repo
# root), models/ (không nằm trong git — giữ sẵn trên host), Dockerfile.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/deploy/vifasttts_web"
JP_HOST="${JP_HOST:-root@jp}"
REMOTE_APP="${REMOTE_APP:-/opt/vifasttts}"
SITE="${SITE:-https://tts.vifast.org}"
STAMP="$(date +%Y%m%d-%H%M%S)"

echo "==> Kiểm tra artifact bắt buộc"
test -f "$SRC/app.py" || { echo "thiếu app.py"; exit 1; }
test -d "$SRC/static" || { echo "thiếu static/"; exit 1; }
test -d "$ROOT/src/vifasttts" || { echo "thiếu src/vifasttts (package Python)"; exit 1; }

echo "==> Backup $REMOTE_APP trên $JP_HOST (bỏ data/models/downloads)"
ssh "$JP_HOST" "cd /opt && tar --exclude=vifasttts/data --exclude=vifasttts/models \
  --exclude=vifasttts/downloads -czf /tmp/vifasttts-before-$STAMP.tgz vifasttts"

echo "==> Rsync app files -> $JP_HOST:$REMOTE_APP"
rsync -a --delete \
  --exclude data --exclude models --exclude downloads --exclude backups --exclude .env \
  --exclude src --exclude '__pycache__' --exclude '*.pyc' \
  "$SRC/" "$JP_HOST:$REMOTE_APP/"

echo "==> Rsync package src/ -> $JP_HOST:$REMOTE_APP/src/"
rsync -a --delete --exclude '__pycache__' --exclude '*.pyc' \
  "$ROOT/src/" "$JP_HOST:$REMOTE_APP/src/"

echo "==> Kiểm tra models/ có sẵn trên host"
ssh "$JP_HOST" "test -f $REMOTE_APP/models/acoustic.onnx && test -f $REMOTE_APP/models/vocoder.onnx" \
  || { echo "THIẾU models/ trên $JP_HOST — copy acoustic.onnx + vocoder.onnx vào $REMOTE_APP/models/"; exit 1; }

echo "==> Rebuild + restart container"
ssh "$JP_HOST" "cd $REMOTE_APP && docker compose up -d --build"

echo "==> Chờ service healthy (tối đa 120s)"
for i in $(seq 1 40); do
  if curl -fsS --max-time 5 "$SITE/healthz" >/dev/null 2>&1; then
    echo "healthy sau ${i}x3s"
    break
  fi
  sleep 3
  if [ "$i" -eq 40 ]; then echo "service KHÔNG healthy sau 120s"; exit 1; fi
done

echo "==> Verify $SITE"
curl -fsS --max-time 10 "$SITE/api/config" >/dev/null
echo "Deploy xong. Backup: /tmp/vifasttts-before-$STAMP.tgz (trên $JP_HOST)"
