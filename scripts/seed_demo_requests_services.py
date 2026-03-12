#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.appy import app
from backend.extensions import db
from backend.local_db_guard import (
    canonical_confirmation_error,
    canonical_mismatch_error,
    is_canonical_db_uri,
    print_app_db_preflight,
)
from backend.models import Request, Structure, StructureService, User

DEFAULT_TARGET_STRUCTURE_SLUG = "default"
MAX_EXISTING_REQUESTS_PER_TARGET = 50
TARGET_REQUEST_COUNT = 25
APP_IMPORT_PATH = "backend.appy:app"

STATUS_SEQUENCE = (
    ["new"] * 5
    + ["triage"] * 5
    + ["assigned"] * 5
    + ["in_progress"] * 5
    + ["done"] * 3
    + ["rejected"] * 2
)
CREATED_DELTAS_HOURS = [2, 8, 24, 48, 72, 120, 168]
SERVICE_DEFINITIONS = {
    "accueil_social": "Accueil social",
    "hebergement_logement": "Hebergement / Logement",
    "aide_alimentaire": "Aide alimentaire",
    "seniors_isolement": "Seniors / Isolement",
    "acces_aux_droits": "Acces aux droits",
    "protection_violences": "Protection / Violences",
}


@dataclass(frozen=True)
class DemoCase:
    title: str
    description: str
    service_code: str
    priority: str
    city: str
    name: str
    email: str
    phone: str
    category: str


