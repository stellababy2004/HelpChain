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
from backend.models import (
    AdminAuditEvent,
    AdminUser,
    Request,
    RequestActivity,
    RequestLog,
    Structure,
    User,
)


DEMO_SOURCE = "demo_boulogne_institutional_v1"
DEMO_STRUCTURE_SLUG = "ccas-boulogne-demo"
DEMO_STRUCTURE_NAME = "CCAS Boulogne-Billancourt Demo"
BOULOGNE_CITY = "Boulogne-Billancourt"
BOULOGNE_LAT = 48.8397
BOULOGNE_LNG = 2.2399
DEFAULT_PASSWORD = "HelpChainDemo1"


@dataclass(frozen=True)
class DemoRequest:
    key: str
    title: str
    category: str
    urgency: str
    status: str
    description: str
    days_ago: int
    hours_offset: int
    risk_score: int | None
    owner_username: str | None
    note: str
    previous_status: str | None = None


DEMO_REQUESTS = [
    DemoRequest(
        key="elderly-risk",
        title="Personne agee isolee sans visite de suivi",
        category="elderly_support",
        urgency="high",
        status="in_progress",
        description="Signalement concernant une personne agee vivant seule, sans passage recent du service habituel, avec fragilite observee par le voisinage.",
        days_ago=2,
        hours_offset=3,
        risk_score=92,
        owner_username="agent_coordination",
        note="Visite de verification programmee avec le service social de secteur.",
        previous_status="open",
    ),
    DemoRequest(
        key="food-assistance",
        title="Aide alimentaire pour foyer en rupture de ressources",
        category="food_assistance",
        urgency="medium",
        status="in_progress",
        description="Demande de soutien alimentaire pour un foyer avec enfants, sans ressources disponibles pour la semaine en cours.",
        days_ago=3,
        hours_offset=1,
        risk_score=64,
        owner_username="agent_orientation",
        note="Orientation confirmee vers le partenaire local de distribution alimentaire.",
        previous_status="open",
    ),
    DemoRequest(
        key="mental-health",
        title="Suivi de sante mentale apres rupture de contact",
        category="mental_health",
        urgency="medium",
        status="open",
        description="Situation signalee pour une personne isolee ayant interrompu son suivi et necessitant une reprise de contact coordonnee.",
        days_ago=1,
        hours_offset=5,
        risk_score=58,
        owner_username=None,
        note="Evaluation initiale recueillie, en attente de qualification complementaire.",
        previous_status=None,
    ),
    DemoRequest(
        key="admin-help",
        title="Accompagnement administratif pour ouverture de droits",
        category="administrative_help",
        urgency="low",
        status="open",
        description="Besoin d'accompagnement pour des demarches d'ouverture de droits et de regularisation de dossier administratif.",
        days_ago=4,
        hours_offset=2,
        risk_score=None,
        owner_username=None,
        note="Pieces manquantes identifiees pour un rendez-vous d'accompagnement.",
        previous_status=None,
    ),
    DemoRequest(
        key="housing-emergency",
        title="Mise a l'abri en urgence apres perte d'hebergement",
        category="housing_emergency",
        urgency="high",
        status="done",
        description="Demande urgente de mise a l'abri pour une personne sans solution d'hebergement a l'issue d'une sortie de structure temporaire.",
        days_ago=6,
        hours_offset=4,
        risk_score=87,
        owner_username="agent_coordination",
        note="Solution de mise a l'abri confirmee et relais transmis pour la suite de l'accompagnement.",
        previous_status="in_progress",
    ),
]


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def ensure_structure(summary: dict[str, int]) -> Structure:
    structure = Structure.query.filter_by(slug=DEMO_STRUCTURE_SLUG).first()
    if structure is None:
        structure = Structure(
            name=DEMO_STRUCTURE_NAME,
            slug=DEMO_STRUCTURE_SLUG,
            status="active",
        )
        db.session.add(structure)
        db.session.flush()
        summary["structures_created"] += 1
    else:
        structure.name = DEMO_STRUCTURE_NAME
        structure.status = "active"
        summary["structures_found"] += 1
    return structure


