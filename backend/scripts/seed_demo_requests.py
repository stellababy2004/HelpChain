from __future__ import annotations

import random
from datetime import datetime, timedelta

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.helpchain_backend.src.app import create_app
from backend.extensions import db
from backend.models import SocialRequest, Structure, User


def _ensure_structure() -> Structure:
    structure = Structure.query.order_by(Structure.id.asc()).first()
    if not structure:
        structure = Structure(name="Default", slug="default")
        db.session.add(structure)
        db.session.commit()
    return structure


def _ensure_user() -> User:
    user = User.query.order_by(User.id.asc()).first()
    if not user:
        user = User(
            username="demo_user",
            email="demo_user@helpchain.local",
            password_hash="x",
            role="requester",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
    return user


def create_request(
    *,
    structure_id: int,
    city: str,
    category: str,
    status: str,
    created_offset_hours: int,
    updated_offset_hours: int | None,
    assigned: int | None,
) -> None:
    created_at = datetime.utcnow() - timedelta(hours=created_offset_hours)
    updated_at = None
    if updated_offset_hours is not None:
        updated_at = datetime.utcnow() - timedelta(hours=updated_offset_hours)

    r = SocialRequest(
        structure_id=structure_id,
        need_type=category,
        urgency=random.choice(["low", "medium", "high"]),
        person_ref=f"city:{city}",
        description=f"Demo request for system testing ({city})",
        status=status,
        assigned_to_user_id=assigned,
        created_at=created_at,
        updated_at=updated_at or created_at,
    )
    db.session.add(r)


def seed() -> None:
    random.seed(42)
    structure = _ensure_structure()
    user = _ensure_user()

    cities = ["Paris", "Boulogne-Billancourt"]
    categories = [
        "food_assistance",
        "housing",
        "medical",
        "administrative",
        "psychological",
    ]

    # Scenario A — new requests (5)
    for _ in range(5):
        create_request(
            structure_id=structure.id,
            city=random.choice(cities),
            category=random.choice(categories),
            status="new",
            created_offset_hours=random.randint(1, 24),
            updated_offset_hours=random.randint(1, 24),
            assigned=None,
        )

    # Scenario B — active requests (5)
    for _ in range(5):
        create_request(
            structure_id=structure.id,
            city=random.choice(cities),
            category=random.choice(categories),
            status="in_progress",
            created_offset_hours=random.randint(1, 48),
            updated_offset_hours=random.randint(1, 24),
            assigned=user.id if random.random() > 0.5 else None,
        )

    # Scenario C — overdue requests (5) older than 3 days
    for _ in range(5):
        create_request(
            structure_id=structure.id,
            city=random.choice(cities),
            category=random.choice(categories),
            status="in_progress",
            created_offset_hours=random.randint(73, 120),
            updated_offset_hours=random.randint(24, 72),
            assigned=user.id if random.random() > 0.5 else None,
        )

    # Scenario D — stale requests (5) updated > 48h ago
    for _ in range(5):
        create_request(
            structure_id=structure.id,
            city=random.choice(cities),
            category=random.choice(categories),
            status=random.choice(["new", "in_progress"]),
            created_offset_hours=random.randint(24, 96),
            updated_offset_hours=random.randint(49, 96),
            assigned=None,
        )

    # Scenario E — resolved today (5)
    for _ in range(5):
        create_request(
            structure_id=structure.id,
            city=random.choice(cities),
            category=random.choice(categories),
            status="resolved",
            created_offset_hours=random.randint(24, 48),
            updated_offset_hours=random.randint(1, 4),
            assigned=user.id if random.random() > 0.5 else None,
        )

    db.session.commit()


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed()
        print("Demo requests created.")
