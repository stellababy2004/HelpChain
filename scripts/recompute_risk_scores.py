from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.extensions import db
from backend.helpchain_backend.src.services.risk_engine import apply_request_risk
from backend.models import Request
from sqlalchemy import inspect


def main() -> int:
    # Use the exact same entrypoint as Flask CLI: backend.appy:app
    from backend.appy import app

    with app.app_context():
        configured_uri = app.config.get("SQLALCHEMY_DATABASE_URI")
        db_url = str(db.engine.url)
        requests_exists = inspect(db.engine).has_table("requests")

        print(f"Configured SQLALCHEMY_DATABASE_URI: {configured_uri}")
        print(f"Resolved engine URL: {db_url}")
        print(f"Table 'requests' exists: {requests_exists}")

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
