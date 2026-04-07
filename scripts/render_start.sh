#!/usr/bin/env bash
set -euo pipefail

if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

echo "=== RENDER START ==="
echo "[HC] render_start.sh running"
echo "[HC] ENVIRONMENT=production"
echo "[HC] Applying database migrations..."
"$PY" -m flask --app run:app db upgrade --directory migrations
echo "[HC] flask db upgrade completed successfully"

echo "[HC] Ensuring production admin user from Render env vars on the production database..."
"$PY" backend/scripts/ensure_render_admin.py
echo "[HC] ensure_render_admin completed successfully for production"

echo "[HC] Starting gunicorn on 0.0.0.0:10000"
exec gunicorn run:app --bind 0.0.0.0:10000
