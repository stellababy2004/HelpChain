#!/usr/bin/env bash
set -eu

if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

echo "=== RENDER BUILD PREP START ==="
"$PY" -V
"$PY" -m pip install --upgrade pip
"$PY" -m pip install -r requirements.txt

if [ "${HC_ENABLE_DB_STAMP_FIX:-0}" = "1" ]; then
  TARGET_REV="${HC_STAMP_TARGET_REV:-b2d5c3f1a9e0}"
  echo "Stamp fix enabled. Forcing alembic_version to ${TARGET_REV}"
  "$PY" - <<PYCODE
from run import app
from sqlalchemy import text

target = "$TARGET_REV"
ctx = app.app_context()
ctx.push()
from backend.helpchain_backend.src.extensions import db

rows = db.session.execute(text("SELECT version_num FROM alembic_version")).fetchall()
print("ALEMBIC_VERSION_BEFORE=", rows)

if len(rows) == 0:
    db.session.execute(
        text("INSERT INTO alembic_version (version_num) VALUES (:v)"),
        {"v": target},
    )
elif len(rows) == 1:
    db.session.execute(
        text("UPDATE alembic_version SET version_num = :v"),
        {"v": target},
    )
else:
    db.session.execute(text("DELETE FROM alembic_version"))
    db.session.execute(
        text("INSERT INTO alembic_version (version_num) VALUES (:v)"),
        {"v": target},
    )

db.session.commit()
rows = db.session.execute(text("SELECT version_num FROM alembic_version")).fetchall()
print("ALEMBIC_VERSION_AFTER=", rows)
PYCODE
else
  echo "Stamp fix disabled (default)."
fi

echo "=== RENDER BUILD PREP DONE ==="
