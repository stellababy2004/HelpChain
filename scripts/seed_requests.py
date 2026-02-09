# scripts/seed_requests.py
from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Ensure project root is on sys.path when running the script directly
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.extensions import db
from backend.helpchain_backend.src.app import create_app
from backend.models import Request


def main() -> int:
    force = "--force" in sys.argv

    app = create_app()
    with app.app_context():
        # покажи реалния DB файл (важно!)
        try:
            db_path = str(db.engine.url.database)
        except Exception:
            db_path = str(db.engine.url)

        print(f"[seed] Using DB: {db_path}")

        existing = Request.query.count()
        print(f"[seed] Existing requests: {existing}")

        if existing > 0 and not force:
            print(
                "[seed] Abort: DB already has requests. Re-run with --force if you still want to add 10 more."
            )
            return 0

        now = datetime.utcnow()

        statuses = ["new", "pending", "approved", "in_progress", "done", "rejected"]
        categories = [
            "general",
            "medical",
            "administrative",
            "legal",
            "social",
            "education",
        ]
        locations = [
            ("Paris", "Île-de-France"),
            ("Boulogne-Billancourt", "Île-de-France"),
            ("Sofia", "Sofia-city"),
            ("Plovdiv", "Plovdiv"),
            ("Varna", "Varna"),
            ("Burgas", "Burgas"),
            ("Lyon", "Auvergne-Rhône-Alpes"),
            ("Marseille", "Provence-Alpes-Côte d'Azur"),
        ]

        # цел: последните ~14 дни да има точки за timeseries
        items: list[Request] = []
        for i in range(10):
            city, region = random.choice(locations)
            status = random.choice(statuses)
            category = random.choice(categories)

            created_at = now - timedelta(
                days=random.randint(0, 13), hours=random.randint(0, 20)
            )
            updated_at = created_at + timedelta(hours=random.randint(0, 72))

            title = f"Помощ #{i + 1}: {category} — {city}"
            desc = f"Seed demo request ({category}) in {city}. Generated for dashboard charts."

            r = Request(
                title=title,
                description=desc,
                name=random.choice(
                    ["Stella", "Ivan", "Maria", "Georgi", "Elena", "Nikolay"]
                ),
                email="demo@example.com",
                phone="+359000000000",
                city=city,
                region=region,
                location_text=f"{city}, {region}",
                message=desc,
                status=status,
                priority=random.choice(["low", "medium", "high"]),
                category=category,
            )

            # ако моделът ти има тези колони, ги сетваме (ако няма — просто прескачаме)
            if hasattr(r, "created_at"):
                r.created_at = created_at
            if hasattr(r, "updated_at"):
                r.updated_at = updated_at

            # ако е done, сложи completed_at, за да има бизнес логика
            if status == "done" and hasattr(r, "completed_at"):
                r.completed_at = updated_at

            items.append(r)

        db.session.add_all(items)
        db.session.commit()

        print("[seed] Inserted 10 demo requests (ok)")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
