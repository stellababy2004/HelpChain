"""
Production-safe scoring utility for professional_leads.

Score weights:
- has email: +20
- has phone: +20
- has organization: +15
- priority city: +25
- target profession: +20

Usage (PowerShell):
  python backend/scripts/score_professional_leads.py --dry-run
  python backend/scripts/score_professional_leads.py --priority-city Paris --target-profession Psychologue --commit --confirm-canonical-db
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


def _append_note(base_notes: str | None, note_to_add: str) -> str:
    base = _norm(base_notes)
    if not base:
        return note_to_add
    if note_to_add in base:
        return base
    return f"{base} | {note_to_add}"


def _derive_priority(score: int) -> str:
    if score >= 70:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"


def _score_lead(lead: ProfessionalLead, priority_city: str, target_profession: str) -> tuple[int, str]:
    score = 0

    if _norm(getattr(lead, "email", None)):
        score += 20
    if _norm(getattr(lead, "phone", None)):
        score += 20
    if _norm(getattr(lead, "organization", None)):
        score += 15

    city = _norm_spaces_lower(getattr(lead, "city", None))
    profession = _norm_spaces_lower(getattr(lead, "profession", None))
    if priority_city and city and priority_city in city:
        score += 25
    if target_profession and profession and target_profession in profession:
        score += 20

    return score, _derive_priority(score)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score professional leads safely.")
    parser.add_argument(
        "--priority-city",
        default="Paris",
        help="Priority city to boost (default: Paris).",
    )
    parser.add_argument(
        "--target-profession",
        default="",
        help="Profession keyword to boost (example: Psychologue).",
    )
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

    priority_city = _norm_spaces_lower(args.priority_city)
    target_profession = _norm_spaces_lower(args.target_profession)
    run_stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    scanned = 0
    scored = 0

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
        has_updated_at = "updated_at" in columns

        # Optional dedicated columns (degrade gracefully if absent).
        score_column = next(
            (c for c in ("lead_score", "score", "quality_score") if c in columns),
            None,
        )
        priority_column = next(
            (c for c in ("lead_priority", "priority", "quality_priority") if c in columns),
            None,
        )

        leads = ProfessionalLead.query.order_by(ProfessionalLead.id.asc()).all()
        for lead in leads:
            scanned += 1
            score, priority = _score_lead(lead, priority_city=priority_city, target_profession=target_profession)
            note = f"[AUTO_SCORE v1 score={score} priority={priority} at={run_stamp}]"

            updated_fields: dict[str, object] = {}
            changed = False

            if score_column:
                if hasattr(lead, score_column):
                    if getattr(lead, score_column, None) != score:
                        setattr(lead, score_column, score)
                        changed = True
                else:
                    updated_fields[score_column] = score
                    changed = True

            if priority_column:
                if hasattr(lead, priority_column):
                    if getattr(lead, priority_column, None) != priority:
                        setattr(lead, priority_column, priority)
                        changed = True
                else:
                    updated_fields[priority_column] = priority
                    changed = True

            if has_notes:
                current_notes = getattr(lead, "notes", None)
                new_notes = _append_note(current_notes, note)
                if new_notes != (current_notes or ""):
                    if hasattr(lead, "notes"):
                        setattr(lead, "notes", new_notes)
                    else:
                        updated_fields["notes"] = new_notes
                    changed = True

            if has_updated_at and changed:
                updated_fields["updated_at"] = datetime.now(UTC)

            if changed:
                scored += 1
                if not dry_run and updated_fields:
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
        f"[{mode}] scanned={scanned} scored={scored} "
        f"priority_city={args.priority_city} target_profession={args.target_profession or '-'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
