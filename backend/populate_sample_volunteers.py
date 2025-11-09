#!/usr/bin/env python3
"""Seed the local database with realistic volunteer profiles."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta

# Ensure the backend package is importable whether the script is run directly or via -m
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CURRENT_DIR)
sys.path.insert(0, os.path.dirname(CURRENT_DIR))

# Delay heavy imports until paths are configured
from appy import app  # noqa: E402
from backend.extensions import db  # noqa: E402
from backend.models import Volunteer  # noqa: E402

SAMPLE_IDENTIFIER = "[SAMPLE]"
SAMPLE_VOLUNTEERS: list[dict[str, object]] = [
    {
        "name": f"{SAMPLE_IDENTIFIER} Ivanka Petrova",
        "email": "ivanka.petrova.sample@helpchain.bg",
        "phone": "+359 888 111 222",
        "skills": "Социална подкрепа, посещения при възрастни, доставка на лекарства",
        "location": "Sofia, Bulgaria",
        "latitude": 42.6977,
        "longitude": 23.3219,
        "points": 1250,
        "level": 4,
        "experience": 430,
        "total_tasks_completed": 32,
        "total_hours_volunteered": 96.5,
        "rating": 4.8,
        "rating_count": 24,
        "streak_days": 5,
        "rank": 1,
        "achievements": ["community_champion", "rapid_responder"],
        "badges": ["sofia_hub", "top_reviewer"],
        "last_activity": datetime.now(UTC) - timedelta(hours=6),
    },
    {
        "name": f"{SAMPLE_IDENTIFIER} Georgi Mihaylov",
        "email": "georgi.mihaylov.sample@helpchain.bg",
        "phone": "+359 887 222 333",
        "skills": "Логистика, транспорт, техническа помощ",
        "location": "Plovdiv, Bulgaria",
        "latitude": 42.1354,
        "longitude": 24.7453,
        "points": 980,
        "level": 3,
        "experience": 275,
        "total_tasks_completed": 21,
        "total_hours_volunteered": 68.0,
        "rating": 4.6,
        "rating_count": 18,
        "streak_days": 3,
        "rank": 3,
        "achievements": ["logistics_master"],
        "badges": ["plovdiv_pioneer"],
        "last_activity": datetime.now(UTC) - timedelta(days=1, hours=2),
    },
    {
        "name": f"{SAMPLE_IDENTIFIER} Desislava Koleva",
        "email": "desislava.koleva.sample@helpchain.bg",
        "phone": "+359 884 333 444",
        "skills": "Психологическа подкрепа, обучение на доброволци",
        "location": "Varna, Bulgaria",
        "latitude": 43.2141,
        "longitude": 27.9147,
        "points": 860,
        "level": 3,
        "experience": 240,
        "total_tasks_completed": 19,
        "total_hours_volunteered": 55.0,
        "rating": 4.9,
        "rating_count": 30,
        "streak_days": 7,
        "rank": 2,
        "achievements": ["mentor", "wellness_support"],
        "badges": ["varna_wave", "five_star"],
        "last_activity": datetime.now(UTC) - timedelta(hours=12),
    },
    {
        "name": f"{SAMPLE_IDENTIFIER} Nikolay Stanchev",
        "email": "nikolay.stanchev.sample@helpchain.bg",
        "phone": "+359 885 444 555",
        "skills": "Инженерна помощ, ремонт на домове, ИТ поддръжка",
        "location": "Burgas, Bulgaria",
        "latitude": 42.5048,
        "longitude": 27.4626,
        "points": 640,
        "level": 2,
        "experience": 160,
        "total_tasks_completed": 14,
        "total_hours_volunteered": 43.0,
        "rating": 4.4,
        "rating_count": 11,
        "streak_days": 2,
        "rank": 5,
        "achievements": ["tech_savior"],
        "badges": ["burgas_builder"],
        "last_activity": datetime.now(UTC) - timedelta(days=2, hours=4),
    },
    {
        "name": f"{SAMPLE_IDENTIFIER} Maria Hristova",
        "email": "maria.hristova.sample@helpchain.bg",
        "phone": "+359 886 777 888",
        "skills": "Организиране на събития, дарителски кампании, комуникация",
        "location": "Ruse, Bulgaria",
        "latitude": 43.8356,
        "longitude": 25.9657,
        "points": 520,
        "level": 2,
        "experience": 140,
        "total_tasks_completed": 11,
        "total_hours_volunteered": 37.5,
        "rating": 4.2,
        "rating_count": 9,
        "streak_days": 1,
        "rank": 6,
        "achievements": ["event_coordinator"],
        "badges": ["danube_connector"],
        "last_activity": datetime.now(UTC) - timedelta(days=3, hours=6),
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete existing sample volunteers before seeding.",
    )
    parser.add_argument(
        "--force-update",
        action="store_true",
        help="Overwrite fields on existing sample volunteers.",
    )
    return parser.parse_args()


def _delete_existing_samples() -> int:
    emails = [entry["email"] for entry in SAMPLE_VOLUNTEERS]
    deleted = Volunteer.query.filter(Volunteer.email.in_(emails)).delete(
        synchronize_session=False
    )
    db.session.commit()
    return deleted


def seed_volunteers(force_update: bool) -> tuple[int, int]:
    created = 0
    updated = 0

    for payload in SAMPLE_VOLUNTEERS:
        volunteer = Volunteer.query.filter_by(email=payload["email"]).first()

        if volunteer is None:
            volunteer = Volunteer(**payload)
            db.session.add(volunteer)
            created += 1
            continue

        if not force_update:
            continue

        for field, value in payload.items():
            setattr(volunteer, field, value)
        volunteer.updated_at = datetime.now(UTC)
        updated += 1

    db.session.commit()
    return created, updated


def main() -> None:
    args = parse_args()

    with app.app_context():
        if args.replace:
            deleted = _delete_existing_samples()
            print(f"🧹 Removed {deleted} existing sample volunteers.")

        created, updated = seed_volunteers(force_update=args.force_update)

        if created:
            print(f"✅ Created {created} sample volunteer profile(s).")
        if updated:
            print(f"🔁 Updated {updated} existing sample volunteer profile(s).")
        if created == 0 and updated == 0:
            print("ℹ️ Nothing to do — sample volunteers already match the seed data.")


if __name__ == "__main__":
    main()
