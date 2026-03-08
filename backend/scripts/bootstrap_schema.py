"""Best-effort runtime schema bootstrap for environments with migration drift.

Creates missing tables from SQLAlchemy metadata. Does not alter existing tables.
"""

from __future__ import annotations

import os
import sys
import argparse

from sqlalchemy import inspect

# Allow running as "python backend/scripts/bootstrap_schema.py" on Render.
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.appy import app
from backend.extensions import db
from backend.local_db_guard import (
    canonical_confirmation_error,
    canonical_mismatch_error,
    is_canonical_db_uri,
    print_app_db_preflight,
)

# Ensure model metadata is loaded before create_all().
import backend.models  # noqa: F401
import backend.helpchain_backend.src.models  # noqa: F401


def main() -> int:
    parser = argparse.ArgumentParser(description="Best-effort schema bootstrap (manual-only)")
    parser.add_argument(
        "--confirm-canonical-db",
        action="store_true",
        help="Required safety flag to allow schema write",
    )
    args = parser.parse_args()

    with app.app_context():
        runtime_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
        print_app_db_preflight(runtime_uri)
        if not args.confirm_canonical_db:
            print(canonical_confirmation_error())
            return 2
        if not is_canonical_db_uri(runtime_uri):
            print(canonical_mismatch_error(runtime_uri))
            return 2

        engine = db.engine
        insp = inspect(engine)
        before = set(insp.get_table_names())
        db.create_all()
        after = set(inspect(engine).get_table_names())
        created = sorted(after - before)
        if created:
            print(f"SCHEMA_BOOTSTRAP: created tables: {', '.join(created)}")
        else:
            print("SCHEMA_BOOTSTRAP: no missing tables")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
