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

# Best-effort table bootstrap for production DBs that historically drifted.
echo "[HC] running schema bootstrap (create missing tables only)"
"$PY" -m backend.scripts.bootstrap_schema || echo "[HC] schema bootstrap failed; continuing startup"

# Optional recovery bootstrap for DB-backed admin auth.
# Enabled only when seed env vars are explicitly provided.
if [ -n "${ADMIN_SEED_USERNAME:-}" ] && [ -n "${ADMIN_SEED_PASSWORD:-}" ]; then
  echo "[HC] running ensure_admin.py bootstrap"
  "$PY" backend/scripts/ensure_admin.py || echo "[HC] ensure_admin.py failed; continuing startup"
fi

exec gunicorn run:app --bind 0.0.0.0:"$PORT" --workers 2
