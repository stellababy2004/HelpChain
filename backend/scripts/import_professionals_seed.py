"""
Seed import script for professional leads (v1 discovery pipeline).

Creates sample Paris professionals with:
- status=imported
- source=seed_import
- source_url (if supported by DB schema)
- import_batch (if supported by DB schema)

Usage (PowerShell):
  python backend/scripts/import_professionals_seed.py --dry-run
  python backend/scripts/import_professionals_seed.py --commit --confirm-canonical-db
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime

from sqlalchemy import func, inspect, text

# Ensure repo root and backend package are importable when executed directly.
_this_dir = os.path.abspath(os.path.dirname(__file__))
_repo_root = os.path.abspath(os.path.join(_this_dir, os.pardir, os.pardir))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
_backend_dir = os.path.abspath(os.path.join(_repo_root, "backend"))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from backend.appy import app
from backend.extensions import db
from backend.helpchain_backend.src.models import ProfessionalLead
from backend.helpchain_backend.src.services.geocoding import geocode_location_best_effort
from backend.local_db_guard import (
    canonical_confirmation_error,
    canonical_mismatch_error,
    is_canonical_db_uri,
    print_app_db_preflight,
)


SEED_ROWS = [
    {
        "full_name": "Dr Claire Martin",
        "profession": "Psychologue",
        "city": "Paris",
        "email": "claire.martin.seed@helpchain.local",
        "phone": "+33 6 11 22 33 44",
        "organization": "Cabinet Paris Centre",
    },
    {
        "full_name": "Me Julien Bernard",
        "profession": "Avocat",
        "city": "Paris",
        "email": "julien.bernard.seed@helpchain.local",
        "phone": "+33 6 22 33 44 55",
        "organization": "Barreau de Paris",
    },
    {
        "full_name": "Sophie Laurent",
        "profession": "Assistant social",
        "city": "Paris",
        "email": "sophie.laurent.seed@helpchain.local",
        "phone": "+33 6 33 44 55 66",
        "organization": "Association Solidarite Paris",
    },
]


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed import professional leads.")
    parser.add_argument("--commit", action="store_true", help="Apply DB writes.")
    parser.add_argument("--dry-run", action="store_true", help="Print actions only.")
    parser.add_argument(
        "--confirm-canonical-db",
        action="store_true",
        help="Required safety flag when using --commit.",
    )
    args = parser.parse_args(argv)

    if args.commit and args.dry_run:
        print("WARNING: both --commit and --dry-run provided; using --commit.")
    dry_run = not args.commit
    if args.dry_run and not args.commit:
        dry_run = True

    batch_id = datetime.now(UTC).strftime("seed_%Y%m%dT%H%M%SZ")
    created = 0
    skipped = 0

    with app.app_context():
        runtime_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
        print_app_db_preflight(runtime_uri)
        if not is_canonical_db_uri(runtime_uri):
            print(canonical_mismatch_error(runtime_uri))
            return 2
        if (not dry_run) and (not args.confirm_canonical_db):
            print(canonical_confirmation_error())
            return 2

        inspector = inspect(db.engine)
        table_names = set(inspector.get_table_names())
        if "professional_leads" not in table_names:
            print("ERROR: professional_leads table is missing.")
            return 3

        columns = {
            c["name"] for c in inspector.get_columns("professional_leads") if c.get("name")
        }
        has_source_url = "source_url" in columns
        has_import_batch = "import_batch" in columns
        has_lat = "latitude" in columns
        has_lng = "longitude" in columns

        for row in SEED_ROWS:
            email = (row.get("email") or "").strip().lower()
            if not email:
                skipped += 1
                continue

            existing = (
                ProfessionalLead.query.filter(func.lower(ProfessionalLead.email) == email)
                .order_by(ProfessionalLead.id.desc())
                .first()
            )
            if existing:
                print(f"SKIP duplicate email: {email}")
                skipped += 1
                continue

            lat = None
            lng = None
            if has_lat and has_lng:
                lat, lng = geocode_location_best_effort(city=row.get("city"))

            if dry_run:
                print(f"DRY-RUN create: {email} ({row.get('profession')} / {row.get('city')})")
                created += 1
                continue

            lead = ProfessionalLead(
                email=email,
                full_name=row.get("full_name"),
                phone=row.get("phone"),
                city=row.get("city"),
                profession=row.get("profession") or "Professionnel",
                organization=row.get("organization"),
                source="seed_import",
                status="imported",
                notes="Imported by seed script",
                created_at=datetime.now(UTC),
            )
            db.session.add(lead)
            db.session.flush()

            extra_updates: dict[str, object] = {}
            if has_source_url:
                source_url = "https://example.org/professionals-directory"
                if hasattr(lead, "source_url"):
                    setattr(lead, "source_url", source_url)
                else:
                    extra_updates["source_url"] = source_url
            if has_import_batch:
                if hasattr(lead, "import_batch"):
                    setattr(lead, "import_batch", batch_id)
                else:
                    extra_updates["import_batch"] = batch_id
            if has_lat and has_lng and lat is not None and lng is not None:
                if hasattr(lead, "latitude") and hasattr(lead, "longitude"):
                    setattr(lead, "latitude", float(lat))
                    setattr(lead, "longitude", float(lng))
                else:
                    extra_updates["latitude"] = float(lat)
                    extra_updates["longitude"] = float(lng)

            if extra_updates:
                set_clause = ", ".join(f"{col} = :{col}" for col in extra_updates.keys())
                params = dict(extra_updates)
                params["id"] = int(lead.id)
                db.session.execute(
                    text(f"UPDATE professional_leads SET {set_clause} WHERE id = :id"),
                    params,
                )

            created += 1

        if dry_run:
            db.session.rollback()
        else:
            db.session.commit()

    mode = "DRY-RUN" if dry_run else "COMMIT"
    print(f"[{mode}] batch={batch_id} created={created} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
