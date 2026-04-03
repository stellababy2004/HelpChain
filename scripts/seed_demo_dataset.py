#!/usr/bin/env python
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.extensions import db
from backend.helpchain_backend.src.app import create_app
from backend.models import AdminUser, Request, Structure, User


DEFAULT_ADMIN_PASSWORD = "HelpChainDemo1"
DEFAULT_REQUESTER_PASSWORD = "HelpChainDemo1"


@dataclass(frozen=True)
class DemoRequest:
    name: str
    city: str
    title: str
    category: str
    status: str
    created_days_ago: int
    owner_username: str | None = None


DEMO_REQUESTS = [
    DemoRequest(
        name="Mme Laurent",
        city="Paris 15",
        title="Hebergement d'urgence",
        category="Hebergement d'urgence",
        status="open",
        created_days_ago=2,
    ),
    DemoRequest(
        name="M. Bernard",
        city="Boulogne-Billancourt",
        title="Aide alimentaire",
        category="Aide alimentaire",
        status="in_progress",
        created_days_ago=4,
        owner_username="agent_intake",
    ),
    DemoRequest(
        name="Mme Petit",
        city="Issy-les-Moulineaux",
        title="Acces aux droits",
        category="Acces aux droits",
        status="done",
        created_days_ago=8,
        owner_username="agent_intake",
    ),
    DemoRequest(
        name="M. Dubois",
        city="Nanterre",
        title="Isolement",
        category="Isolement",
        status="open",
        created_days_ago=3,
    ),
    DemoRequest(
        name="Mme Garcia",
        city="Courbevoie",
        title="Sante",
        category="Sante",
        status="in_progress",
        created_days_ago=5,
        owner_username="agent_intake",
    ),
    DemoRequest(
        name="M. Moreau",
        city="Colombes",
        title="Logement",
        category="Logement",
        status="cancelled",
        created_days_ago=10,
        owner_username="agent_intake",
    ),
]


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def ensure_structure(summary: dict[str, int]) -> Structure:
    structure = Structure.query.filter_by(slug="default").first()
    if structure is None:
        structure = Structure(name="Default", slug="default")
        db.session.add(structure)
        db.session.flush()
        summary["structure_created"] += 1
    else:
        summary["structure_found"] += 1
        if structure.name != "Default":
            structure.name = "Default"
    return structure


def ensure_admin_user(
    *,
    username: str,
    email: str,
    role: str,
    structure_id: int | None,
    summary: dict[str, int],
    summary_key_created: str,
    summary_key_found: str,
) -> AdminUser:
    user = AdminUser.query.filter(
        (AdminUser.username == username) | (AdminUser.email == email)
    ).first()
    if user is None:
        user = AdminUser(
            username=username,
            email=email,
            role=role,
            structure_id=structure_id,
            is_active=True,
        )
        user.set_password(DEFAULT_ADMIN_PASSWORD)
        db.session.add(user)
        db.session.flush()
        summary[summary_key_created] += 1
    else:
        summary[summary_key_found] += 1
        user.username = username
        user.email = email
        user.role = role
        user.structure_id = structure_id
        user.is_active = True
    return user


def ensure_requester_user(structure_id: int, summary: dict[str, int]) -> User:
    user = User.query.filter(
        (User.username == "requester_demo")
        | (User.email == "requester@helpchain.local")
    ).first()
    if user is None:
        user = User(
            username="requester_demo",
            email="requester@helpchain.local",
            role="requester",
            structure_id=structure_id,
            is_active=True,
        )
        user.set_password(DEFAULT_REQUESTER_PASSWORD)
        db.session.add(user)
        db.session.flush()
        summary["requester_created"] += 1
    else:
        summary["requester_found"] += 1
        user.username = "requester_demo"
        user.email = "requester@helpchain.local"
        user.role = "requester"
        user.structure_id = structure_id
        user.is_active = True
    return user


def ensure_demo_request(
    demo: DemoRequest,
    *,
    structure_id: int,
    requester_id: int,
    owner_lookup: dict[str, int],
    summary: dict[str, int],
) -> None:
    row = (
        Request.query.filter_by(
            structure_id=structure_id,
            name=demo.name,
            city=demo.city,
        )
        .order_by(Request.id.asc())
        .first()
    )

    now = utc_now_naive()
    created_at = now - timedelta(days=demo.created_days_ago)
    completed_at = None
    if demo.status in {"done", "cancelled"}:
        completed_at = created_at + timedelta(days=1)

    owner_id = owner_lookup.get(demo.owner_username) if demo.owner_username else None
    email_local = (
        demo.name.lower()
        .replace("mme ", "")
        .replace("m. ", "")
        .replace(" ", ".")
        .replace("'", "")
    )

    payload = {
        "title": demo.title,
        "description": f"{demo.category} - dossier de demonstration locale pour {demo.city}.",
        "name": demo.name,
        "email": f"{email_local}@demo.helpchain.local",
        "city": demo.city,
        "status": demo.status,
        "category": demo.category,
        "structure_id": structure_id,
        "owner_id": owner_id,
        "user_id": requester_id,
        "created_at": created_at,
        "completed_at": completed_at,
    }

    if row is None:
        row = Request(**payload)
        db.session.add(row)
        summary["requests_created"] += 1
        return

    summary["requests_found"] += 1
    for key, value in payload.items():
        setattr(row, key, value)


def print_summary(summary: dict[str, int], structure: Structure) -> None:
    print(
        f"structure: {'created' if summary['structure_created'] else 'found'} "
        f"(id={structure.id}, slug={structure.slug}, name={structure.name})"
    )
    print(
        "admin users: "
        f"created={summary['admin_created']} "
        f"found={summary['admin_found']}"
    )
    print(
        "requester: "
        f"created={summary['requester_created']} "
        f"found={summary['requester_found']}"
    )
    print(
        "requests: "
        f"created={summary['requests_created']} "
        f"found={summary['requests_found']}"
    )


def main() -> int:
    summary = {
        "structure_created": 0,
        "structure_found": 0,
        "admin_created": 0,
        "admin_found": 0,
        "requester_created": 0,
        "requester_found": 0,
        "requests_created": 0,
        "requests_found": 0,
    }

    app = create_app()
    with app.app_context():
        try:
            structure = ensure_structure(summary)
            db.session.flush()

            superadmin = ensure_admin_user(
                username="admin",
                email="admin@helpchain.local",
                role="superadmin",
                structure_id=None,
                summary=summary,
                summary_key_created="admin_created",
                summary_key_found="admin_found",
            )
            ops = ensure_admin_user(
                username="agent_intake",
                email="agent.intake@helpchain.local",
                role="ops",
                structure_id=structure.id,
                summary=summary,
                summary_key_created="admin_created",
                summary_key_found="admin_found",
            )
            requester = ensure_requester_user(structure.id, summary)

            owner_lookup = {
                superadmin.username: superadmin.id,
                ops.username: ops.id,
            }

            for demo in DEMO_REQUESTS:
                ensure_demo_request(
                    demo,
                    structure_id=structure.id,
                    requester_id=requester.id,
                    owner_lookup=owner_lookup,
                    summary=summary,
                )

            db.session.commit()
            print_summary(summary, structure)
            return 0
        except Exception:
            db.session.rollback()
            raise


if __name__ == "__main__":
    raise SystemExit(main())
