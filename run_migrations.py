#!/usr/bin/env python3
"""Run Alembic migrations using migrations/alembic.ini.

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
    alembic_ini = repo_root / "migrations" / "alembic.ini"

    if not alembic_ini.exists():
        print(f"ERROR: alembic.ini not found at {alembic_ini}", file=sys.stderr)
        return 2

    # Sanity-check the alembic.ini to avoid cryptic configparser errors later.
    # If the first meaningful (non-empty, non-comment) line doesn't start
    # with '[' then it's not a valid INI file for Alembic — fail early with
    # a helpful error message so CI logs are actionable.
    try:
        with alembic_ini.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line:
                    continue
                if line.startswith("#") or line.startswith(";"):
                    continue
                if not line.startswith("["):
                    print(
                        f"ERROR: malformed alembic.ini — first non-comment line does not start with '[': {line!r}",
                        file=sys.stderr,
                    )
                    return 3
                break
    except Exception as exc:
        print("ERROR: could not read alembic.ini:", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 4

    database_url = os.environ.get("DATABASE_URL", "sqlite:///test.db")

    logging.basicConfig(level=logging.INFO)

    cfg = Config(str(alembic_ini))
    # Ensure Alembic uses the absolute migrations folder regardless of CWD
    cfg.set_main_option("script_location", str(repo_root / "migrations"))
    cfg.set_main_option("sqlalchemy.url", database_url)

    print(
        f"Running Alembic migrations (alembic.ini={alembic_ini}) against: {database_url}"
    )

    try:
        # Alembic env.py expects `flask.current_app` (Flask-Migrate integration).
        # Ensure we run inside the application's context so env.py can access
        # the Flask-Migrate extension and DB engine.
        from backend.appy import app

        with app.app_context():
            command.upgrade(cfg, "head")
    except Exception as exc:
        print("ERROR: Alembic migration failed:", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1

    print("Migrations applied successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
