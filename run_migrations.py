#!/usr/bin/env python3
"""Run Alembic migrations using backend/migrations/alembic.ini.

This script is intentionally simple and safe for CI.
It reads DATABASE_URL from the environment (falls back to sqlite:///test.db),
overrides the sqlalchemy.url option in the Alembic config, and runs `upgrade head`.

Placing this at the repo root matches how the CI workflow invokes
`python -u run_migrations.py`.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config


def main() -> int:
    repo_root = Path(__file__).resolve().parent
    alembic_ini = repo_root / "backend" / "migrations" / "alembic.ini"

    if not alembic_ini.exists():
        print(f"ERROR: alembic.ini not found at {alembic_ini}", file=sys.stderr)
        return 2

    database_url = os.environ.get("DATABASE_URL", "sqlite:///test.db")

    logging.basicConfig(level=logging.INFO)

    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", database_url)

    print(
        f"Running Alembic migrations (alembic.ini={alembic_ini}) against: {database_url}"
    )

    try:
        command.upgrade(cfg, "head")
    except Exception as exc:
        print("ERROR: Alembic migration failed:", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1

    print("Migrations applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
