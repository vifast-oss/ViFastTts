#!/usr/bin/env bash
# Quickstart N0: clone repo → chạy script → mở http://127.0.0.1:8090
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.venv-demo"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8090}"

pick_python() {
  local cmd
  for cmd in "${PYTHON:-}" python3.12 python3.11 python3; do
    [ -n "$cmd" ] || continue
    command -v "$cmd" >/dev/null 2>&1 || continue
    if "$cmd" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      printf '%s\n' "$cmd"; return 0
    fi
  done
  echo "Cần Python >= 3.11 (đặt PYTHON=/đường/dẫn/python3.12)." >&2
  return 1
}
PY="$(pick_python)"

"$ROOT/scripts/fetch_ngochuyen_models.sh"
if [ ! -x "$VENV/bin/python" ]; then
  echo "Tạo venv demo: $VENV"
  "$PY" -m venv "$VENV"
fi
"$VENV/bin/python" -m pip install -q --disable-pip-version-check -r "$ROOT/deploy/vifasttts_demo/requirements.txt"
export PYTHONPATH="$ROOT/src"
export MODEL_DIR="$ROOT/artifacts/onnx/n0"
echo "Mở http://$HOST:$PORT  (Ctrl-C để dừng)"
exec "$VENV/bin/uvicorn" deploy.vifasttts_demo.app:app --host "$HOST" --port "$PORT"
