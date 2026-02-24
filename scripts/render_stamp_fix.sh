#!/usr/bin/env bash
set -u

if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

echo "=== STAMP FIX START ==="
"$PY" -V
echo "Stamping alembic_version to b2d5c3f1a9e0"
"$PY" -m flask --app run:app db stamp b2d5c3f1a9e0 --directory migrations

echo "Running upgrade"
"$PY" -m flask --app run:app db upgrade --directory migrations

echo "Starting gunicorn"
exec gunicorn run:app --bind 0.0.0.0:"$PORT"