DEMO_CASES: list[DemoCase] = [
    DemoCase(
        title="Famille avec deux enfants sans solution d'hebergement stable",
        description="La famille a perdu son logement temporaire et cherche une solution d'hebergement d'urgence.",
        service_code="hebergement_logement",
        priority="high",
        city="Boulogne-Billancourt",
        name="Nadia L.",
        email="nadia.l@example.org",
        phone="+33 6 10 22 31 41",
        category="logement",
    ),
    DemoCase(
        title="Personne agee isolee necessitant aide pour les courses",
        description="La situation signale un isolement durable avec difficultes de deplacement et absence de relais familial.",
        service_code="seniors_isolement",
        priority="medium",
        city="Boulogne-Billancourt",
        name="Paul M.",
        email="paul.m@example.org",
        phone="+33 6 11 23 32 42",
        category="isolement_personne_agee",
    ),
    DemoCase(
        title="Demande d'aide alimentaire suite a perte d'emploi",
        description="Le foyer ne dispose plus de ressources suffisantes pour couvrir les besoins alimentaires de la semaine.",
        service_code="aide_alimentaire",
        priority="medium",
        city="Boulogne-Billancourt",
        name="Sonia K.",
        email="sonia.k@example.org",
        phone="+33 6 12 24 33 43",
        category="aide_alimentaire",
    ),
    DemoCase(
        title="Signalement de violences intrafamiliales avec enfant mineur",
        description="Une evaluation immediate est requise pour proteger la personne et l'enfant concerne.",
        service_code="protection_violences",
        priority="critical",
        city="Boulogne-Billancourt",
        name="Signalement confidentiel",
        email="signalement1@example.org",
        phone="+33 6 13 25 34 44",
        category="violence_domestique",
    ),
    DemoCase(
        title="Demande d'accompagnement pour demarches administratives CAF",
        description="La personne sollicite un appui pour regulariser ses droits sociaux et finaliser son dossier CAF.",
        service_code="acces_aux_droits",
        priority="low",
        city="Boulogne-Billancourt",
        name="Claire T.",
        email="claire.t@example.org",
        phone="+33 6 14 26 35 45",
        category="accompagnement_administratif",
    ),
    DemoCase(
        title="Situation sociale generale sans referent identifie",
        description="Un premier accueil social est necessaire pour qualifier la situation et orienter vers le bon dispositif.",
        service_code="accueil_social",
        priority="medium",
        city="Boulogne-Billancourt",
        name="Karim A.",
        email="karim.a@example.org",
        phone="+33 6 15 27 36 46",
        category="orientation_sociale",
    ),
    DemoCase(
        title="Mere isolee en recherche de mise a l'abri",
        description="La demande concerne un besoin de mise a l'abri avec orientation rapide vers les solutions territoriales.",
        service_code="hebergement_logement",
        priority="high",
        city="Boulogne-Billancourt",
        name="Lina B.",
        email="lina.b@example.org",
        phone="+33 6 16 28 37 47",
        category="hebergement_urgence",
    ),
    DemoCase(
        title="Retard de paiement des aides et rupture de droits",
        description="Le dossier necessite un traitement prioritaire pour eviter une aggravation de la precarite.",
        service_code="acces_aux_droits",
        priority="high",
        city="Boulogne-Billancourt",
        name="Hugo D.",
        email="hugo.d@example.org",
        phone="+33 6 17 29 38 48",
        category="rupture_droits_sociaux",
    ),
    DemoCase(
        title="Demande de colis alimentaire pour famille en difficulte",
        description="Le menage signale une tension budgetaire severe et demande un soutien alimentaire ponctuel.",
        service_code="aide_alimentaire",
        priority="medium",
        city="Boulogne-Billancourt",
        name="Fatima R.",
        email="fatima.r@example.org",
        phone="+33 6 18 30 39 49",
        category="aide_alimentaire",
    ),
    DemoCase(
        title="Voisinage inquiet pour une personne agee sans visite",
        description="Une verification sociale est demandee en raison d'un isolement important depuis plusieurs jours.",
        service_code="seniors_isolement",
        priority="medium",
        city="Boulogne-Billancourt",
        name="Jeanne C.",
        email="jeanne.c@example.org",
        phone="+33 6 19 31 40 50",
        category="isolement_personne_agee",
    ),
    DemoCase(
        title="Conflit familial avec risque de violences recurrentes",
        description="Le dossier releve d'une vigilance renforcee avec coordination immediate des acteurs de protection.",
        service_code="protection_violences",
        priority="critical",
        city="Boulogne-Billancourt",
        name="Signalement confidentiel 2",
        email="signalement2@example.org",
        phone="+33 6 20 32 41 51",
        category="violence_domestique",
    ),
    DemoCase(
        title="Orientation sociale pour menage en precarite energetique",
        description="Un entretien d'accueil social est requis pour cadrer les priorites d'accompagnement.",
        service_code="accueil_social",
        priority="low",
        city="Boulogne-Billancourt",
        name="Michel P.",
        email="michel.p@example.org",
        phone="+33 6 21 33 42 52",
        category="precarite_energetique",
    ),
    DemoCase(
        title="Demande de logement temporaire apres separation",
        description="La personne se retrouve sans solution stable et sollicite une orientation vers l'hebergement adapte.",
        service_code="hebergement_logement",
        priority="high",
        city="Boulogne-Billancourt",
        name="Elodie F.",
        email="elodie.f@example.org",
        phone="+33 6 22 34 43 53",
        category="logement",
    ),
    DemoCase(
        title="Personne agee avec perte d'autonomie et isolement",
        description="La situation justifie un suivi rapproche avec appui pour les besoins du quotidien.",
        service_code="seniors_isolement",
        priority="high",
        city="Boulogne-Billancourt",
        name="Andre V.",
        email="andre.v@example.org",
        phone="+33 6 23 35 44 54",
        category="seniors",
    ),
    DemoCase(
        title="Demande d'aide alimentaire pour etudiant isole",
        description="Un appui alimentaire temporaire est sollicite dans l'attente d'une stabilisation des ressources.",
        service_code="aide_alimentaire",
        priority="low",
        city="Boulogne-Billancourt",
        name="Malo S.",
        email="malo.s@example.org",
        phone="+33 6 24 36 45 55",
        category="aide_alimentaire",
    ),
    DemoCase(
        title="Demarches securite sociale bloquees",
        description="Le dossier doit etre regularise rapidement afin de retablir l'acces aux droits essentiels.",
        service_code="acces_aux_droits",
        priority="medium",
        city="Boulogne-Billancourt",
        name="Ines H.",
        email="ines.h@example.org",
        phone="+33 6 25 37 46 56",
        category="accompagnement_administratif",
    ),
    DemoCase(
        title="Signalement de violences conjugales et besoin de protection immediate",
        description="Le niveau de risque est eleve et une action coordonnee est necessaire sans delai.",
        service_code="protection_violences",
        priority="critical",
        city="Boulogne-Billancourt",
        name="Signalement confidentiel 3",
        email="signalement3@example.org",
        phone="+33 6 26 38 47 57",
        category="violence_domestique",
    ),
    DemoCase(
        title="Accueil social pour situation de surendettement",
        description="Un premier cadrage social est demande pour organiser les relais vers les partenaires competents.",
        service_code="accueil_social",
        priority="medium",
        city="Boulogne-Billancourt",
        name="Damien E.",
        email="damien.e@example.org",
        phone="+33 6 27 39 48 58",
        category="orientation_sociale",
    ),
    DemoCase(
        title="Famille en hotel social sans perspective de relogement",
        description="La famille exprime un besoin de stabilisation rapide avec evaluation du parcours logement.",
        service_code="hebergement_logement",
        priority="high",
        city="Boulogne-Billancourt",
        name="Amina G.",
        email="amina.g@example.org",
        phone="+33 6 28 40 49 59",
        category="logement",
    ),
    DemoCase(
        title="Demande de suivi senior apres sortie d'hospitalisation",
        description="Une coordination locale est sollicitee pour limiter le risque de rupture de suivi.",
        service_code="seniors_isolement",
        priority="medium",
        city="Boulogne-Billancourt",
        name="Lucien B.",
        email="lucien.b@example.org",
        phone="+33 6 29 41 50 60",
        category="sante",
    ),
    DemoCase(
        title="Demande alimentaire urgente pour foyer avec enfants",
        description="Le foyer signale une absence de denrees suffisantes pour les prochains jours.",
        service_code="aide_alimentaire",
        priority="high",
        city="Boulogne-Billancourt",
        name="Sabrina Y.",
        email="sabrina.y@example.org",
        phone="+33 6 30 42 51 61",
        category="aide_alimentaire",
    ),
    DemoCase(
        title="Dossier administratif RSA incomplet",
        description="La personne demande un accompagnement pour finaliser les justificatifs requis.",
        service_code="acces_aux_droits",
        priority="low",
        city="Boulogne-Billancourt",
        name="Theo J.",
        email="theo.j@example.org",
        phone="+33 6 31 43 52 62",
        category="accompagnement_administratif",
    ),
    DemoCase(
        title="Signalement de menace au domicile avec mineur",
        description="Le contexte impose une evaluation prioritaire et des mesures de protection adaptees.",
        service_code="protection_violences",
        priority="critical",
        city="Boulogne-Billancourt",
        name="Signalement confidentiel 4",
        email="signalement4@example.org",
        phone="+33 6 32 44 53 63",
        category="violence_domestique",
    ),
    DemoCase(
        title="Demande d'accueil social pour orientation associative",
        description="Un entretien de premiere ligne est demande afin d'orienter vers la structure locale appropriee.",
        service_code="accueil_social",
        priority="low",
        city="Boulogne-Billancourt",
        name="Romain N.",
        email="romain.n@example.org",
        phone="+33 6 33 45 54 64",
        category="orientation_sociale",
    ),
    DemoCase(
        title="Famille sans solution de logement apres expulsion",
        description="Le menage sollicite une prise en charge rapide pour eviter une aggravation de la situation.",
        service_code="hebergement_logement",
        priority="critical",
        city="Boulogne-Billancourt",
        name="Meriem Z.",
        email="meriem.z@example.org",
        phone="+33 6 34 46 55 65",
        category="hebergement_urgence",
    ),
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed service-routed French demo requests for CCAS operational testing."
    )
    parser.add_argument(
        "--structure-slug",
        default=DEFAULT_TARGET_STRUCTURE_SLUG,
        help="Target structure slug for tenant-specific demo seed (default: default).",
    )
    parser.add_argument(
        "--confirm-canonical-db",
        action="store_true",
        help="Required safety flag. Refuses writes without explicit confirmation.",
    )
    return parser.parse_args()


