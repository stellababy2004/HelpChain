"""
Quick status normalization script (manual-only write, canonical DB guard enforced).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.local_db_guard import (
    APP_IMPORT_PATH,
    canonical_confirmation_error,
    canonical_mismatch_error,
    is_canonical_db_uri,
    print_app_db_preflight,
)

# Adjust table/column names if different
TABLE = "request"
STATUS_COL = "status"

# SQL variants
SQL_UPDATES = [
    f"UPDATE {TABLE} SET {STATUS_COL}='pending' WHERE {STATUS_COL} IN ('Inconnu','En attente')",
    f"UPDATE {TABLE} SET {STATUS_COL}='in_progress' WHERE {STATUS_COL} IN ('En cours')",
    f"UPDATE {TABLE} SET {STATUS_COL}='in_progress' WHERE LOWER({STATUS_COL}) IN ('in progress')",
    f"UPDATE {TABLE} SET {STATUS_COL}='pending' WHERE LOWER({STATUS_COL}) IN ('pending')",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize legacy status values")
    parser.add_argument(
        "--confirm-canonical-db",
        action="store_true",
        help="Required safety flag to allow DB write",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    from backend.appy import app

    with app.app_context():
        runtime_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
        print(f"APP: {APP_IMPORT_PATH}")
        print_app_db_preflight(runtime_uri)
        if not args.confirm_canonical_db:
            print(canonical_confirmation_error())
            return 2
        if not is_canonical_db_uri(runtime_uri):
            print(canonical_mismatch_error(runtime_uri))
            return 2

    engine = create_engine(runtime_uri, future=True)
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            for sql in SQL_UPDATES:
                res = conn.execute(text(sql))
                print(f"Executed: {sql} -- affected: {res.rowcount}")
            trans.commit()
            print("Status normalization completed.")
            return 0
        except Exception as exc:
            trans.rollback()
            print("Error, transaction rolled back:", exc)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
