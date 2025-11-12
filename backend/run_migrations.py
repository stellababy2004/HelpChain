#!/usr/bin/env python3
"""
Run Alembic migrations programmatically from CI.

This script mirrors the previous `run_migrations.py` used in the workflow.
It loads the `backend/migrations/alembic.ini`, overrides the
`sqlalchemy.url` value with the environment `DATABASE_URL` and runs
`alembic upgrade head`.

Exit codes:
 - 0: success
 - 2: missing configuration (alembic.ini or DATABASE_URL)
 - other: exceptions bubbled up (printed to stderr)
"""

from __future__ import annotations

import os
import sys

from alembic.config import Config

from alembic import command


def main() -> int:
    root = os.path.dirname(__file__)
    migrations_ini = os.path.join(root, "migrations", "alembic.ini")

    if not os.path.isfile(migrations_ini):
        print(
            f"ERROR: migrations/alembic.ini not found at: {migrations_ini}",
            file=sys.stderr,
        )
        return 2

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is not set", file=sys.stderr)
        return 2

    print(f"Using alembic.ini: {migrations_ini}")
    print(f"Overriding sqlalchemy.url with DATABASE_URL={database_url}")

    cfg = Config(migrations_ini)
    # Ensure alembic picks up the runtime DB URL provided by CI
    cfg.set_main_option("sqlalchemy.url", database_url)

    try:
        command.upgrade(cfg, "head")
        print("Migrations finished: upgrade head")
        return 0
    except Exception as exc:  # pragma: no cover - runtime/CI path
        print("Migrations failed:", exc, file=sys.stderr)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