def _ensure_seed_user() -> User:
    user = User.query.order_by(User.id.asc()).first()
    if user is not None:
        return user

    user = User(
        username="demo_requester_services",
        email="demo.requester.services@helpchain.local",
        role="user",
        is_active=True,
    )
    if hasattr(user, "set_password"):
        user.set_password("Example-Test-Password-123!")
    db.session.add(user)
    db.session.commit()
    return user


def _risk_level_from_priority(priority: str) -> str:
    mapping = {
        "low": "standard",
        "medium": "attention",
        "high": "high",
        "critical": "critical",
    }
    return mapping.get((priority or "").strip().lower(), "standard")


def _risk_score_from_priority(priority: str) -> int:
    mapping = {
        "low": 25,
        "medium": 55,
        "high": 80,
        "critical": 95,
    }
    return mapping.get((priority or "").strip().lower(), 40)


def _ensure_services_for_structure(structure_id: int, service_codes: list[str]) -> None:
    for code in service_codes:
        name = SERVICE_DEFINITIONS.get(code, code)
        service = StructureService.query.filter_by(
            structure_id=structure_id,
            code=code,
        ).first()
        if service is None:
            db.session.add(
                StructureService(
                    structure_id=structure_id,
                    code=code,
                    name=name,
                    is_active=True,
                )
            )
            continue
        if service.name != name:
            service.name = name
        if not bool(service.is_active):
            service.is_active = True


