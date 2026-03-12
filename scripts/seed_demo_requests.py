#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

# Ensure project root is importable when running from scripts/ directly.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.appy import app
from backend.extensions import db
from backend.models import AdminUser, Request, User

APP_IMPORT_PATH = "backend.appy:app"
CANONICAL_DB_URI = "sqlite:///C:/dev/HelpChain.bg/backend/instance/app_clean.db"
MAX_EXISTING_REQUESTS = 50


@dataclass(frozen=True)
class DemoCase:
    title: str
    description: str
    city: str
    category: str
    status: str
    priority: str
    risk_level: str
    risk_score: int
    risk_signals: list[str]
    created_delta_hours: int
    assign_owner: bool
    name: str
    email: str
    phone: str


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed realistic French social demo requests for local admin testing."
    )
    parser.add_argument(
        "--confirm-canonical-db",
        action="store_true",
        help="Required safety flag. Refuses writes without explicit confirmation.",
    )
    return parser.parse_args()


def _normalize_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _seed_cases() -> list[DemoCase]:
    return [
        DemoCase(
            title="Famille sans hébergement stable à Paris 19e",
            description="Famille avec deux enfants sans solution d’hébergement stable depuis plusieurs nuits. Besoin d’orientation rapide vers un dispositif d’urgence.",
            city="Paris",
            category="logement",
            status="new",
            priority="urgent",
            risk_level="high",
            risk_score=82,
            risk_signals=["no_owner", "housing_instability"],
            created_delta_hours=2,
            assign_owner=False,
            name="Samira B.",
            email="samira.b@example.org",
            phone="+33 6 10 22 33 44",
        ),
        DemoCase(
            title="Demande d’aide alimentaire - secteur Boulogne",
            description="Mère isolée en fin de droits avec rupture de ressources. Demande de soutien alimentaire immédiat pour la semaine.",
            city="Boulogne-Billancourt",
            category="aide_alimentaire",
            status="triage",
            priority="attention",
            risk_level="medium",
            risk_score=58,
            risk_signals=["not_seen_72h"],
            created_delta_hours=8,
            assign_owner=True,
            name="Claire T.",
            email="claire.t@example.org",
            phone="+33 6 21 45 87 10",
        ),
        DemoCase(
            title="Signalement de violence intrafamiliale avec mineur",
            description="Situation signalée de violence au sein du foyer avec présence d’un enfant. Évaluation pluridisciplinaire à enclencher sans délai.",
            city="Meudon",
            category="violence_domestique",
            status="assigned",
            priority="urgent",
            risk_level="critical",
            risk_score=96,
            risk_signals=["violence", "child_present", "assign_immediately"],
            created_delta_hours=24,
            assign_owner=True,
            name="Anonyme (signalement)",
            email="signalement.meudon@example.org",
            phone="+33 6 98 75 42 11",
        ),
        DemoCase(
            title="Personne âgée isolée - suivi quotidien absent",
            description="Personne âgée vivant seule, difficultés pour faire les courses et préparer les repas. Aucun relais familial de proximité identifié.",
            city="Issy-les-Moulineaux",
            category="isolement_personne_agee",
            status="in_progress",
            priority="standard",
            risk_level="low",
            risk_score=34,
            risk_signals=["followup_needed"],
            created_delta_hours=24,
            assign_owner=True,
            name="René L.",
            email="rene.l@example.org",
            phone="+33 6 44 70 12 03",
        ),
        DemoCase(
            title="Accompagnement démarches CAF et CPAM",
            description="Demande d’aide administrative pour démarches CAF et sécurité sociale. Personne en difficulté numérique.",
            city="Paris",
            category="accompagnement_administratif",
            status="new",
            priority="standard",
            risk_level="low",
            risk_score=22,
            risk_signals=[],
            created_delta_hours=48,
            assign_owner=False,
            name="Mireille D.",
            email="mireille.d@example.org",
            phone="+33 6 55 88 19 27",
        ),
        DemoCase(
            title="Coordination médicale et soutien psychologique",
            description="Personne isolée nécessitant accompagnement médical et soutien psychologique après hospitalisation récente.",
            city="Meudon",
            category="soutien_psychologique",
            status="triage",
            priority="attention",
            risk_level="medium",
            risk_score=63,
            risk_signals=["health_followup"],
            created_delta_hours=48,
            assign_owner=True,
            name="Nadia F.",
            email="nadia.f@example.org",
            phone="+33 6 74 11 28 65",
        ),
        DemoCase(
            title="Aide famille monoparentale en rupture de garde",
            description="Parent isolé avec difficultés de garde et risque de déscolarisation. Demande d’appui social et orientation locale.",
            city="Boulogne-Billancourt",
            category="aide_famille",
            status="assigned",
            priority="attention",
            risk_level="high",
            risk_score=76,
            risk_signals=["family_instability"],
            created_delta_hours=72,
            assign_owner=True,
            name="Yassine R.",
            email="yassine.r@example.org",
            phone="+33 6 15 26 37 48",
        ),
        DemoCase(
            title="Demande de suivi santé mentale en attente",
            description="Orientation psychologique demandée, sans rendez-vous confirmé à ce stade. Besoin de coordination entre acteurs de secteur.",
            city="Issy-les-Moulineaux",
            category="soutien_psychologique",
            status="in_progress",
            priority="attention",
            risk_level="medium",
            risk_score=55,
            risk_signals=["not_seen_72h", "manager_review_today"],
            created_delta_hours=72,
            assign_owner=False,
            name="Luc P.",
            email="luc.p@example.org",
            phone="+33 6 80 18 44 90",
        ),
        DemoCase(
            title="Situation logement dégradée - risque d’expulsion",
            description="Ménage menacé d’expulsion, impayés cumulés et absence de solution alternative identifiée.",
            city="Paris",
            category="logement",
            status="new",
            priority="urgent",
            risk_level="high",
            risk_score=88,
            risk_signals=["no_owner", "housing_critical"],
            created_delta_hours=96,
            assign_owner=False,
            name="Hakim A.",
            email="hakim.a@example.org",
            phone="+33 6 61 29 83 14",
        ),
        DemoCase(
            title="Demande alimentaire et santé enfant",
            description="Famille avec enfant en bas âge, difficultés alimentaires et suivi pédiatrique irrégulier.",
            city="Meudon",
            category="aide_alimentaire",
            status="assigned",
            priority="urgent",
            risk_level="high",
            risk_score=79,
            risk_signals=["child_vulnerability"],
            created_delta_hours=96,
            assign_owner=True,
            name="Fatou N.",
            email="fatou.n@example.org",
            phone="+33 6 42 31 73 00",
        ),
        DemoCase(
            title="Suivi administratif non finalisé",
            description="Dossier administratif incomplet après plusieurs rendez-vous manqués. Besoin de relance structurée.",
            city="Boulogne-Billancourt",
            category="accompagnement_administratif",
            status="triage",
            priority="standard",
            risk_level="low",
            risk_score=28,
            risk_signals=["followup_needed"],
            created_delta_hours=168,
            assign_owner=False,
            name="Pierre G.",
            email="pierre.g@example.org",
            phone="+33 6 37 92 15 60",
        ),
        DemoCase(
            title="Violence conjugale - mise à l’abri prioritaire",
            description="Personne victime de violences répétées, demande de mise à l’abri et coordination immédiate avec partenaires locaux.",
            city="Issy-les-Moulineaux",
            category="violence_domestique",
            status="in_progress",
            priority="urgent",
            risk_level="critical",
            risk_score=98,
            risk_signals=["violence", "assign_immediately", "manager_review_today"],
            created_delta_hours=8,
            assign_owner=True,
            name="Confidentiel",
            email="confidentiel.issy@example.org",
            phone="+33 6 90 11 55 33",
        ),
        DemoCase(
            title="Isolement d’une personne âgée - coordination voisinage",
            description="Alerte de voisinage concernant une personne âgée sans visites régulières. Besoin de vérification sociale.",
            city="Paris",
            category="isolement_personne_agee",
            status="assigned",
            priority="attention",
            risk_level="medium",
            risk_score=49,
            risk_signals=["not_seen_72h"],
            created_delta_hours=24,
            assign_owner=True,
            name="Georgette M.",
            email="georgette.m@example.org",
            phone="+33 6 32 90 41 17",
        ),
        DemoCase(
            title="Demande de soutien familial - conflit parental",
            description="Conflit parental impactant la stabilité des enfants. Demande d’accompagnement et médiation sociale.",
            city="Meudon",
            category="aide_famille",
            status="new",
            priority="attention",
            risk_level="medium",
            risk_score=61,
            risk_signals=["family_instability", "no_owner"],
            created_delta_hours=2,
            assign_owner=False,
            name="Élodie C.",
            email="elodie.c@example.org",
            phone="+33 6 53 21 18 47",
        ),
        DemoCase(
            title="Clôture accompagnement administratif",
            description="Demande traitée et clôturée après finalisation des démarches administratives et validation de la situation.",
            city="Issy-les-Moulineaux",
            category="accompagnement_administratif",
            status="done",
            priority="standard",
            risk_level="low",
            risk_score=15,
            risk_signals=[],
            created_delta_hours=168,
            assign_owner=True,
            name="Laura B.",
            email="laura.b@example.org",
            phone="+33 6 11 22 83 90",
        ),
        DemoCase(
            title="Demande rejetée - dossier incomplet",
            description="Demande rejetée après relances multiples sans pièces minimales nécessaires pour instruction.",
            city="Boulogne-Billancourt",
            category="accompagnement_administratif",
            status="rejected",
            priority="standard",
            risk_level="low",
            risk_score=12,
            risk_signals=[],
            created_delta_hours=96,
            assign_owner=True,
            name="Antoine V.",
            email="antoine.v@example.org",
            phone="+33 6 77 64 90 02",
        ),
        DemoCase(
            title="Suivi santé chronique avec risque d’isolement",
            description="Personne avec pathologie chronique, absence de suivi régulier et isolement social progressif.",
            city="Paris",
            category="sante",
            status="in_progress",
            priority="attention",
            risk_level="high",
            risk_score=74,
            risk_signals=["health_followup", "not_seen_72h"],
            created_delta_hours=72,
            assign_owner=True,
            name="Jules K.",
            email="jules.k@example.org",
            phone="+33 6 14 88 63 25",
        ),
        DemoCase(
            title="Aide alimentaire ponctuelle - étudiant isolé",
            description="Étudiant sans ressources immédiates, demande d’aide alimentaire ponctuelle et orientation vers partenaires locaux.",
            city="Meudon",
            category="aide_alimentaire",
            status="triage",
            priority="standard",
            risk_level="medium",
            risk_score=46,
            risk_signals=["followup_needed"],
            created_delta_hours=8,
            assign_owner=False,
            name="Malo R.",
            email="malo.r@example.org",
            phone="+33 6 63 09 55 72",
        ),
        DemoCase(
            title="Logement indigne signalé - enfant concerné",
            description="Signalement de logement insalubre avec enfant concerné. Intervention coordonnée à programmer avec urgence.",
            city="Issy-les-Moulineaux",
            category="logement",
            status="assigned",
            priority="urgent",
            risk_level="critical",
            risk_score=94,
            risk_signals=["child_present", "assign_immediately"],
            created_delta_hours=4 * 24,
            assign_owner=True,
            name="Sonia E.",
            email="sonia.e@example.org",
            phone="+33 6 25 78 32 10",
        ),
        DemoCase(
            title="Soutien psychologique post-traumatique",
            description="Demande de soutien psychologique après événement traumatique, besoin d’un relais thérapeutique rapide.",
            city="Boulogne-Billancourt",
            category="soutien_psychologique",
            status="new",
            priority="attention",
            risk_level="high",
            risk_score=72,
            risk_signals=["no_owner", "manager_review_today"],
            created_delta_hours=24,
            assign_owner=False,
            name="Nora S.",
            email="nora.s@example.org",
            phone="+33 6 19 45 88 31",
        ),
    ]


