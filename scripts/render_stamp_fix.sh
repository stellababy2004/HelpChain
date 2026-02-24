#!/usr/bin/env bash
set -eu

if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

echo "=== STAMP FIX START ==="
"$PY" -V
TARGET_REV="b2d5c3f1a9e0"
echo "Forcing alembic_version to $TARGET_REV via SQL"
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

echo "Running upgrade"
"$PY" -m flask --app run:app db upgrade --directory migrations

echo "Starting gunicorn"
exec gunicorn run:app --bind 0.0.0.0:"$PORT"
