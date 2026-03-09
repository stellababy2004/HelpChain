#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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

STATUS_DISTRIBUTION = [
    ("new", 10),
    ("triage", 10),
    ("assigned", 10),
    ("in_progress", 10),
    ("done", 6),
    ("rejected", 4),
]

CITIES = [
    "Paris",
    "Issy-les-Moulineaux",
    "Boulogne-Billancourt",
    "Meudon",
]

CREATED_DELTAS_HOURS = [2, 6, 12, 24, 48, 72, 120, 168, 240]


@dataclass(frozen=True)
class Theme:
    category: str
    title_prefix: str
    desc_core: str
    risk_level: str
    risk_score: int
    priority: str
    risk_signals: list[str]


THEMES: list[Theme] = [
    Theme(
        category="hebergement_urgence",
        title_prefix="Hébergement d’urgence",
        desc_core="Ménage sans solution d’hébergement pour la nuit, orientation rapide vers un dispositif de mise à l’abri.",
        risk_level="high",
        risk_score=84,
        priority="urgent",
        risk_signals=["no_owner", "housing_instability"],
    ),
    Theme(
        category="logement_instable",
        title_prefix="Logement instable",
        desc_core="Situation de logement précaire avec risque de rupture dans les prochains jours.",
        risk_level="high",
        risk_score=78,
        priority="urgent",
        risk_signals=["housing_instability"],
    ),
    Theme(
        category="aide_alimentaire",
        title_prefix="Aide alimentaire",
        desc_core="Demande de soutien alimentaire temporaire pour un foyer en tension budgétaire.",
        risk_level="medium",
        risk_score=56,
        priority="attention",
        risk_signals=["followup_needed"],
    ),
    Theme(
        category="isolement_personne_agee",
        title_prefix="Isolement d’une personne âgée",
        desc_core="Personne âgée isolée nécessitant un accompagnement pour les courses et les démarches de santé.",
        risk_level="medium",
        risk_score=51,
        priority="attention",
        risk_signals=["not_seen_72h"],
    ),
    Theme(
        category="accompagnement_administratif",
        title_prefix="Accompagnement administratif",
        desc_core="Demande d’aide administrative pour renouvellement de droits CAF et assurance maladie.",
        risk_level="low",
        risk_score=26,
        priority="standard",
        risk_signals=[],
    ),
    Theme(
        category="violences_intrafamiliales",
        title_prefix="Violences intrafamiliales",
        desc_core="Signalement de violences au domicile, besoin d’évaluation prioritaire avec coordination partenariale.",
        risk_level="critical",
        risk_score=97,
        priority="urgent",
        risk_signals=["violence", "assign_immediately", "manager_review_today"],
    ),
    Theme(
        category="soutien_psychologique",
        title_prefix="Soutien psychologique",
        desc_core="Besoin de soutien psychologique avec orientation vers un suivi adapté au contexte social.",
        risk_level="medium",
        risk_score=60,
        priority="attention",
        risk_signals=["health_followup"],
    ),
    Theme(
        category="acces_soins",
        title_prefix="Accès aux soins",
        desc_core="Difficultés d’accès aux soins de première nécessité, coordination requise avec les acteurs de santé.",
        risk_level="high",
        risk_score=73,
        priority="attention",
        risk_signals=["health_followup", "not_seen_72h"],
    ),
    Theme(
        category="famille_monoparentale",
        title_prefix="Famille monoparentale en difficulté",
        desc_core="Parent isolé avec enfants, difficultés cumulées de garde et de stabilité financière.",
        risk_level="high",
        risk_score=76,
        priority="urgent",
        risk_signals=["family_instability"],
    ),
    Theme(
        category="mineur_risque",
        title_prefix="Situation de mineur à risque",
        desc_core="Situation préoccupante impliquant un mineur, évaluation socio-éducative à engager rapidement.",
        risk_level="critical",
        risk_score=95,
        priority="urgent",
        risk_signals=["child_present", "manager_review_today"],
    ),
    Theme(
        category="precarite_energetique",
        title_prefix="Précarité énergétique",
        desc_core="Foyer exposé à une coupure d’énergie, nécessité d’orientation vers aides d’urgence.",
        risk_level="medium",
        risk_score=59,
        priority="attention",
        risk_signals=["followup_needed"],
    ),
    Theme(
        category="rupture_droits_sociaux",
        title_prefix="Rupture de droits sociaux",
        desc_core="Interruption de droits sociaux entraînant une baisse immédiate des ressources du foyer.",
        risk_level="high",
        risk_score=81,
        priority="urgent",
        risk_signals=["rights_break", "no_owner"],
    ),
    Theme(
        category="orientation_association_locale",
        title_prefix="Orientation vers association locale",
        desc_core="Demande d’orientation vers une structure associative adaptée au besoin du ménage.",
        risk_level="low",
        risk_score=24,
        priority="standard",
        risk_signals=[],
    ),
    Theme(
        category="accompagnement_handicap",
        title_prefix="Accompagnement handicap",
        desc_core="Besoin d’accompagnement social et administratif lié à une situation de handicap.",
        risk_level="medium",
        risk_score=57,
        priority="attention",
        risk_signals=["followup_needed"],
    ),
    Theme(
        category="mediation_sociale",
        title_prefix="Médiation sociale",
        desc_core="Demande de médiation sociale pour apaiser une situation de tension locale récurrente.",
        risk_level="low",
        risk_score=31,
        priority="standard",
        risk_signals=[],
    ),
]

