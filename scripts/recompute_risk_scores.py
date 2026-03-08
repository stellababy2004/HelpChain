from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.local_db_guard import (
    APP_IMPORT_PATH,
    canonical_confirmation_error,
    canonical_mismatch_error,
    is_canonical_db_uri,
    print_app_db_preflight,
)
from backend.extensions import db
from backend.helpchain_backend.src.services.risk_engine import apply_request_risk
from backend.models import Request
from sqlalchemy import inspect


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute request risk scores on canonical local DB only"
    )
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
        configured_uri = app.config.get("SQLALCHEMY_DATABASE_URI")
        db_url = str(db.engine.url)
        requests_exists = inspect(db.engine).has_table("requests")

        print(f"APP: {APP_IMPORT_PATH}")
        print_app_db_preflight(configured_uri)
        print(f"Configured SQLALCHEMY_DATABASE_URI: {configured_uri}")
        print(f"Resolved engine URL: {db_url}")
        print(f"Table 'requests' exists: {requests_exists}")
        if not args.confirm_canonical_db:
            print(canonical_confirmation_error())
            return 2
        if not is_canonical_db_uri(configured_uri):
            print(canonical_mismatch_error(configured_uri))
            return 2

        if not requests_exists:
            print(
                "ERROR: table 'requests' is missing in the target DB. "
                "Run migrations against this same DB target first."
            )
            return 2

        requests = Request.query.all()
        total = 0

        for req in requests:
            apply_request_risk(req)
            total += 1

        db.session.commit()
        critical_count = Request.query.filter_by(risk_level="critical").count()
        attention_count = Request.query.filter_by(risk_level="attention").count()
        standard_count = Request.query.filter_by(risk_level="standard").count()

        print("Risk recompute completed.")
        print(f"DB: {db_url}")
        print(f"Processed requests: {total}")
        print(
            "Risk level totals: "
            f"critical={critical_count}, "
            f"attention={attention_count}, "
            f"standard={standard_count}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