def main() -> int:
    args = _parse_args()
    print(f"APP: {APP_IMPORT_PATH}")

    with app.app_context():
        db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        print_app_db_preflight(db_uri)

        if not args.confirm_canonical_db:
            print(canonical_confirmation_error())
            return 2

        if not is_canonical_db_uri(db_uri):
            print(canonical_mismatch_error(db_uri))
            return 2

        target_slug = (args.structure_slug or "").strip().lower()
        if not target_slug:
            print("ERROR: --structure-slug must not be empty.")
            return 2

        structure = Structure.query.filter_by(slug=target_slug).first()
        if structure is None:
            print(f"ERROR: target structure not found: {target_slug}")
            return 1

        service_codes = sorted({case.service_code for case in DEMO_CASES})
        _ensure_services_for_structure(structure.id, service_codes)
        db.session.flush()

        services = (
            StructureService.query.filter(
                StructureService.structure_id == structure.id,
                StructureService.code.in_(service_codes),
            )
            .order_by(StructureService.code.asc())
            .all()
        )
        service_map = {service.code: service for service in services}
        missing_codes = [code for code in service_codes if code not in service_map]
        if missing_codes:
            print(f"ERROR: required service code(s) missing: {', '.join(missing_codes)}")
            print(
                "HINT: run scripts/seed_demo_services.py --confirm-canonical-db "
                "--structure-slug <slug>"
            )
            return 1

        existing_count = int(
            Request.query.filter(Request.structure_id == structure.id).count()
        )
        if existing_count > MAX_EXISTING_REQUESTS_PER_TARGET:
            print("Demo seed skipped: target structure already contains enough requests.")
            print(f"Target structure: {target_slug}")
            print(f"Existing requests in target structure: {existing_count}")
            return 0

        existing_titles = {
            (row[0] or "").strip()
            for row in (
                db.session.query(Request.title)
                .filter(
                    Request.structure_id == structure.id,
                    Request.source_channel == "service_routed_demo_seed",
                )
                .all()
            )
            if row and row[0]
        }

        target_to_add = max(0, TARGET_REQUEST_COUNT - existing_count)
        if target_to_add == 0:
            print("Demo seed skipped: target structure already has demo volume.")
            print(f"Target structure: {target_slug}")
            print(f"Existing requests in target structure: {existing_count}")
            return 0

        seed_user = _ensure_seed_user()
        now = datetime.now(UTC).replace(tzinfo=None)
        created_requests: list[Request] = []

        for idx, case in enumerate(DEMO_CASES):
            if len(created_requests) >= target_to_add:
                break
            if case.title in existing_titles:
                continue

            status = STATUS_SEQUENCE[idx % len(STATUS_SEQUENCE)]
            created_at = now - timedelta(
                hours=CREATED_DELTAS_HOURS[idx % len(CREATED_DELTAS_HOURS)]
            )
            service = service_map[case.service_code]

            req = Request(
                title=case.title,
                description=case.description,
                message=case.description,
                status=status,
                priority=case.priority,
                category=case.category,
                city=case.city,
                region="Ile-de-France",
                location_text=case.city,
                name=case.name,
                email=case.email,
                phone=case.phone,
                user_id=seed_user.id,
                structure_id=structure.id,
                service_id=service.id,
                source_channel="service_routed_demo_seed",
                created_at=created_at,
                updated_at=created_at,
                completed_at=(
                    created_at + timedelta(hours=6) if status == "done" else None
                ),
                risk_level=_risk_level_from_priority(case.priority),
                risk_score=_risk_score_from_priority(case.priority),
            )
            created_requests.append(req)
            existing_titles.add(case.title)

        if not created_requests:
            print("Demo seed skipped: no new demo requests to add for target structure.")
            print(f"Target structure: {target_slug}")
            return 0

        db.session.add_all(created_requests)
        db.session.commit()

        print(f"Target structure: {target_slug} (id={structure.id})")
        print(f"Seeded demo requests: {len(created_requests)}")
        print(f"Target structure requests total: {existing_count + len(created_requests)}")
        print(
            "Statuses distribution:",
            {
                s: sum(1 for r in created_requests if (r.status or "").lower() == s)
                for s in ("new", "triage", "assigned", "in_progress", "done", "rejected")
            },
        )
        print(
            "Services distribution:",
            {
                code: sum(
                    1
                    for r in created_requests
                    if r.service_id == service_map[code].id
                )
                for code in service_codes
            },
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
