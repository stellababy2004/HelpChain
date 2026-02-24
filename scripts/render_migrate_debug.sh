#!/usr/bin/env bash
set -u

echo "=== START CMD ==="
pwd
ls -la
ls -la migrations || true
ls -la migrations/versions || true

if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

"$PY" -V

echo "=== ALEMBIC_VERSION TABLE ==="
alembic_ver_rc=0
"$PY" - <<'PYCODE' > /tmp/alembic_version.log 2>&1 || alembic_ver_rc=$?
from run import app
from sqlalchemy import text

ctx = app.app_context()
ctx.push()
from backend.helpchain_backend.src.extensions import db

rows = db.session.execute(text("SELECT version_num FROM alembic_version")).fetchall()
print(f"ALEMBIC_VERSION_ROWS={rows} ALEMBIC_VERSION_COUNT={len(rows)}")
PYCODE
cat /tmp/alembic_version.log || true
echo "ALEMBIC_VERSION_EXIT=$alembic_ver_rc"

echo "=== DB CURRENT ==="
cur_rc=0
"$PY" -m flask --app run:app db current --directory migrations > /tmp/current.log 2>&1 || cur_rc=$?
tail -n 100 /tmp/current.log || true
echo "DB_CURRENT_EXIT=$cur_rc"

echo "=== DB HEADS ==="
heads_rc=0
"$PY" -m flask --app run:app db heads --directory migrations > /tmp/heads.log 2>&1 || heads_rc=$?
tail -n 100 /tmp/heads.log || true
echo "DB_HEADS_EXIT=$heads_rc"

echo "=== RUN MIGRATIONS ==="
mig_rc=0
"$PY" -m flask --app run:app db upgrade --directory migrations > /tmp/migrate.log 2>&1 || mig_rc=$?

echo "=== MIGRATE.LOG ==="
tail -n 300 /tmp/migrate.log || true
echo "MIGRATE_EXIT=$mig_rc"

if [ "$mig_rc" -ne 0 ]; then
  echo "=== MIGRATIONS FAILED ==="
  exit "$mig_rc"
fi

echo "=== START GUNICORN ==="
exec gunicorn run:app --bind 0.0.0.0:"$PORT"
