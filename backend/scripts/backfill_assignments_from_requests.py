from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.helpchain_backend.src.app import create_app
from backend.extensions import db
from backend.models import Assignment, Intervenant, Request


def _assignment_exists(request_id: int, intervenant_id: int) -> bool:
    return (
        Assignment.query.filter(
            Assignment.request_id == request_id,
            Assignment.intervenant_id == intervenant_id,
        )
        .first()
        is not None
    )


def backfill_assignments_from_requests(apply: bool) -> None:
    mode = "APPLY MODE" if apply else "DRY RUN"
    print(f"Mode: {mode}")
    requests = Request.query.filter(Request.assigned_volunteer_id.isnot(None)).all()
    if not requests:
        print("Requests scanned: 0")
        print("Assignments created: 0")
        print("Duplicates skipped: 0")
        print("Missing intervenant matches: 0")
        print("Rows skipped: 0")
        return

    created = 0
    duplicates = 0
    missing_intervenant = 0
    skipped = 0

    for req in requests:
        volunteer_id = getattr(req, "assigned_volunteer_id", None)
        if not volunteer_id:
            skipped += 1
            continue

        intervenant = Intervenant.query.filter(
            Intervenant.legacy_volunteer_id == int(volunteer_id)
        ).first()
        if not intervenant:
            missing_intervenant += 1
            continue

        if _assignment_exists(req.id, intervenant.id):
            duplicates += 1
            continue

        assigned_at = getattr(req, "owned_at", None) or getattr(req, "created_at", None)
        if apply:
            assignment = Assignment(
                request_id=req.id,
                intervenant_id=intervenant.id,
                structure_id=intervenant.structure_id,
                assigned_by_admin_id=getattr(req, "owner_id", None),
                assigned_at=assigned_at,
                status="active",
                notes="Backfilled from legacy volunteer assignment",
            )
            db.session.add(assignment)
        created += 1

    if apply:
        db.session.commit()

    print(f"Requests scanned: {len(requests)}")
    print(f"Assignments created: {created}")
    print(f"Duplicates skipped: {duplicates}")
    print(f"Missing intervenant matches: {missing_intervenant}")
    print(f"Rows skipped: {skipped}")


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    app = create_app()
    with app.app_context():
        backfill_assignments_from_requests(apply)