def ensure_requester(structure_id: int, summary: dict[str, int]) -> User:
    user = User.query.filter_by(email="demo.requester.boulogne@helpchain.local").first()
    if user is None:
        user = User(
            username="demo_requester_boulogne",
            email="demo.requester.boulogne@helpchain.local",
            role="requester",
            structure_id=structure_id,
            is_active=True,
        )
        user.set_password(DEFAULT_PASSWORD)
        db.session.add(user)
        db.session.flush()
        summary["requesters_created"] += 1
    else:
        user.username = "demo_requester_boulogne"
        user.role = "requester"
        user.structure_id = structure_id
        user.is_active = True
        summary["requesters_found"] += 1
    return user


def ensure_agent(
    *,
    username: str,
    email: str,
    structure_id: int,
    summary: dict[str, int],
) -> AdminUser:
    agent = AdminUser.query.filter(
        (AdminUser.username == username) | (AdminUser.email == email)
    ).first()
    if agent is None:
        agent = AdminUser(
            username=username,
            email=email,
            role="ops",
            structure_id=structure_id,
            is_active=True,
        )
        agent.set_password(DEFAULT_PASSWORD)
        db.session.add(agent)
        db.session.flush()
        summary["agents_created"] += 1
    else:
        agent.username = username
        agent.email = email
        agent.role = "ops"
        agent.structure_id = structure_id
        agent.is_active = True
        summary["agents_found"] += 1
    return agent


def reset_demo_audit_rows(summary: dict[str, int]) -> None:
    deleted = (
        db.session.query(AdminAuditEvent)
        .filter(AdminAuditEvent.user_agent == DEMO_SOURCE)
        .delete(synchronize_session=False)
    )
    summary["admin_audit_deleted"] += int(deleted or 0)


def upsert_request(
    demo: DemoRequest,
    *,
    structure_id: int,
    requester_id: int,
    agents_by_username: dict[str, AdminUser],
    summary: dict[str, int],
) -> Request:
    request_row = (
        Request.query.filter_by(
            source_channel=DEMO_SOURCE,
            city=BOULOGNE_CITY,
            title=demo.title,
            structure_id=structure_id,
        )
        .order_by(Request.id.asc())
        .first()
    )

    created_at = utc_now_naive() - timedelta(days=demo.days_ago, hours=demo.hours_offset)
    owner = agents_by_username.get(demo.owner_username) if demo.owner_username else None
    completed_at = created_at + timedelta(days=1, hours=2) if demo.status == "done" else None

    payload = {
        "title": demo.title,
        "description": demo.description,
        "name": "Accueil demo Boulogne-Billancourt",
        "email": "accueil.demo.boulogne@helpchain.local",
        "phone": "+33 1 46 00 00 00",
        "city": BOULOGNE_CITY,
        "region": "Ile-de-France",
        "location_text": "Boulogne-Billancourt, France",
        "address_line": "Boulogne-Billancourt",
        "postcode": "92100",
        "country": "France",
        "normalized_address": "Boulogne-Billancourt, 92100, France",
        "geocoding_status": "complete",
        "message": demo.description,
        "status": demo.status,
        "priority": demo.urgency,
        "category": demo.category,
        "source_channel": DEMO_SOURCE,
        "completed_at": completed_at,
        "created_at": created_at,
        "updated_at": created_at + timedelta(hours=6),
        "latitude": BOULOGNE_LAT,
        "longitude": BOULOGNE_LNG,
        "structure_id": structure_id,
        "user_id": requester_id,
        "owner_id": owner.id if owner else None,
        "owned_at": created_at + timedelta(hours=1) if owner else None,
        "risk_score": demo.risk_score or 0,
    }

    if request_row is None:
        request_row = Request(**payload)
        db.session.add(request_row)
        db.session.flush()
        summary["requests_created"] += 1
    else:
        for key, value in payload.items():
            setattr(request_row, key, value)
        summary["requests_updated"] += 1

    # Keep demo activity deterministic across reruns.
    RequestLog.query.filter_by(request_id=request_row.id).delete(synchronize_session=False)
    RequestActivity.query.filter_by(request_id=request_row.id).delete(synchronize_session=False)

    create_request_history(request_row, demo, owner)
    create_admin_audit_rows(request_row, demo, owner)
    return request_row


