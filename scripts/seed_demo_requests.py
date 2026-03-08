from __future__ import annotations

import argparse
import sys
from pathlib import Path
from datetime import UTC, datetime, timedelta

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.appy import app
from backend.extensions import db
from backend.local_db_guard import (
    canonical_confirmation_error,
    canonical_mismatch_error,
    is_canonical_db_uri,
    print_app_db_preflight,
)
from backend.models import AdminUser, Request, Structure, User, Volunteer

DEMO_PREFIX = "[DEMO]"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed structured demo requests")
    parser.add_argument(
        "--confirm-canonical-db",
        action="store_true",
        help="Required safety flag to allow DB writes",
    )
    return parser.parse_args()


def _preflight_or_fail(*, actual_uri: str, confirmed: bool) -> int:
    print_app_db_preflight(actual_uri)
    if not confirmed:
        print(canonical_confirmation_error())
        return 2
    if not is_canonical_db_uri(actual_uri):
        print(canonical_mismatch_error(actual_uri))
        return 2
    return 0


def _ensure_structure() -> Structure:
    structure = Structure.query.filter_by(slug="default").first()
    if structure:
        return structure
    structure = Structure(name="Default", slug="default")
    db.session.add(structure)
    db.session.flush()
    return structure


def _ensure_admin(username: str, email: str, role: str = "ops") -> AdminUser:
    admin = AdminUser.query.filter_by(username=username).first()
    if admin:
        return admin
    admin = AdminUser(username=username, email=email, role=role, is_active=True)
    admin.set_password("DemoAdmin123!")
    db.session.add(admin)
    db.session.flush()
    return admin


def _ensure_user(username: str, email: str) -> User:
    user = User.query.filter_by(username=username).first()
    if user:
        return user
    user = User(
        username=username,
        email=email,
        role="requester",
        is_active=True,
        password_hash="",
    )
    db.session.add(user)
    db.session.flush()
    return user


def _ensure_volunteer(email: str, name: str, phone: str) -> Volunteer:
    vol = Volunteer.query.filter_by(email=email).first()
    if vol:
        return vol
    vol = Volunteer(
        name=name,
        email=email,
        phone=phone,
        location="Paris",
        availability="weekday-evening",
        skills="logistics,translation,medical support",
        is_active=True,
    )
    db.session.add(vol)
    db.session.flush()
    return vol


def _clear_demo_requests() -> int:
    to_delete = Request.query.filter(Request.title.like(f"{DEMO_PREFIX}%")).all()
    count = len(to_delete)
    for row in to_delete:
        db.session.delete(row)
    db.session.flush()
    return count


