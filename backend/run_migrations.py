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

# Optional helper (SQLAlchemy URL parsing)
try:  # keep import optional for environments without SQLAlchemy v1.4+ helpers
    from sqlalchemy.engine import make_url
except Exception:  # pragma: no cover - best-effort import
    try:
        from sqlalchemy.engine.url import make_url  # type: ignore
    except Exception:
        make_url = None  # type: ignore


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

    # Defensive: if DATABASE_URL points to a sqlite file, ensure the parent
    # directory exists and the file is touchable. In CI the path may be
    # absolute (e.g. /home/runner/...) or relative; SQLite will fail with
    # "unable to open database file" if the directory doesn't exist or
    # permissions are wrong.
    try:  # pragma: no cover - environment-specific
        if make_url is not None:
            url = make_url(database_url)
            if getattr(url, "drivername", "") == "sqlite":
                db_path = url.database
                if db_path:
                    # If relative path, make it relative to repository root
                    if not os.path.isabs(db_path):
                        db_path = os.path.join(root, db_path)
                    parent = os.path.dirname(db_path) or "."
                    os.makedirs(parent, exist_ok=True)

                    # Optional reset: when HELPCHAIN_RESET_DB is set, delete any
                    # existing sqlite file first to avoid conflicts between
                    # previously created schema (e.g. via create_all) and Alembic.
                    try:
                        reset = os.environ.get("HELPCHAIN_RESET_DB", "").lower() in (
                            "1",
                            "true",
                            "yes",
                        )
                    except Exception:
                        reset = False
                    if reset and os.path.exists(db_path):
                        try:
                            os.remove(db_path)
                            print(f"Reset sqlite DB file: {db_path}")
                        except Exception as _e:
                            print(
                                f"Warning: could not remove sqlite DB file: {db_path} -> {_e}"
                            )

                    # touch the file so sqlite can open it for connections
                    try:
                        open(db_path, "a").close()
                        print(f"Ensured sqlite DB exists at: {db_path}")
                    except Exception:
                        # best-effort: creation may fail due to permissions in CI
                        print(f"Warning: could not touch sqlite DB file: {db_path}")
    except Exception:
        # If URL parsing fails for any reason, continue and let alembic
        # raise the original, more informative error.
        pass

    try:
        command.upgrade(cfg, "head")
        print("Migrations finished: upgrade head")
        return 0
    except Exception as exc:  # pragma: no cover - runtime/CI path
        print("Migrations failed:", exc, file=sys.stderr)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