def _resolve_seed_user() -> User:
    user = User.query.order_by(User.id.asc()).first()
    if user:
        return user

    user = User(
        username="demo_requester",
        email="demo.requester@helpchain.local",
        role="user",
        is_active=True,
    )
    user.set_password("Example-Test-Password-123!")
    db.session.add(user)
    db.session.commit()
    return user


def _owner_pool() -> list[AdminUser]:
    return AdminUser.query.filter_by(is_active=True).order_by(AdminUser.id.asc()).all()


def _build_request(
    case: DemoCase, now: datetime, seed_user_id: int, owner_id: int | None
) -> Request:
    created_at = now - timedelta(hours=int(case.created_delta_hours))
    completed_at = None
    if case.status == "done":
        completed_at = created_at + timedelta(hours=12)

    req = Request(
        title=case.title,
        description=case.description,
        message=case.description,
        name=case.name,
        email=case.email,
        phone=case.phone,
        city=case.city,
        region="Île-de-France",
        location_text=case.city,
        status=case.status,
        priority=case.priority,
        category=case.category,
        source_channel="admin_demo_seed",
        user_id=seed_user_id,
        created_at=created_at,
        updated_at=created_at,
        completed_at=completed_at,
        owner_id=owner_id,
        owned_at=(created_at + timedelta(hours=2)) if owner_id else None,
        risk_level=case.risk_level,
        risk_score=int(case.risk_score),
        risk_signals=json.dumps(case.risk_signals, ensure_ascii=False),
    )
    return req


