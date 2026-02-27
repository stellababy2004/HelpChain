#!/usr/bin/env bash
set -eu

if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

echo "=== RENDER START ==="
echo "[HC] render_start.sh running"
"$PY" -m flask --app run:app db upgrade --directory migrations
exec gunicorn run:app --bind 0.0.0.0:"$PORT" --workers 1
