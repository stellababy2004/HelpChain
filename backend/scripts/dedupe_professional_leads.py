"""
Production-safe dedupe utility for professional_leads.

Detects duplicates by:
- normalized email
- normalized phone
- normalized full_name + city + profession

Usage (PowerShell):
  python backend/scripts/dedupe_professional_leads.py --dry-run
  python backend/scripts/dedupe_professional_leads.py --commit --confirm-canonical-db
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import UTC, datetime

from sqlalchemy import inspect, text

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
from backend.local_db_guard import (
    canonical_confirmation_error,
    canonical_mismatch_error,
    is_canonical_db_uri,
    print_app_db_preflight,
)


def _norm(value: str | None) -> str:
    return (value or "").strip()


def _norm_lower(value: str | None) -> str:
    return _norm(value).lower()


def _norm_spaces_lower(value: str | None) -> str:
    return re.sub(r"\s+", " ", _norm(value)).strip().lower()


def _norm_phone(value: str | None) -> str:
    raw = _norm(value)
    if not raw:
        return ""
    return re.sub(r"\D+", "", raw)


def _build_dedupe_keys(lead: ProfessionalLead) -> list[tuple[str, str]]:
    keys: list[tuple[str, str]] = []
    email_key = _norm_lower(getattr(lead, "email", None))
    phone_key = _norm_phone(getattr(lead, "phone", None))
    name_key = _norm_spaces_lower(getattr(lead, "full_name", None))
    city_key = _norm_spaces_lower(getattr(lead, "city", None))
    prof_key = _norm_spaces_lower(getattr(lead, "profession", None))

    if email_key:
        keys.append(("email", email_key))
    if phone_key:
        keys.append(("phone", phone_key))
    if name_key and city_key and prof_key:
        keys.append(("identity", f"{name_key}|{city_key}|{prof_key}"))
    return keys


def _already_marked(notes: str | None, duplicate_of_id: int) -> bool:
    txt = _norm(notes)
    if not txt:
        return False
    marker = f"[AUTO_DEDUPE duplicate_of={duplicate_of_id}]"
    return marker in txt


def _append_note(notes: str | None, note_to_add: str) -> str:
    base = _norm(notes)
    if not base:
        return note_to_add
    if note_to_add in base:
        return base
    return f"{base} | {note_to_add}"


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dedupe professional leads safely.")
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

    scanned = 0
    duplicates_found = 0
    duplicates_marked = 0

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
        has_notes = "notes" in columns
        has_status = "status" in columns
        has_updated_at = "updated_at" in columns

        leads = (
            ProfessionalLead.query.order_by(
                ProfessionalLead.created_at.asc().nullslast(),
                ProfessionalLead.id.asc(),
            ).all()
        )

        seen_by_key: dict[tuple[str, str], int] = {}
        duplicate_to_primary: dict[int, int] = {}
        duplicate_reason: dict[int, str] = {}

        for lead in leads:
            scanned += 1
            key_candidates = _build_dedupe_keys(lead)
            primary_id = None
            reason = None
            for key_type, key_value in key_candidates:
                hit = seen_by_key.get((key_type, key_value))
                if hit and hit != lead.id:
                    primary_id = hit
                    reason = key_type
                    break

            if primary_id:
                duplicate_to_primary[int(lead.id)] = int(primary_id)
                duplicate_reason[int(lead.id)] = str(reason or "unknown")
            else:
                for key_type, key_value in key_candidates:
                    seen_by_key.setdefault((key_type, key_value), int(lead.id))

        duplicates_found = len(duplicate_to_primary)

        for dup_id, primary_id in duplicate_to_primary.items():
            lead = next((x for x in leads if int(x.id) == int(dup_id)), None)
            if not lead:
                continue

            note_marker = (
                f"[AUTO_DEDUPE duplicate_of={primary_id}]"
                f"[key={duplicate_reason.get(dup_id, 'unknown')}]"
                f"[at={datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}]"
            )

            updated_fields: dict[str, object] = {}
            should_mark = False

            if has_notes:
                current_notes = getattr(lead, "notes", None)
                if not _already_marked(current_notes, primary_id):
                    new_notes = _append_note(current_notes, note_marker)
                    if hasattr(lead, "notes"):
                        setattr(lead, "notes", new_notes)
                    else:
                        updated_fields["notes"] = new_notes
                    should_mark = True

            if has_status:
                current_status = _norm_lower(getattr(lead, "status", None))
                if current_status in ("", "new", "imported"):
                    if hasattr(lead, "status"):
                        setattr(lead, "status", "rejected")
                    else:
                        updated_fields["status"] = "rejected"
                    should_mark = True

            if has_updated_at:
                updated_fields.setdefault("updated_at", datetime.now(UTC))

            if not should_mark:
                continue

            duplicates_marked += 1
            if dry_run:
                continue

            if updated_fields:
                set_clause = ", ".join(f"{col} = :{col}" for col in updated_fields.keys())
                params = dict(updated_fields)
                params["id"] = int(lead.id)
                db.session.execute(
                    text(f"UPDATE professional_leads SET {set_clause} WHERE id = :id"),
                    params,
                )

        if dry_run:
            db.session.rollback()
        else:
            db.session.commit()

    mode = "DRY-RUN" if dry_run else "COMMIT"
    print(
        f"[{mode}] scanned={scanned} duplicates_found={duplicates_found} "
        f"duplicates_marked={duplicates_marked}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