def main() -> int:
    args = _parse_args()

    print(f"APP: {APP_IMPORT_PATH}")

    with app.app_context():
        db_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        print(f"DB: {db_uri}")

        if not args.confirm_canonical_db:
            print("ERROR: missing required flag --confirm-canonical-db")
            print("HINT: this write script is manual-only and requires explicit confirmation.")
            return 1

        if db_uri != CANONICAL_DB_URI:
            print("ERROR: Refusing to seed non-canonical DB target.")
            print(f"Expected: {CANONICAL_DB_URI}")
            print(f"Actual:   {db_uri}")
            return 1

        existing_count = int(db.session.query(Request.id).count())
        if existing_count > MAX_EXISTING_REQUESTS:
            print("Demo seed skipped: database already populated.")
            print(f"Existing requests: {existing_count}")
            return 0

        seed_user = _resolve_seed_user()
        owners = _owner_pool()
        now = _normalize_now()

        cases = _seed_cases()
        created: list[Request] = []
        owner_idx = 0
        for case in cases:
            owner_id = None
            if case.assign_owner and owners:
                owner_id = owners[owner_idx % len(owners)].id
                owner_idx += 1
            created.append(_build_request(case, now, seed_user.id, owner_id))

        db.session.add_all(created)
        db.session.commit()

        print(f"Seeded demo requests: {len(created)}")
        print(
            "Statuses distribution:",
            {
                s: sum(1 for r in created if (r.status or "").lower() == s)
                for s in ("new", "triage", "assigned", "in_progress", "done", "rejected")
            },
        )
        print(
            "Cities distribution:",
            {
                city: sum(1 for r in created if r.city == city)
                for city in (
                    "Paris",
                    "Issy-les-Moulineaux",
                    "Boulogne-Billancourt",
                    "Meudon",
                )
            },
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
