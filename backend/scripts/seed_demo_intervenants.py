from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.helpchain_backend.src.app import create_app
from backend.extensions import db
from backend.models import Intervenant, Structure, utc_now


def _pick_structure() -> Structure | None:
    structure = (
        Structure.query.filter(Structure.slug.isnot(None))
        .filter(Structure.slug != "default")
        .order_by(Structure.id.asc())
        .first()
    )
    if structure is None:
        structure = Structure.query.order_by(Structure.id.asc()).first()
    return structure


def _intervenant_exists(structure_id: int, name: str, email: str | None) -> bool:
    query = Intervenant.query.filter(Intervenant.structure_id == structure_id)
    query = query.filter(Intervenant.name == name)
    if email:
        query = query.filter(Intervenant.email == email)
    else:
        query = query.filter(Intervenant.email.is_(None))
    return query.first() is not None


def seed_demo_intervenants() -> None:
    structure = _pick_structure()
    if structure is None:
        print("No structures found. Seed skipped.")
        return

    demo_rows = [
        {
            "name": "Claire Bernard",
            "actor_type": "volunteer",
            "email": "claire.bernard@example.org",
            "phone": "+33 6 12 34 56 01",
            "location": "Lyon",
            "is_active": True,
        },
        {
            "name": "Dr. Julien Martin",
            "actor_type": "professional",
            "email": "julien.martin@example.org",
            "phone": "+33 6 12 34 56 02",
            "location": "Paris",
            "is_active": True,
        },
        {
            "name": "Association Soleil",
            "actor_type": "association",
            "email": "contact@soleil-assoc.fr",
            "phone": "+33 6 12 34 56 03",
            "location": "Marseille",
            "is_active": True,
        },
        {
            "name": "Service Municipal Solidarité",
            "actor_type": "municipal_service",
            "email": "solidarite@ville.fr",
            "phone": "+33 6 12 34 56 04",
            "location": "Toulouse",
            "is_active": True,
        },
        {
            "name": "Amélie Dupont",
            "actor_type": "social_worker",
            "email": "amelie.dupont@example.org",
            "phone": "+33 6 12 34 56 05",
            "location": "Bordeaux",
            "is_active": True,
        },
        {
            "name": "Collectif Rive Gauche",
            "actor_type": "association",
            "email": "contact@rive-gauche.org",
            "phone": "+33 6 12 34 56 06",
            "location": "Nantes",
            "is_active": False,
        },
        {
            "name": "Marc Petit",
            "actor_type": "volunteer",
            "email": "marc.petit@example.org",
            "phone": "+33 6 12 34 56 07",
            "location": "Lille",
            "is_active": True,
        },
        {
            "name": "Centre Médico-Social",
            "actor_type": "professional",
            "email": "cms@example.org",
            "phone": "+33 6 12 34 56 08",
            "location": "Grenoble",
            "is_active": True,
        },
    ]

    created = 0
    skipped = 0

    now = utc_now()
    for idx, row in enumerate(demo_rows):
        if _intervenant_exists(structure.id, row["name"], row.get("email")):
            skipped += 1
            continue

        intervenant = Intervenant(
            structure_id=structure.id,
            name=row["name"],
            actor_type=row["actor_type"],
            email=row.get("email"),
            phone=row.get("phone"),
            location=row.get("location"),
            is_active=row.get("is_active", True),
            created_at=now - timedelta(days=(idx + 1)),
        )
        db.session.add(intervenant)
        created += 1

    if created:
        db.session.commit()

    total_checked = len(demo_rows)
    print(f"Intervenants checked: {total_checked}")
    print(f"Intervenants created: {created}")
    print(f"Duplicates skipped: {skipped}")
    print(f"Structure used: {structure.id} ({structure.name})")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed_demo_intervenants()
