from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta

_this_dir = os.path.abspath(os.path.dirname(__file__))
_repo_root = os.path.abspath(os.path.join(_this_dir, os.pardir, os.pardir))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from backend.appy import app
from backend.extensions import db
from backend.models import Request, Structure


ROWS = [
    {
        "title": "Aide alimentaire urgente pour une personne isolée",
        "description": "Demande d’orientation vers une aide alimentaire temporaire. Situation signalée comme urgente par un proche.",
        "name": "Demandeur Paris 01",
        "email": "requester.paris01@helpchain.local",
        "phone": "+33 6 10 00 00 01",
        "city": "Paris",
        "postcode": "75011",
        "category": "aide_alimentaire",
        "priority": "urgent",
        "status": "open",
        "structure_slug": "paris",
        "risk_score": 72,
        "risk_level": "high",
    },
    {
        "title": "Accompagnement administratif CAF / dossier social",
        "description": "Besoin d’aide pour comprendre un courrier administratif et préparer les pièces justificatives.",
        "name": "Demandeur Boulogne 01",
        "email": "requester.boulogne01@helpchain.local",
        "phone": "+33 6 10 00 00 02",
        "city": "Boulogne-Billancourt",
        "postcode": "92100",
        "category": "administratif",
        "priority": "normal",
        "status": "open",
        "structure_slug": "boulogne-billancourt",
        "risk_score": 38,
        "risk_level": "medium",
    },
    {
        "title": "Visite de lien social — personne âgée isolée",
        "description": "Personne âgée vivant seule, besoin d’un passage ou d’une orientation vers une structure locale.",
        "name": "Demandeur Neuilly 01",
        "email": "requester.neuilly01@helpchain.local",
        "phone": "+33 6 10 00 00 03",
        "city": "Neuilly-sur-Seine",
        "postcode": "92200",
        "category": "isolement",
        "priority": "high",
        "status": "open",
        "structure_slug": "neuilly-sur-seine",
        "risk_score": 64,
        "risk_level": "high",
    },
    {
        "title": "Orientation psychologique après rupture familiale",
        "description": "Demande d’orientation vers un soutien psychologique ou une association partenaire.",
        "name": "Demandeur Paris 02",
        "email": "requester.paris02@helpchain.local",
        "phone": "+33 6 10 00 00 04",
        "city": "Paris",
        "postcode": "75018",
        "category": "soutien_psychologique",
        "priority": "high",
        "status": "in_progress",
        "structure_slug": "paris",
        "risk_score": 58,
        "risk_level": "medium",
    },
    {
        "title": "Aide transport pour rendez-vous médical",
        "description": "Besoin d’un accompagnement ponctuel pour un rendez-vous médical prévu cette semaine.",
        "name": "Demandeur Boulogne 02",
        "email": "requester.boulogne02@helpchain.local",
        "phone": "+33 6 10 00 00 05",
        "city": "Boulogne-Billancourt",
        "postcode": "92100",
        "category": "transport_medical",
        "priority": "normal",
        "status": "open",
        "structure_slug": "boulogne-billancourt",
        "risk_score": 24,
        "risk_level": "low",
    },
]


def main() -> int:
    with app.app_context():
        created = 0
        skipped = 0

        for i, row in enumerate(ROWS):
            existing = Request.query.filter_by(email=row["email"]).first()
            if existing:
                print(f"SKIP duplicate: {row['email']}")
                skipped += 1
                continue

            structure = Structure.query.filter_by(slug=row["structure_slug"]).first()
            if not structure:
                print(f"SKIP missing structure: {row['structure_slug']}")
                skipped += 1
                continue

            now = datetime.now(UTC) - timedelta(days=i)

            req = Request(
                title=row["title"],
                description=row["description"],
                message=row["description"],
                name=row["name"],
                email=row["email"],
                phone=row["phone"],
                city=row["city"],
                region="Île-de-France",
                location_text=f"{row['city']}, Île-de-France",
                postcode=row["postcode"],
                country="France",
                status=row["status"],
                priority=row["priority"],
                category=row["category"],
                source_channel="local_demo_seed",
                structure_id=structure.id,
                created_at=now,
                updated_at=now,
                is_archived=False,
                risk_score=row["risk_score"],
                risk_level=row["risk_level"],
                risk_signals="local_demo_seed",
                risk_last_updated=now,
            )

            db.session.add(req)
            created += 1
            print(f"CREATE request: {row['title']} -> {row['city']}")

        db.session.commit()
        print(f"DONE created={created} skipped={skipped}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())