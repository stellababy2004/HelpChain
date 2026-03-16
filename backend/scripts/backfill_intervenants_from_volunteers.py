from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.helpchain_backend.src.app import create_app
from backend.extensions import db
from backend.models import Intervenant, Volunteer


def _intervenant_exists(volunteer_id: int, structure_id: int, name: str | None, email: str | None) -> bool:
    direct = Intervenant.query.filter(
        Intervenant.legacy_volunteer_id == volunteer_id
    ).first()
    if direct is not None:
        return True

    query = Intervenant.query.filter(Intervenant.structure_id == structure_id)
    if email:
        query = query.filter(Intervenant.email == email)
    else:
        query = query.filter(Intervenant.email.is_(None))
    if name:
        query = query.filter(Intervenant.name == name)
    else:
        query = query.filter(Intervenant.name.is_(None))
    return query.first() is not None


def backfill_intervenants_from_volunteers() -> None:
    volunteers = Volunteer.query.order_by(Volunteer.id.asc()).all()
    if not volunteers:
        print("Volunteers scanned: 0")
        print("Intervenants created: 0")
        print("Duplicates skipped: 0")
        return

    created = 0
    skipped = 0

    for v in volunteers:
        structure_id = getattr(v, "structure_id", None)
        if structure_id is None:
            skipped += 1
            continue

        name = (v.name or "").strip() or None
        email = (v.email or "").strip() or None

        if _intervenant_exists(v.id, structure_id, name, email):
            skipped += 1
            continue

        intervenant = Intervenant(
            structure_id=structure_id,
            name=name,
            legacy_volunteer_id=v.id,
            actor_type="volunteer",
            email=email,
            phone=(v.phone or "").strip() or None,
            location=(v.location or "").strip() or None,
            is_active=bool(v.is_active) if v.is_active is not None else True,
            created_at=getattr(v, "created_at", None),
        )
        if intervenant.created_at is None:
            from backend.models import utc_now

            intervenant.created_at = utc_now()
        db.session.add(intervenant)
        created += 1

    db.session.commit()

    print(f"Volunteers scanned: {len(volunteers)}")
    print(f"Intervenants created: {created}")
    print(f"Duplicates skipped: {skipped}")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        backfill_intervenants_from_volunteers()
