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


def seed_requests(total: int = 20) -> None:
    structure = Structure.query.order_by(Structure.id.asc()).first()
    if not structure:
        structure = Structure(name="Default", slug="default")
        db.session.add(structure)
        db.session.commit()

    user = User.query.order_by(User.id.asc()).first()
    if not user:
        user = User(
            username="seed_user",
            email="seed_user@helpchain.local",
            password_hash="x",
            role="requester",
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()

    cities = ["Paris", "Boulogne-Billancourt"]
    need_types = [
        "food_assistance",
        "housing",
        "medical_help",
        "administrative_help",
        "psychological_support",
    ]
    statuses = ["new", "in_progress", "resolved"]
    urgencies = ["low", "medium", "high"]

    random.seed(42)
    for i in range(total):
        created_at = datetime.utcnow() - timedelta(hours=random.randint(1, 72))
        updated_at = created_at + timedelta(hours=random.randint(1, 24))
        city = random.choice(cities)
        status = random.choice(statuses)
        assigned_to_user_id = user.id if status == "in_progress" and random.random() > 0.3 else None

        r = SocialRequest(
            structure_id=structure.id,
            need_type=random.choice(need_types),
            urgency=random.choice(urgencies),
            person_ref=f"city:{city}",
            description=f"Test request generated for development ({city})",
            status=status,
            assigned_to_user_id=assigned_to_user_id,
            created_at=created_at,
            updated_at=updated_at,
        )
        db.session.add(r)

    db.session.commit()


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed_requests()
        print("Test requests created.")
