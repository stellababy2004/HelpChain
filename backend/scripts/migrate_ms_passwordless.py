"""Standalone SQLite migration for passwordless Microsoft OIDC fields.

Problem addressed: importing the full Flask app seeds data and queries the
`users` table before the new columns exist, causing OperationalError. This
script bypasses the Flask app and operates directly on the SQLite file.

Adds columns (idempotent checks):
    - ms_oid TEXT (unique index)
    - password_disabled INTEGER NOT NULL DEFAULT 0
Indexes:
    - ix_users_ms_oid UNIQUE
    - ix_users_email (if not already existing)

Usage (from backend root):
    .\.venv\Scripts\python.exe .\scripts\migrate_ms_passwordless.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
DB_FILE = INSTANCE_DIR / "volunteers.db"
DB_URI = f"sqlite:///{DB_FILE}"  # SQLAlchemy URI


def connect_engine() -> Engine:
    if not DB_FILE.exists():
        raise SystemExit(
            f"Database file not found: {DB_FILE}. Start app once to create it."
        )
    return create_engine(DB_URI, future=True)


def column_exists(engine: Engine, table: str, column: str) -> bool:
    with engine.connect() as conn:
        r = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(str(row[1]) == column for row in r)


def create_index(engine: Engine, sql: str) -> None:
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
    except Exception as e:
        print(f"Index creation skipped (maybe exists): {e}")


def main() -> None:
    print(f"Using DB file: {DB_FILE}")
    engine = connect_engine()

    # Добавяне ms_oid
    try:
        if not column_exists(engine, "users", "ms_oid"):
            print("Adding column ms_oid ...")
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN ms_oid TEXT"))
        else:
            print("Column ms_oid already exists.")
    except Exception as e:
        print(f"Failed adding ms_oid (maybe exists or locked): {e}")

    # Добавяне password_disabled
    try:
        if not column_exists(engine, "users", "password_disabled"):
            print("Adding column password_disabled ...")
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "ALTER TABLE users ADD COLUMN password_disabled INTEGER DEFAULT 0 NOT NULL"
                    )
                )
        else:
            print("Column password_disabled already exists.")
    except Exception as e:
        print(f"Failed adding password_disabled: {e}")

    # Индекси
    print("Ensuring indexes ...")
    create_index(
        engine, "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_ms_oid ON users(ms_oid)"
    )
    create_index(engine, "CREATE INDEX IF NOT EXISTS ix_users_email ON users(email)")

    print("Migration complete.")


if __name__ == "__main__":
    main()