CRITICAL_DEMO_THEMES = {
    "violences_intrafamiliales",
    "mineur_risque",
    "hebergement_urgence",
    "acces_soins",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed rich French CCAS-style demo requests for local admin testing."
    )
    parser.add_argument(
        "--confirm-canonical-db",
        action="store_true",
        help="Required safety flag. Refuses writes without explicit confirmation.",
    )
    return parser.parse_args()


def _status_sequence() -> list[str]:
    out: list[str] = []
    for status, count in STATUS_DISTRIBUTION:
        out.extend([status] * count)
    return out


def _ensure_seed_user() -> User:
    user = User.query.order_by(User.id.asc()).first()
    if user:
        return user

    user = User(
        username="demo_requester_rich",
        email="demo.requester.rich@helpchain.local",
        role="user",
        is_active=True,
    )
    user.set_password("DemoRequesterRich123!")
    db.session.add(user)
    db.session.commit()
    return user


def _owner_pool() -> list[AdminUser]:
    return AdminUser.query.filter_by(is_active=True).order_by(AdminUser.id.asc()).all()


def _build_title(theme: Theme, city: str, idx: int) -> str:
    return f"{theme.title_prefix} - {city} (dossier {idx + 1:02d})"


def _build_description(theme: Theme, city: str, status: str) -> str:
    status_text = {
        "new": "Signalement nouvellement reçu, en attente de première qualification.",
        "triage": "Dossier en phase de triage avec priorisation opérationnelle.",
        "assigned": "Dossier affecté à un référent territorial pour action.",
        "in_progress": "Accompagnement en cours avec suivi inter-acteurs.",
        "done": "Accompagnement finalisé, situation stabilisée à ce stade.",
        "rejected": "Demande non retenue après analyse du périmètre d’intervention.",
    }.get(status, "Suivi en cours.")
    return f"{theme.desc_core} Secteur concerné: {city}. {status_text}"


def _created_at_from_delta(now: datetime, idx: int) -> datetime:
    hours = CREATED_DELTAS_HOURS[idx % len(CREATED_DELTAS_HOURS)]
    return now - timedelta(hours=hours)


def _should_assign_owner(status: str, idx: int, has_owners: bool) -> bool:
    if not has_owners:
        return False
    if status in {"assigned", "in_progress", "done"}:
        return True
    # Keep part of new/triage/rejected unassigned for pilotage visibility.
    return (idx % 3) == 0


def _make_demo_requests(now: datetime, seed_user_id: int, owners: list[AdminUser]) -> list[Request]:
    statuses = _status_sequence()
    owner_idx = 0
    records: list[Request] = []

    for idx in range(len(statuses)):
        status = statuses[idx]
        city = CITIES[idx % len(CITIES)]
        theme = THEMES[idx % len(THEMES)]

        # Force a few explicitly critical operational demo cases.
        if idx in {3, 11, 19, 27, 35}:
            theme = next(t for t in THEMES if t.category in CRITICAL_DEMO_THEMES)

        created_at = _created_at_from_delta(now, idx)
        owner_id = None
        if _should_assign_owner(status, idx, bool(owners)):
            owner_id = owners[owner_idx % len(owners)].id
            owner_idx += 1

        completed_at = None
        if status == "done":
            completed_at = created_at + timedelta(hours=18)

        req = Request(
            title=_build_title(theme, city, idx),
            description=_build_description(theme, city, status),
            message=_build_description(theme, city, status),
            name=f"Demandeur {idx + 1:02d}",
            email=f"demandeur{idx + 1:02d}@example.org",
            phone=f"+33 6 {10 + (idx % 80):02d} {20 + (idx % 70):02d} {30 + (idx % 60):02d} {40 + (idx % 50):02d}",
            city=city,
            region="Île-de-France",
            location_text=city,
            category=theme.category,
            status=status,
            priority=theme.priority,
            source_channel="admin_demo_seed_rich",
            user_id=seed_user_id,
            owner_id=owner_id,
            owned_at=(created_at + timedelta(hours=2)) if owner_id else None,
            created_at=created_at,
            updated_at=created_at,
            completed_at=completed_at,
            risk_level=theme.risk_level,
            risk_score=int(theme.risk_score),
            risk_signals=json.dumps(theme.risk_signals, ensure_ascii=False),
        )
        records.append(req)
    return records


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
            print("Demo seed skipped: database already contains enough requests.")
            print(f"Existing requests: {existing_count}")
            return 0

        seed_user = _ensure_seed_user()
        owners = _owner_pool()
        now = datetime.now(UTC).replace(tzinfo=None)

        demo_requests = _make_demo_requests(now, seed_user.id, owners)
        db.session.add_all(demo_requests)
        db.session.commit()

        print(f"Seeded demo requests: {len(demo_requests)}")
        print(
            "Statuses distribution:",
            {
                s: sum(1 for r in demo_requests if (r.status or "").lower() == s)
                for s in ("new", "triage", "assigned", "in_progress", "done", "rejected")
            },
        )
        print(
            "Cities distribution:",
            {city: sum(1 for r in demo_requests if r.city == city) for city in CITIES},
        )
        print(
            "Risk distribution:",
            {
                rl: sum(1 for r in demo_requests if (r.risk_level or "").lower() == rl)
                for rl in ("low", "medium", "high", "critical")
            },
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
