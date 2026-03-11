"""Backfill missing Request latitude/longitude with best-effort geocoding.

Safe + idempotent:
- touches only rows where latitude is NULL or longitude is NULL
- keeps row unchanged when geocoding fails
- continues on per-row errors
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from sqlalchemy import or_

# Allow running from repository root via:
#   python backend/scripts/backfill_request_coordinates.py
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.appy import app
from backend.extensions import db
from backend.models import Request
from backend.helpchain_backend.src.services.geocoding import geocode_location_best_effort


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill missing Request coordinates (best-effort, non-blocking)."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max rows to scan (0 = all).",
    )
    parser.add_argument(
        "--sleep-ms",
        type=int,
        default=120,
        help="Delay between geocode calls to avoid hammering upstream.",
    )
    args = parser.parse_args()

    scanned = 0
    updated = 0
    skipped = 0
    failed = 0

    with app.app_context():
        q = (
            db.session.query(Request)
            .filter(or_(Request.latitude.is_(None), Request.longitude.is_(None)))
            .order_by(Request.id.asc())
        )
        if args.limit and args.limit > 0:
            q = q.limit(args.limit)

        rows = q.all()
        for req in rows:
            scanned += 1
            try:
                lat, lng = geocode_location_best_effort(
                    location_text=getattr(req, "location_text", None),
                    city=getattr(req, "city", None),
                )
                if lat is None or lng is None:
                    skipped += 1
                    continue

                req.latitude = float(lat)
                req.longitude = float(lng)
                db.session.commit()
                updated += 1
            except Exception:
                db.session.rollback()
                failed += 1
            finally:
                if args.sleep_ms > 0:
                    time.sleep(args.sleep_ms / 1000.0)

    print("BACKFILL_REQUEST_COORDINATES SUMMARY")
    print(f"scanned={scanned}")
    print(f"updated={updated}")
    print(f"skipped={skipped}")
    print(f"failed={failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

