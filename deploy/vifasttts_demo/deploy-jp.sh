#!/usr/bin/env bash
# Deploy ViFastTts demo lên host jp (docker trực tiếp trên jp, không dùng LXD).
#
#   ./deploy/vifasttts_demo/deploy-jp.sh
#
# Yêu cầu trên host jp:
#   - docker + docker compose plugin
#   - network ngoài tên `coolify` để Traefik nhận label
#   - /opt/vifasttts đã tồn tại, có models/ (acoustic.onnx, vocoder.onnx),
#     data/ và downloads/ — deploy KHÔNG xoá các thư mục này.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="$ROOT/deploy/vifasttts_demo"
JP_HOST="${JP_HOST:-root@jp}"
REMOTE_APP="${REMOTE_APP:-/opt/vifasttts}"
SITE="${SITE:-https://tts.vifast.org}"
STAMP="$(date +%Y%m%d-%H%M%S)"

echo "==> Kiểm tra artifact bắt buộc"
test -f "$SRC/app.py" || { echo "thiếu app.py"; exit 1; }
test -d "$SRC/static" || { echo "thiếu static/"; exit 1; }

echo "==> Backup $REMOTE_APP trên $JP_HOST (bỏ data/models/downloads)"
ssh "$JP_HOST" "cd /opt && tar --exclude=vifasttts/data --exclude=vifasttts/models \
  --exclude=vifasttts/downloads -czf /tmp/vifasttts-before-$STAMP.tgz vifasttts"

echo "==> Rsync source -> $JP_HOST:$REMOTE_APP"
rsync -a --delete \
  --exclude data --exclude models --exclude downloads --exclude backups --exclude .env \
  --exclude '__pycache__' --exclude '*.pyc' \
  "$SRC/" "$JP_HOST:$REMOTE_APP/"

echo "==> Rebuild + restart container"
ssh "$JP_HOST" "cd $REMOTE_APP && docker compose up -d --build"

echo "==> Verify $SITE"
curl -fsS "$SITE/healthz" >/dev/null
curl -fsS "$SITE/api/config" >/dev/null
echo "Deploy xong. Backup: /tmp/vifasttts-before-$STAMP.tgz (trên $JP_HOST)"