def main() -> int:
    args = _parse_args()
    with app.app_context():
        actual_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
        guard_rc = _preflight_or_fail(
            actual_uri=actual_uri,
            confirmed=bool(args.confirm_canonical_db),
        )
        if guard_rc != 0:
            return guard_rc

        structure = _ensure_structure()
        admin_main = _ensure_admin("admin", "admin@helpchain.live", role="superadmin")
        admin_ops = _ensure_admin("ops_demo", "ops.demo@helpchain.live", role="ops")

        vol_anna = _ensure_volunteer("anna.vol@helpchain.live", "Anna Petrova", "+33600000001")
        vol_ivan = _ensure_volunteer("ivan.vol@helpchain.live", "Ivan Georgiev", "+33600000002")
        vol_maria = _ensure_volunteer("maria.vol@helpchain.live", "Maria Dimitrova", "+33600000003")

        req_user_1 = _ensure_user("requester_ana", "ana.requester@helpchain.live")
        req_user_2 = _ensure_user("requester_boris", "boris.requester@helpchain.live")
        req_user_3 = _ensure_user("requester_elena", "elena.requester@helpchain.live")

        removed = _clear_demo_requests()
        now = datetime.now(UTC)

        payloads = [
            {
                "title": f"{DEMO_PREFIX} Violence + urgence médicale sans owner",
                "description": "Contexte: signalement de violence avec risque immédiat. Demande: affectation d’un responsable territorial et contact médical d’urgence.",
                "status": "new",
                "priority": "urgent",
                "category": "emergency",
                "name": "Sofia T.",
                "email": "sofia.demo1@client.local",
                "phone": "+33611110001",
                "city": "Paris",
                "user_id": req_user_1.id,
                "owner_id": None,
                "assigned_volunteer_id": None,
                "created_at": now - timedelta(hours=90),
            },
            {
                "title": f"{DEMO_PREFIX} Food + isolement en attente",
                "description": "Contexte: personne isolée sans ressources alimentaires. Demande: mise en relation rapide avec une aide alimentaire locale.",
                "status": "pending",
                "priority": "high",
                "category": "food",
                "name": "Luc Martin",
                "email": "luc.demo2@client.local",
                "phone": "+33611110002",
                "city": "Lyon",
                "user_id": req_user_2.id,
                "owner_id": None,
                "assigned_volunteer_id": None,
                "created_at": now - timedelta(hours=60),
            },
            {
                "title": f"{DEMO_PREFIX} Logement instable avec owner",
                "description": "Contexte: menace d’expulsion pour une famille monoparentale. Demande: sécuriser une solution d’hébergement et organiser le suivi social.",
                "status": "in_progress",
                "priority": "high",
                "category": "housing",
                "name": "Claire N.",
                "email": "claire.demo3@client.local",
                "phone": "+33611110003",
                "city": "Marseille",
                "user_id": req_user_3.id,
                "owner_id": admin_main.id,
                "assigned_volunteer_id": vol_anna.id,
                "created_at": now - timedelta(hours=30),
            },
            {
                "title": f"{DEMO_PREFIX} Assistance standard déjà traitée",
                "description": "Contexte: besoin d’information administrative. Demande: orientation vers les démarches et clôture après retour à l’usager.",
                "status": "done",
                "priority": "medium",
                "category": "general",
                "name": "Nina B.",
                "email": "nina.demo4@client.local",
                "phone": "+33611110004",
                "city": "Bordeaux",
                "user_id": req_user_1.id,
                "owner_id": admin_ops.id,
                "assigned_volunteer_id": vol_ivan.id,
                "created_at": now - timedelta(days=4),
                "completed_at": now - timedelta(days=2),
            },
            {
                "title": f"{DEMO_PREFIX} Cas rejeté après vérification",
                "description": "Contexte: demande en doublon déjà traitée. Demande: clôture administrative sans action opérationnelle supplémentaire.",
                "status": "rejected",
                "priority": "low",
                "category": "general",
                "name": "Petar S.",
                "email": "petar.demo5@client.local",
                "phone": "+33611110005",
                "city": "Lille",
                "user_id": req_user_2.id,
                "owner_id": admin_ops.id,
                "assigned_volunteer_id": None,
                "created_at": now - timedelta(days=6),
            },
            {
                "title": f"{DEMO_PREFIX} Unassigned urgent santé",
                "description": "Contexte: besoin de soins sans interlocuteur identifié. Demande: affectation immédiate et coordination avec un acteur de santé.",
                "status": "unassigned",
                "priority": "urgent",
                "category": "health",
                "name": "Mira V.",
                "email": "mira.demo6@client.local",
                "phone": "+33611110006",
                "city": "Nantes",
                "user_id": req_user_3.id,
                "owner_id": None,
                "assigned_volunteer_id": None,
                "created_at": now - timedelta(hours=20),
            },
            {
                "title": f"{DEMO_PREFIX} Pending avec owner sans bénévole",
                "description": "Contexte: famille avec enfant en tension alimentaire. Demande: mobilisation d’un bénévole et planification d’un suivi sous 24 heures.",
                "status": "pending",
                "priority": "high",
                "category": "food",
                "name": "Olga D.",
                "email": "olga.demo7@client.local",
                "phone": "+33611110007",
                "city": "Toulouse",
                "user_id": req_user_1.id,
                "owner_id": admin_main.id,
                "assigned_volunteer_id": None,
                "created_at": now - timedelta(hours=52),
            },
            {
                "title": f"{DEMO_PREFIX} In progress avec bénévole mais stale",
                "description": "Contexte: accompagnement logement engagé mais sans avancée récente. Demande: relance opérationnelle et mise à jour du plan d’action.",
                "status": "in_progress",
                "priority": "medium",
                "category": "housing",
                "name": "Georgi R.",
                "email": "georgi.demo8@client.local",
                "phone": "+33611110008",
                "city": "Nice",
                "user_id": req_user_2.id,
                "owner_id": admin_ops.id,
                "assigned_volunteer_id": vol_maria.id,
                "created_at": now - timedelta(hours=80),
            },
            {
                "title": f"{DEMO_PREFIX} New low priority no signal",
                "description": "Contexte: demande d’information générale. Demande: réponse d’orientation et qualification du besoin.",
                "status": "new",
                "priority": "low",
                "category": "general",
                "name": "Ivana K.",
                "email": "ivana.demo9@client.local",
                "phone": "+33611110009",
                "city": "Rennes",
                "user_id": req_user_3.id,
                "owner_id": None,
                "assigned_volunteer_id": None,
                "created_at": now - timedelta(hours=3),
            },
            {
                "title": f"{DEMO_PREFIX} Pending violence owner assigned",
                "description": "Contexte: situation de violence avec danger signalé. Demande: revue managériale du dossier et coordination de protection.",
                "status": "pending",
                "priority": "urgent",
                "category": "safety",
                "name": "Milen A.",
                "email": "milen.demo10@client.local",
                "phone": "+33611110010",
                "city": "Strasbourg",
                "user_id": req_user_1.id,
                "owner_id": admin_main.id,
                "assigned_volunteer_id": vol_anna.id,
                "created_at": now - timedelta(hours=10),
            },
            {
                "title": f"{DEMO_PREFIX} Done after food support",
                "description": "Contexte: aide alimentaire organisée et délivrée. Demande: validation de la résolution et archivage du suivi.",
                "status": "done",
                "priority": "medium",
                "category": "food",
                "name": "Teodora P.",
                "email": "teodora.demo11@client.local",
                "phone": "+33611110011",
                "city": "Grenoble",
                "user_id": req_user_2.id,
                "owner_id": admin_ops.id,
                "assigned_volunteer_id": vol_ivan.id,
                "created_at": now - timedelta(days=3),
                "completed_at": now - timedelta(days=1),
            },
            {
                "title": f"{DEMO_PREFIX} Pending no owner 72h+",
                "description": "Contexte: parent isolé sans hébergement stable ni ressources. Demande: prise en charge prioritaire et affectation d’un responsable.",
                "status": "pending",
                "priority": "high",
                "category": "social",
                "name": "Lora M.",
                "email": "lora.demo12@client.local",
                "phone": "+33611110012",
                "city": "Montpellier",
                "user_id": req_user_3.id,
                "owner_id": None,
                "assigned_volunteer_id": None,
                "created_at": now - timedelta(hours=110),
            },
        ]

        created = 0
        for payload in payloads:
            req = Request(
                title=payload["title"],
                description=payload["description"],
                message=payload["description"],
                status=payload["status"],
                priority=payload["priority"],
                category=payload["category"],
                name=payload["name"],
                email=payload["email"],
                phone=payload["phone"],
                city=payload["city"],
                user_id=payload["user_id"],
                structure_id=structure.id,
                owner_id=payload["owner_id"],
                assigned_volunteer_id=payload["assigned_volunteer_id"],
                created_at=payload["created_at"],
                completed_at=payload.get("completed_at"),
            )
            db.session.add(req)
            created += 1

        db.session.commit()

        total_demo = (
            Request.query.filter(Request.title.like(f"{DEMO_PREFIX}%")).count()
        )
        by_status = (
            db.session.query(Request.status, db.func.count(Request.id))
            .filter(Request.title.like(f"{DEMO_PREFIX}%"))
            .group_by(Request.status)
            .all()
        )
        by_risk = (
            db.session.query(Request.risk_level, db.func.count(Request.id))
            .filter(Request.title.like(f"{DEMO_PREFIX}%"))
            .group_by(Request.risk_level)
            .all()
        )
        with_owner = (
            Request.query.filter(
                Request.title.like(f"{DEMO_PREFIX}%"), Request.owner_id.isnot(None)
            ).count()
        )
        without_owner = (
            Request.query.filter(
                Request.title.like(f"{DEMO_PREFIX}%"), Request.owner_id.is_(None)
            ).count()
        )

        print(f"Removed old demo requests: {removed}")
        print(f"Created demo requests: {created}")
        print(f"Total demo requests now: {total_demo}")
        print("Status breakdown:", {k or "null": v for k, v in by_status})
        print("Risk breakdown:", {k or "null": v for k, v in by_risk})
        print(f"Owner assigned: {with_owner} | Owner missing: {without_owner}")
        print("Demo data prefix:", DEMO_PREFIX)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
