#!/usr/bin/env bash
set -u

if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

echo "=== RENDER START ==="
echo "[HC] render_start.sh running"
echo "[HC] Applying database migrations..."
if "$PY" -m flask --app run:app db upgrade --directory migrations; then
  echo "[HC] flask db upgrade completed successfully"
else
  echo "[HC] WARNING: flask db upgrade failed; continuing startup"
fi
echo "[HC] Ensuring production admin user..."
if "$PY" backend/scripts/ensure_render_admin.py; then
  echo "[HC] ensure_render_admin completed successfully"
else
  echo "[HC] WARNING: ensure_render_admin failed; continuing startup"
fi

echo "[HC] Starting gunicorn on 0.0.0.0:10000"
exec gunicorn run:app --bind 0.0.0.0:10000