def create_request_history(request_row: Request, demo: DemoRequest, owner: AdminUser | None) -> None:
    base_time = request_row.created_at

    db.session.add(
        RequestLog(
            request_id=request_row.id,
            action="note_added",
            timestamp=base_time + timedelta(minutes=20),
        )
    )
    db.session.add(
        RequestActivity(
            request_id=request_row.id,
            actor_admin_id=owner.id if owner else None,
            action="note_added",
            old_value=None,
            new_value=demo.note,
            created_at=base_time + timedelta(minutes=20),
        )
    )

    if owner is not None:
        db.session.add(
            RequestLog(
                request_id=request_row.id,
                action="assignment",
                timestamp=base_time + timedelta(hours=1),
            )
        )
        db.session.add(
            RequestActivity(
                request_id=request_row.id,
                actor_admin_id=owner.id,
                action="assignment",
                old_value=None,
                new_value=owner.username,
                created_at=base_time + timedelta(hours=1),
            )
        )

    if demo.previous_status:
        actor_id = owner.id if owner else None
        db.session.add(
            RequestLog(
                request_id=request_row.id,
                action="status_change",
                timestamp=base_time + timedelta(hours=2),
            )
        )
        db.session.add(
            RequestActivity(
                request_id=request_row.id,
                actor_admin_id=actor_id,
                action="status_change",
                old_value=demo.previous_status,
                new_value=demo.status,
                created_at=base_time + timedelta(hours=2),
            )
        )


def create_admin_audit_rows(request_row: Request, demo: DemoRequest, owner: AdminUser | None) -> None:
    if owner is not None:
        db.session.add(
            AdminAuditEvent(
                created_at=request_row.created_at + timedelta(hours=1),
                admin_user_id=owner.id,
                admin_username=owner.username,
                action="request.assign_owner",
                target_type="request",
                target_id=request_row.id,
                user_agent=DEMO_SOURCE,
                payload={"owner": owner.username, "title": request_row.title},
            )
        )

    if demo.previous_status:
        actor = owner
        db.session.add(
            AdminAuditEvent(
                created_at=request_row.created_at + timedelta(hours=2),
                admin_user_id=actor.id if actor else None,
                admin_username=actor.username if actor else None,
                action="request.status_change",
                target_type="request",
                target_id=request_row.id,
                user_agent=DEMO_SOURCE,
                payload={
                    "old_status": demo.previous_status,
                    "new_status": demo.status,
                    "title": request_row.title,
                },
            )
        )


def print_summary(summary: dict[str, int]) -> None:
    print("HelpChain Boulogne-Billancourt demo dataset")
    print(f"structures: created={summary['structures_created']} found={summary['structures_found']}")
    print(f"agents: created={summary['agents_created']} found={summary['agents_found']}")
    print(f"requesters: created={summary['requesters_created']} found={summary['requesters_found']}")
    print(f"requests: created={summary['requests_created']} updated={summary['requests_updated']}")
    print(f"admin audit rows reset={summary['admin_audit_deleted']}")


def main() -> int:
    summary = {
        "structures_created": 0,
        "structures_found": 0,
        "agents_created": 0,
        "agents_found": 0,
        "requesters_created": 0,
        "requesters_found": 0,
        "requests_created": 0,
        "requests_updated": 0,
        "admin_audit_deleted": 0,
    }

    app = create_app()
    with app.app_context():
        try:
            structure = ensure_structure(summary)
            requester = ensure_requester(structure.id, summary)
            agent_coordination = ensure_agent(
                username="agent_coordination",
                email="agent.coordination@helpchain.local",
                structure_id=structure.id,
                summary=summary,
            )
            agent_orientation = ensure_agent(
                username="agent_orientation",
                email="agent.orientation@helpchain.local",
                structure_id=structure.id,
                summary=summary,
            )

            reset_demo_audit_rows(summary)

            agents_by_username = {
                agent_coordination.username: agent_coordination,
                agent_orientation.username: agent_orientation,
            }

            for demo in DEMO_REQUESTS:
                upsert_request(
                    demo,
                    structure_id=structure.id,
                    requester_id=requester.id,
                    agents_by_username=agents_by_username,
                    summary=summary,
                )

            db.session.commit()
            print_summary(summary)
            return 0
        except Exception:
            db.session.rollback()
            raise


if __name__ == "__main__":
    raise SystemExit(main())
