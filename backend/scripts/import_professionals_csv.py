"""
Production-safe CSV import for professional leads.

Expected CSV headers (case-insensitive):
  full_name,email,phone,profession,city,organization,source,source_url

Usage (PowerShell):
  python backend/scripts/import_professionals_csv.py --file ./data/professionals.csv --dry-run
  python backend/scripts/import_professionals_csv.py --file ./data/professionals.csv --commit --confirm-canonical-db
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

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


REQUIRED_COLUMNS = {"email", "profession", "city"}


def _norm(value: str | None) -> str:
    return (value or "").strip()


def _norm_email(value: str | None) -> str:
    return _norm(value).lower()


def _read_csv_rows(file_path: Path) -> list[dict[str, str]]:
    with file_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row.")

        # Normalize headers to lower/trim so input is forgiving.
        normalized = [(_norm(name).lower()) for name in reader.fieldnames]
        reader.fieldnames = normalized

        missing = [c for c in REQUIRED_COLUMNS if c not in normalized]
        if missing:
            raise ValueError(f"CSV missing required columns: {', '.join(sorted(missing))}")

        rows: list[dict[str, str]] = []
        for row in reader:
            rows.append({(_norm(k).lower()): _norm(v) for k, v in row.items() if k})
        return rows


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import professional leads from CSV.")
    parser.add_argument("--file", required=True, help="Path to CSV file.")
    parser.add_argument("--commit", action="store_true", help="Apply DB writes.")
    parser.add_argument("--dry-run", action="store_true", help="Preview only.")
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

    file_path = Path(args.file)
    if not file_path.exists() or not file_path.is_file():
        print(f"ERROR: CSV file not found: {file_path}")
        return 2

    try:
        csv_rows = _read_csv_rows(file_path)
    except Exception as exc:
        print(f"ERROR: failed to parse CSV: {exc}")
        return 2

    batch_id = datetime.now(UTC).strftime("csv_%Y%m%dT%H%M%SZ")
    created = 0
    skipped_duplicates = 0
    skipped_invalid = 0

    with app.app_context():
        runtime_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
        print_app_db_preflight(runtime_uri)
        if not is_canonical_db_uri(runtime_uri):
            print(canonical_mismatch_error(runtime_uri))
            return 3
        if (not dry_run) and (not args.confirm_canonical_db):
            print(canonical_confirmation_error())
            return 3

        inspector = inspect(db.engine)
        table_names = set(inspector.get_table_names())
        if "professional_leads" not in table_names:
            print("ERROR: professional_leads table is missing.")
            return 4

        columns = {
            c["name"] for c in inspector.get_columns("professional_leads") if c.get("name")
        }
        has_source_url = "source_url" in columns
        has_import_batch = "import_batch" in columns
        has_lat = "latitude" in columns
        has_lng = "longitude" in columns

        seen_in_file: set[str] = set()

        for idx, row in enumerate(csv_rows, start=2):  # header is line 1
            email = _norm_email(row.get("email"))
            profession = _norm(row.get("profession"))
            city = _norm(row.get("city"))
            if not email or not profession or not city:
                print(f"SKIP invalid row {idx}: requires email/profession/city")
                skipped_invalid += 1
                continue

            if email in seen_in_file:
                print(f"SKIP duplicate in CSV row {idx}: {email}")
                skipped_duplicates += 1
                continue
            seen_in_file.add(email)

            existing = (
                ProfessionalLead.query.filter(func.lower(ProfessionalLead.email) == email)
                .order_by(ProfessionalLead.id.desc())
                .first()
            )
            if existing:
                print(f"SKIP duplicate in DB row {idx}: {email}")
                skipped_duplicates += 1
                continue

            lat = None
            lng = None
            if has_lat and has_lng:
                lat, lng = geocode_location_best_effort(city=city)

            source = _norm(row.get("source")) or "csv_import"
            source_url = _norm(row.get("source_url"))

            if dry_run:
                print(f"DRY-RUN create row {idx}: {email} ({profession} / {city})")
                created += 1
                continue

            lead = ProfessionalLead(
                email=email,
                full_name=_norm(row.get("full_name")) or None,
                phone=_norm(row.get("phone")) or None,
                city=city,
                profession=profession,
                organization=_norm(row.get("organization")) or None,
                source=source,
                status="imported",
                notes="Imported from CSV",
                created_at=datetime.now(UTC),
            )
            db.session.add(lead)
            db.session.flush()

            extra_updates: dict[str, object] = {}
            if has_source_url and source_url:
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
    print(
        f"[{mode}] batch={batch_id} file={file_path} created={created} "
        f"skipped_duplicates={skipped_duplicates} skipped_invalid={skipped_invalid}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
