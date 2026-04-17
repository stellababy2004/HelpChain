#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import inspect as sa_inspect


def _prepare_import_path() -> None:
    this_file = Path(__file__).resolve()
    backend_dir = this_file.parents[1]
    repo_root = backend_dir.parent
    for p in (str(repo_root), str(backend_dir)):
        if p not in sys.path:
            sys.path.insert(0, p)


_prepare_import_path()

from backend.appy import app
from backend.extensions import db
from backend.helpchain_backend.src.models import Case, CaseEvent, CaseParticipant, ProfessionalLead
from backend.models import (
    AdminAuditEvent,
    AdminLoginAttempt,
    AdminUser,
    Intervenant,
    NotificationJob,
    Request,
    RequestActivity,
    Structure,
    User,
)


DEMO_MARKER = "Demo Boulogne"
DEMO_SECURITY_TAG = "seed-admin-operational-demo"
NOW = datetime.now(UTC)
DEMO_INTERVENANT_COORDS = {
    "15 Rue de Billancourt": (48.83291, 2.23928),
    "12 Rue Nationale": (48.83582, 2.23864),
    "26 Avenue Victor Hugo": (48.84244, 2.23618),
    "3 Rue Anna Jacquin": (48.83863, 2.24782),
    "48 Rue de Paris": (48.84162, 2.23193),
    "22 Rue de la Saussière": (48.83954, 2.24701),
    "9 Rue Paul Bert": (48.84398, 2.23484),
    "81 Boulevard de la République": (48.83539, 2.24176),
    "19 Rue de Bellevue": (48.84662, 2.22918),
    "2 Rue des Menus": (48.83996, 2.23574),
    "67 Rue Thiers": (48.84341, 2.24103),
    "21 Rue de Meudon": (48.82794, 2.24058),
    "5 Rue des 4 Cheminées": (48.83684, 2.24653),
    "28 Rue de Clamart": (48.82861, 2.24744),
    "22 Rue de la Saussiere": (48.83954, 2.24701),
    "81 Boulevard de la Republique": (48.83539, 2.24176),
    "5 Rue des 4 Cheminees": (48.83684, 2.24653),
    "11 Rue de Solferino": (48.83279, 2.23821),
    "74 Rue du Vieux Pont de Sevres": (48.82942, 2.22988),
    "6 Rue Ernest Renan": (48.82342, 2.27267),
    "14 Avenue de Verdun": (48.82454, 2.27461),
    "18 Rue de l'Abbe Groult": (48.83982, 2.29634),
    "27 Rue de la Convention": (48.84617, 2.28661),
    "31 Rue de Silly": (48.83594, 2.24715),
    "45 Rue du Point du Jour": (48.83421, 2.25793),
}


def _mask_db_url(uri: str) -> str:
    return re.sub(r"://([^:@/]+):([^@/]+)@", r"://\1:***@", uri)


def _demo_signal_text(*signals: str) -> str:
    vals = [s for s in signals if s]
    return json.dumps(vals, ensure_ascii=False)


@dataclass(frozen=True)
class RequestSeed:
    key: str
    title: str
    description: str
    structure_slug: str
    category: str
    status: str
    priority: str
    risk_level: str
    risk_score: int
    owner_username: str | None
    requester_username: str
    address: str
    created_hours_ago: int
    updated_hours_ago: int
    activity_hours_ago: list[int]
    signals: tuple[str, ...]


@dataclass(frozen=True)
class CaseSeed:
    request_key: str
    status: str
    priority: str
    risk_score: int
    owner_username: str | None
    lead_email: str | None
    created_hours_ago: int
    last_activity_hours_ago: int
    events: tuple[tuple[str, str, int, str], ...]
    participants: tuple[tuple[str, str, str | None, str | None, str | None], ...]


def _runtime_uri() -> str:
    return str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")


def _is_production_env() -> bool:
    markers = [
        os.getenv("HC_ENV", ""),
        os.getenv("FLASK_ENV", ""),
        os.getenv("APP_ENV", ""),
        os.getenv("ENV", ""),
        str(app.config.get("ENV", "") or ""),
        str(app.config.get("APP_ENV", "") or ""),
    ]
    normalized = [m.strip().lower() for m in markers if m]
    return any(m in {"prod", "production"} for m in normalized)


def _is_demo_seed_allowed() -> bool:
    return (os.getenv("HC_ALLOW_DEMO_SEED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _sqlite_path_from_uri(uri: str) -> Path | None:
    norm = (uri or "").strip().replace("\\", "/")
    if not norm.lower().startswith("sqlite:"):
        return None
    raw_path = norm.replace("sqlite:///", "", 1).replace("sqlite://", "", 1)
    if not raw_path:
        return None
    path = Path(raw_path)
    if path.is_absolute():
        return path.resolve()
    return (Path(__file__).resolve().parents[2] / path).resolve()


def _bump(summary: dict[str, int], key: str, amount: int = 1) -> None:
    summary[key] = int(summary.get(key, 0) or 0) + int(amount)


def _table_available(model: type[object]) -> bool:
    try:
        bind = db.session.get_bind()
        if bind is None:
            return False
        return bool(sa_inspect(bind).has_table(model.__tablename__))
    except Exception:
        return False


def _ensure_demo_branch() -> str:
    uri = _runtime_uri().strip()
    norm = uri.lower()
    force_demo = _is_demo_seed_allowed()
    if not uri:
        raise RuntimeError("Refusing demo seed: runtime DB URL is empty.")
    if _is_production_env():
        raise RuntimeError("Refusing demo seed: production-like environment detected.")
    if not force_demo:
        raise RuntimeError(
            "Refusing demo seed: set HC_ALLOW_DEMO_SEED=1 to confirm local demo execution."
        )
    if norm.startswith("sqlite:"):
        sqlite_path = _sqlite_path_from_uri(uri)
        repo_root = Path(__file__).resolve().parents[2]
        if sqlite_path is None or repo_root not in sqlite_path.parents:
            raise RuntimeError(
                "Refusing demo seed: sqlite target must stay inside the local repo runtime. "
                f"Actual={_mask_db_url(uri)}"
            )
        return uri
    if "-pooler" in norm:
        raise RuntimeError(
            f"Refusing demo seed: pooled Neon URL is not allowed. Actual={_mask_db_url(uri)}"
        )
    if not norm.startswith(("postgresql://", "postgresql+psycopg://")):
        raise RuntimeError(
            "Refusing demo seed: unsupported DB URL for demo execution. "
            f"Actual={_mask_db_url(uri)}"
        )
    return uri


def _get_or_create_structure(
    name: str, slug: str, *, status: str = "active", summary: dict[str, int] | None = None
) -> Structure:
    row = Structure.query.filter_by(slug=slug).first()
    if row is None:
        row = Structure(name=name, slug=slug, status=status)
        db.session.add(row)
        if summary is not None:
            _bump(summary, "structures_created")
    else:
        row.name = name
        row.status = status
        if summary is not None:
            _bump(summary, "structures_reused")
    return row


def _set_password_if_needed(user: AdminUser | User, password: str) -> None:
    try:
        if not getattr(user, "password_hash", None):
            user.set_password(password)
    except Exception:
        pass


def _get_or_create_admin(
    *,
    username: str,
    email: str,
    role: str,
    structure_id: int | None,
    password: str = "DemoBoulogne123!",
    summary: dict[str, int] | None = None,
) -> AdminUser:
    row = AdminUser.query.filter_by(username=username).first()
    created = row is None
    if row is None:
        row = AdminUser(username=username, email=email, role=role, is_active=True)
        _set_password_if_needed(row, password)
        db.session.add(row)
    row.email = email
    row.role = role
    row.is_active = True
    row.structure_id = structure_id
    if not getattr(row, "password_hash", None):
        _set_password_if_needed(row, password)
    if summary is not None:
        _bump(summary, "admins_created" if created else "admins_reused")
    return row


def _get_or_create_user(
    *,
    username: str,
    email: str,
    structure_id: int | None,
    role: str = "requester",
    password: str = "DemoBoulogne123!",
    summary: dict[str, int] | None = None,
) -> User:
    row = User.query.filter_by(username=username).first()
    created = row is None
    if row is None:
        row = User(username=username, email=email, role=role, is_active=True)
        _set_password_if_needed(row, password)
        db.session.add(row)
    row.email = email
    row.role = role
    row.is_active = True
    row.structure_id = structure_id
    if not getattr(row, "password_hash", None):
        _set_password_if_needed(row, password)
    if summary is not None:
        _bump(summary, "users_created" if created else "users_reused")
    return row


def _join_location(city: str, address: str) -> str:
    return f"{city} || {address}"


def _get_or_create_intervenant(
    *,
    structure_id: int,
    full_name: str,
    email: str,
    phone: str,
    profession: str,
    address: str,
    city: str = "Boulogne-Billancourt",
    is_active: bool = True,
    created_hours_ago: int = 96,
    summary: dict[str, int] | None = None,
) -> Intervenant:
    row = Intervenant.query.filter_by(email=email).first()
    created = row is None
    if row is None:
        row = Intervenant(structure_id=structure_id)
        db.session.add(row)
    row.structure_id = structure_id
    row.name = full_name
    row.email = email
    row.phone = phone
    row.actor_type = profession
    row.location = _join_location(city, address)
    coords = DEMO_INTERVENANT_COORDS.get(address)
    if coords:
        row.latitude = float(coords[0])
        row.longitude = float(coords[1])
    row.is_active = is_active
    row.created_at = NOW - timedelta(hours=created_hours_ago)
    if summary is not None:
        _bump(summary, "intervenants_created" if created else "intervenants_reused")
    return row


def _get_or_create_professional_lead(
    *,
    owner_admin_id: int | None,
    full_name: str,
    email: str,
    phone: str,
    profession: str,
    organization: str,
    availability: str,
    address: str,
    city: str = "Boulogne-Billancourt",
    status: str = "new",
    created_hours_ago: int = 24,
    touched_hours_ago: int = 4,
    contacted_hours_ago: int | None = None,
    first_followup_hours_ago: int | None = None,
    second_followup_hours_ago: int | None = None,
    notes: str | None = None,
    summary: dict[str, int] | None = None,
) -> ProfessionalLead:
    row = ProfessionalLead.query.filter_by(email=email).first()
    created = row is None
    if row is None:
        row = ProfessionalLead(email=email, profession=profession)
        db.session.add(row)
    row.full_name = full_name
    row.phone = phone
    row.city = city
    row.profession = profession
    row.organization = organization
    row.availability = availability
    row.message = f"{DEMO_MARKER} | {address}, {city}"
    row.source = "demo_page"
    row.locale = "fr"
    row.owner_admin_id = owner_admin_id
    row.status = status
    row.notes = notes or f"{DEMO_MARKER} | adresse: {address}"
    row.created_at = NOW - timedelta(hours=created_hours_ago)
    row.contacted_at = (
        NOW - timedelta(hours=contacted_hours_ago)
        if contacted_hours_ago is not None
        else None
    )
    row.first_followup_sent_at = (
        NOW - timedelta(hours=first_followup_hours_ago)
        if first_followup_hours_ago is not None
        else None
    )
    row.second_followup_sent_at = (
        NOW - timedelta(hours=second_followup_hours_ago)
        if second_followup_hours_ago is not None
        else None
    )
    row.last_touched_at = NOW - timedelta(hours=touched_hours_ago)
    row.last_touched_by_admin_id = owner_admin_id
    if summary is not None:
        _bump(summary, "leads_created" if created else "leads_reused")
    return row


def _upsert_request(
    seed: RequestSeed,
    *,
    structures: dict[str, Structure],
    admins: dict[str, AdminUser],
    users: dict[str, User],
    summary: dict[str, int] | None = None,
) -> Request:
    row = Request.query.filter_by(title=seed.title).first()
    created = row is None
    if row is None:
        row = Request(title=seed.title, user_id=users[seed.requester_username].id)
        db.session.add(row)
    created_at = NOW - timedelta(hours=seed.created_hours_ago)
    updated_at = NOW - timedelta(hours=seed.updated_hours_ago)
    row.title = seed.title
    row.description = seed.description
    row.message = seed.description
    row.name = f"{DEMO_MARKER} - demandeur"
    row.email = users[seed.requester_username].email
    row.phone = "+33 1 84 60 92 00"
    row.city = "Boulogne-Billancourt"
    row.region = "Ile-de-France"
    row.address_line = seed.address
    row.postcode = "92100"
    row.country = "France"
    row.location_text = f"{seed.address}, 92100 Boulogne-Billancourt, France"
    row.normalized_address = row.location_text
    row.geocoding_status = "needs_review"
    row.status = seed.status
    row.priority = seed.priority
    row.category = seed.category
    row.structure_id = structures[seed.structure_slug].id
    row.user_id = users[seed.requester_username].id
    row.owner_id = admins[seed.owner_username].id if seed.owner_username else None
    row.owned_at = updated_at if seed.owner_username else None
    row.risk_level = seed.risk_level
    row.risk_score = seed.risk_score
    row.risk_signals = _demo_signal_text(*seed.signals)
    row.risk_last_updated = updated_at
    row.created_at = created_at
    row.updated_at = updated_at
    row.is_archived = False
    row.deleted_at = None
    if summary is not None:
        _bump(summary, "requests_created" if created else "requests_reused")
    return row


def _upsert_request_activity(
    request_id: int,
    *,
    actor_admin_id: int | None,
    action: str,
    text: str,
    created_at: datetime,
) -> None:
    row = (
        RequestActivity.query.filter_by(
            request_id=request_id,
            action=action,
            actor_admin_id=actor_admin_id,
            new_value=text,
        )
        .first()
    )
    if row is None:
        row = RequestActivity(
            request_id=request_id,
            actor_admin_id=actor_admin_id,
            action=action,
            new_value=text,
            created_at=created_at,
        )
        db.session.add(row)
    else:
        row.created_at = created_at


def _upsert_case(
    seed: CaseSeed,
    *,
    requests_map: dict[str, Request],
    admins: dict[str, AdminUser],
    leads: dict[str, ProfessionalLead],
) -> Case:
    req = requests_map[seed.request_key]
    row = Case.query.filter_by(request_id=req.id).first()
    if row is None:
        row = Case(request_id=req.id)
        db.session.add(row)
    created_at = NOW - timedelta(hours=seed.created_hours_ago)
    last_activity_at = NOW - timedelta(hours=seed.last_activity_hours_ago)
    row.request_id = req.id
    row.structure_id = req.structure_id
    row.owner_user_id = admins[seed.owner_username].id if seed.owner_username else None
    row.assigned_professional_lead_id = leads[seed.lead_email].id if seed.lead_email else None
    row.status = seed.status
    row.priority = seed.priority
    row.risk_score = seed.risk_score
    row.latitude = req.latitude
    row.longitude = req.longitude
    row.created_at = created_at
    row.updated_at = last_activity_at
    row.last_activity_at = last_activity_at
    row.opened_at = created_at
    row.assigned_at = created_at + timedelta(hours=6) if seed.status in {"assigned", "in_progress", "resolved", "closed"} or seed.owner_username else None
    row.resolved_at = last_activity_at if seed.status in {"resolved", "closed"} else None
    row.closed_at = last_activity_at if seed.status in {"closed", "cancelled"} else None
    return row


def _upsert_case_event(case_id: int, actor_user_id: int | None, event_type: str, message: str, visibility: str, created_at: datetime) -> None:
    row = (
        CaseEvent.query.filter_by(
            case_id=case_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            message=message,
        )
        .first()
    )
    if row is None:
        row = CaseEvent(
            case_id=case_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            message=message,
            visibility=visibility,
            created_at=created_at,
        )
        db.session.add(row)
    else:
        row.visibility = visibility
        row.created_at = created_at


def _upsert_case_participant(
    case_id: int,
    *,
    participant_type: str,
    role: str,
    user_id: int | None = None,
    professional_lead_id: int | None = None,
    external_name: str | None = None,
) -> None:
    query = CaseParticipant.query.filter_by(case_id=case_id, participant_type=participant_type, role=role)
    if user_id is not None:
        query = query.filter(CaseParticipant.user_id == user_id)
    elif professional_lead_id is not None:
        query = query.filter(CaseParticipant.professional_lead_id == professional_lead_id)
    else:
        query = query.filter(CaseParticipant.external_name == external_name)
    row = query.first()
    if row is None:
        row = CaseParticipant(
            case_id=case_id,
            participant_type=participant_type,
            role=role,
            user_id=user_id,
            professional_lead_id=professional_lead_id,
            external_name=external_name,
            status="active",
            added_at=NOW,
        )
        db.session.add(row)
    else:
        row.status = "active"
        row.added_at = NOW


def _upsert_notification_job(
    *,
    structure_id: int | None,
    channel: str,
    event_type: str,
    recipient: str,
    subject: str,
    status: str,
    attempts: int,
    max_attempts: int,
    created_hours_ago: int,
    next_retry_hours_from_now: int | None = None,
    summary: dict[str, int] | None = None,
) -> None:
    row = NotificationJob.query.filter_by(subject=subject, recipient=recipient).first()
    created_at = NOW - timedelta(hours=created_hours_ago)
    created = row is None
    if row is None:
        row = NotificationJob(channel=channel, event_type=event_type, recipient=recipient, subject=subject)
        db.session.add(row)
    row.structure_id = structure_id
    row.channel = channel
    row.event_type = event_type
    row.recipient = recipient
    row.subject = subject
    row.payload_json = json.dumps({"marker": DEMO_MARKER}, ensure_ascii=False)
    row.status = status
    row.attempts = attempts
    row.max_attempts = max_attempts
    row.created_at = created_at
    row.updated_at = created_at
    row.next_retry_at = NOW + timedelta(hours=next_retry_hours_from_now) if next_retry_hours_from_now is not None else None
    row.sent_at = created_at if status in {"done", "sent"} else None
    row.processed_at = created_at if status in {"done", "sent", "dead_letter", "failed"} else None
    row.last_error = "Relance API SMTP en attente" if status in {"retry", "dead_letter", "failed"} else None
    if summary is not None:
        _bump(summary, "notifications_created" if created else "notifications_reused")


def _security_user_agent() -> str:
    return f"{DEMO_SECURITY_TAG}/v1"


def _reset_security_demo_rows(summary: dict[str, int]) -> None:
    ua = _security_user_agent()
    login_deleted = (
        db.session.query(AdminLoginAttempt)
        .filter(AdminLoginAttempt.user_agent == ua)
        .delete(synchronize_session=False)
    )
    audit_deleted = (
        db.session.query(AdminAuditEvent)
        .filter(AdminAuditEvent.user_agent == ua)
        .delete(synchronize_session=False)
    )
    _bump(summary, "security_signals_reused", int((login_deleted or 0) + (audit_deleted or 0)))


def _seed_security_events(
    *,
    summary: dict[str, int],
    admin_user: AdminUser,
    ops_admin: AdminUser,
    request_targets: dict[str, Request],
) -> None:
    ua = _security_user_agent()
    now = datetime.now(UTC)
    login_events = [
        AdminLoginAttempt(
            created_at=now - timedelta(minutes=46),
            username=admin_user.username,
            ip="127.0.0.1",
            success=True,
            user_agent=ua,
        ),
        AdminLoginAttempt(
            created_at=now - timedelta(minutes=41),
            username="admin",
            ip="185.143.221.14",
            success=False,
            user_agent=ua,
        ),
        AdminLoginAttempt(
            created_at=now - timedelta(minutes=39),
            username="admin",
            ip="185.143.221.14",
            success=False,
            user_agent=ua,
        ),
        AdminLoginAttempt(
            created_at=now - timedelta(minutes=36),
            username="readonly.demo",
            ip="185.143.221.14",
            success=False,
            user_agent=ua,
        ),
        AdminLoginAttempt(
            created_at=now - timedelta(minutes=30),
            username=ops_admin.username,
            ip="10.0.12.24",
            success=True,
            user_agent=ua,
        ),
        AdminLoginAttempt(
            created_at=now - timedelta(minutes=22),
            username="ops.boulogne.demo",
            ip="78.245.16.91",
            success=False,
            user_agent=ua,
        ),
        AdminLoginAttempt(
            created_at=now - timedelta(minutes=14),
            username=admin_user.username,
            ip="127.0.0.1",
            success=True,
            user_agent=ua,
        ),
        AdminLoginAttempt(
            created_at=now - timedelta(minutes=6),
            username=ops_admin.username,
            ip="127.0.0.1",
            success=True,
            user_agent=ua,
        ),
    ]
    db.session.add_all(login_events)

    audit_events = [
        AdminAuditEvent(
            created_at=now - timedelta(minutes=28),
            admin_user_id=admin_user.id,
            admin_username=admin_user.username,
            action="request.assign_owner",
            target_type="Request",
            target_id=request_targets["r16"].id,
            ip="127.0.0.1",
            user_agent=ua,
            payload={"marker": DEMO_MARKER, "new": {"owner": admin_user.username}},
        ),
        AdminAuditEvent(
            created_at=now - timedelta(minutes=24),
            admin_user_id=admin_user.id,
            admin_username=admin_user.username,
            action="request.update_status",
            target_type="Request",
            target_id=request_targets["r2"].id,
            ip="127.0.0.1",
            user_agent=ua,
            payload={"marker": DEMO_MARKER, "old": {"status": "open"}, "new": {"status": "in_progress"}},
        ),
        AdminAuditEvent(
            created_at=now - timedelta(minutes=21),
            admin_user_id=ops_admin.id,
            admin_username=ops_admin.username,
            action="security.denied_action",
            target_type="Request",
            target_id=request_targets["r3"].id,
            ip="185.143.221.14",
            user_agent=ua,
            payload={"marker": DEMO_MARKER, "reason": "role_guard"},
        ),
        AdminAuditEvent(
            created_at=now - timedelta(minutes=16),
            admin_user_id=admin_user.id,
            admin_username=admin_user.username,
            action="notification.retry",
            target_type="Request",
            target_id=request_targets["r10"].id,
            ip="127.0.0.1",
            user_agent=ua,
            payload={"marker": DEMO_MARKER, "channel": "email", "status": "retry"},
        ),
        AdminAuditEvent(
            created_at=now - timedelta(minutes=11),
            admin_user_id=ops_admin.id,
            admin_username=ops_admin.username,
            action="interest.approve",
            target_type="Request",
            target_id=request_targets["r11"].id,
            ip="127.0.0.1",
            user_agent=ua,
            payload={"marker": DEMO_MARKER, "source": "operational_demo"},
        ),
        AdminAuditEvent(
            created_at=now - timedelta(minutes=7),
            admin_user_id=admin_user.id,
            admin_username=admin_user.username,
            action="request.escalate",
            target_type="Request",
            target_id=request_targets["r5"].id,
            ip="127.0.0.1",
            user_agent=ua,
            payload={"marker": DEMO_MARKER, "reason": "night_shelter_required"},
        ),
    ]
    db.session.add_all(audit_events)
    _bump(summary, "security_signals_created", len(login_events) + len(audit_events))


def _request_seeds() -> list[RequestSeed]:
    return [
        RequestSeed("r1", "Demo Boulogne - Isolement personne agee sans visite recente", "Signalement d'une personne agee vivant seule, sans visite familiale recente et sans relais de voisinage organise.", "ccas-boulogne-demo", "isolation", "open", "high", "critical", 93, None, "demo.requester.01", "15 Rue de Billancourt", 132, 98, [126], ("no_owner", "not_seen_72h")),
        RequestSeed("r2", "Demo Boulogne - Sortie d'hospitalisation sans relais a domicile", "Retour a domicile apres hospitalisation avec besoin de coordination infirmiere et de suivi social dans les 24 heures.", "reseau-sante-boulogne-demo", "health", "in_progress", "high", "attention", 74, "admin", "demo.requester.02", "32 Route de la Reine", 56, 6, [30, 12, 5], ("owner_assigned",)),
        RequestSeed("r3", "Demo Boulogne - Demande alimentaire urgente pour parent isole", "Parent isole avec deux enfants, absence de denrees pour le week-end et aucune solution familiale immediate.", "association-solidarite-92-demo-boulogne", "food", "new", "critical", "critical", 96, None, "demo.requester.03", "41 Rue du Chateau", 26, 24, [23], ("no_owner",)),
        RequestSeed("r4", "Demo Boulogne - Orientation femme victime de violence", "Besoin d'orientation discrete vers une solution de mise a l'abri et un accompagnement de protection.", "plateforme-protection-familles-92-demo-boulogne", "violence", "open", "critical", "critical", 94, "ops.boulogne.demo", "demo.requester.04", "8 Rue des Abondances", 40, 8, [28, 14, 7], ("followup_required",)),
        RequestSeed("r5", "Demo Boulogne - Hebergement temporaire pour menage sans solution", "Menage avec enfant mineur sans solution pour la nuit, orientation hebergement a activer avant 18h.", "association-solidarite-92-demo-boulogne", "housing", "open", "critical", "critical", 92, None, "demo.requester.05", "63 Avenue Jean-Baptiste Clement", 82, 79, [78], ("no_owner", "not_seen_72h")),
        RequestSeed("r6", "Demo Boulogne - Rupture administrative CAF RSA", "Suspension de droits CAF et RSA faute de pieces, besoin d'un rendez-vous de regularisation et d'un appui documentaire.", "ccas-boulogne-demo", "admin_help", "in_progress", "normal", "attention", 46, "ops.boulogne.demo", "demo.requester.06", "6 Rue Escudier", 76, 14, [48, 13], ("docs_missing",)),
        RequestSeed("r7", "Demo Boulogne - Accompagnement sante mentale apres rupture", "Personne en rupture familiale avec anxiete forte et besoin d'un premier entretien d'orientation medico-sociale.", "cellule-coordination-senior-demo-boulogne", "health", "open", "high", "attention", 69, None, "demo.requester.07", "24 Rue Fessart", 62, 51, [50], ("no_owner",)),
        RequestSeed("r8", "Demo Boulogne - Aide transport medical pour rendez-vous CHU", "Usager a mobilite reduite sans solution de transport pour un rendez-vous hospitalier fixe demain matin.", "ccas-boulogne-demo", "mobility", "in_progress", "normal", "standard", 42, "admin", "demo.requester.08", "52 Boulevard Jean Jaures", 34, 5, [18, 4], ("appointment_pending",)),
        RequestSeed("r9", "Demo Boulogne - Soutien demarches prefecture pour renouvellement titre", "Dossier prefecture incomplet avec echeance proche, besoin d'un accompagnement administratif et de mediation.", "plateforme-protection-familles-92-demo-boulogne", "orientation", "open", "normal", "attention", 55, "ops.boulogne.demo", "demo.requester.09", "14 Rue de Sevres", 96, 74, [90], ("not_seen_72h",)),
        RequestSeed("r10", "Demo Boulogne - Impayes energie avec risque de coupure", "Impayes energie cumules avec avis de coupure recu, besoin d'un traitement rapide et d'un contact fournisseur.", "association-solidarite-92-demo-boulogne", "energy", "open", "high", "critical", 90, None, "demo.requester.10", "11 Rue Gambetta", 88, 82, [81], ("no_owner", "not_seen_72h")),
        RequestSeed("r11", "Demo Boulogne - Coordination retour domicile apres chirurgie", "Coordination entre CCAS, infirmiere liberale et aidant familial apres sortie de chirurgie recente.", "reseau-sante-boulogne-demo", "orientation", "in_progress", "high", "attention", 67, "admin", "demo.requester.11", "17 Avenue Pierre Grenier", 28, 2, [16, 7, 1], ("multi_actor",)),
        RequestSeed("r12", "Demo Boulogne - Dossier administratif sans retour usager", "Usager sans retour apres plusieurs relances sur un dossier de domiciliation et de couverture sante.", "ccas-boulogne-demo", "admin_help", "open", "normal", "attention", 60, "ops.boulogne.demo", "demo.requester.12", "29 Rue du Vieux Pont de Sevres", 104, 93, [92], ("not_seen_72h",)),
        RequestSeed("r13", "Demo Boulogne - Demande alimentaire ponctuelle resolue", "Distribution exceptionnelle confirmee avec remise effective au foyer et verification telephonique.", "association-solidarite-92-demo-boulogne", "food", "done", "normal", "standard", 18, "admin", "demo.requester.13", "4 Rue de l'Ancienne Mairie", 44, 10, [24, 9], ()),
        RequestSeed("r14", "Demo Boulogne - Orientation sociale finalisee", "Orientation vers le service social de secteur finalisee avec rendez-vous honore et relais transmis.", "ccas-boulogne-demo", "orientation", "done", "normal", "standard", 14, "ops.boulogne.demo", "demo.requester.14", "36 Rue Gallieni", 68, 12, [40, 11], ()),
        RequestSeed("r15", "Demo Boulogne - Doublon de saisie hebergement", "Demande en doublon apres rappel telephonique du meme foyer, dossier clos sans suite apres verification.", "association-solidarite-92-demo-boulogne", "housing", "cancelled", "low", "standard", 9, None, "demo.requester.15", "7 Rue de Solferino", 20, 19, [19], ()),
        RequestSeed("r16", "Demo Boulogne - Urgence sociale critique sans responsable", "Situation critique avec rupture immediate de ressources et aucun responsable territorial affecte au dossier.", "ccas-boulogne-demo", "emergency", "new", "critical", "critical", 98, None, "demo.requester.16", "55 Rue d'Aguesseau", 12, 11, [10], ("no_owner",)),
        RequestSeed("r17", "Demo Boulogne - Aidant familial epuise sans relais", "Aidant principal a bout de souffle, besoin d'un relais de proximite et d'une evaluation rapide de la situation.", "cellule-coordination-senior-demo-boulogne", "isolation", "open", "high", "attention", 71, "ops.boulogne.demo", "demo.requester.17", "10 Rue de Bellevue", 50, 18, [24, 17], ("caregiver_alert",)),
        RequestSeed("r18", "Demo Boulogne - Demande de domiciliation administrative", "Personne sans adresse stable ayant besoin d'une domiciliation administrative pour relancer ses droits.", "plateforme-protection-familles-92-demo-boulogne", "admin_help", "new", "normal", "standard", 38, None, "demo.requester.18", "6 Rue Marcel Dassault", 16, 15, [15], ("no_owner",)),
        RequestSeed("r19", "Demo Boulogne - Mediation bailleur pour maintien logement", "Mediation a engager avec le bailleur social apres impayes et tensions avec le voisinage.", "plateforme-protection-familles-92-demo-boulogne", "housing", "in_progress", "high", "attention", 64, "admin", "demo.requester.19", "42 Rue de Paris", 64, 7, [26, 6], ("landlord_contact",)),
        RequestSeed("r20", "Demo Boulogne - Rupture de droits CPAM", "Droits CPAM suspendus apres changement de situation, risque de renoncement aux soins sans accompagnement.", "reseau-sante-boulogne-demo", "health", "open", "high", "attention", 73, None, "demo.requester.20", "13 Rue de Meudon", 72, 66, [65], ("no_owner", "not_seen_72h")),
        RequestSeed("r21", "Demo Boulogne - Accompagnement enfant en situation de handicap", "Famille en attente de relais MDPH et d'un point de coordination avec l'ecole et le centre social.", "cellule-coordination-senior-demo-boulogne", "family", "in_progress", "high", "attention", 63, "ops.boulogne.demo", "demo.requester.21", "18 Avenue Andre Morizet", 46, 4, [20, 8, 3], ("multi_actor",)),
        RequestSeed("r22", "Demo Boulogne - Besoin de courses solidaires ponctuel", "Personne agee avec immobilisation temporaire, appui de proximite organise puis cloture apres confirmation.", "reseau-sante-boulogne-demo", "daily_life", "done", "low", "standard", 12, "admin", "demo.requester.22", "2 Rue de Silly", 36, 9, [18, 8], ()),
    ]


def _case_seeds() -> list[CaseSeed]:
    return [
        CaseSeed("r16", "new", "critical", 97, None, None, 12, 11, (("case_created", "Demande placee en file critique.", 11, "internal"), ("triage_scored", "Risque critique confirme par l'equipe de permanence.", 10, "internal")), ()),
        CaseSeed("r3", "new", "critical", 92, None, None, 26, 23, (("case_created", "Signalement alimentaire enregistre.", 24, "internal"), ("note_added", "Besoin de colis alimentaire sous 24h.", 23, "internal")), ()),
        CaseSeed("r1", "triaged", "high", 84, None, "claire.martin.lead@boulogne.demo", 132, 94, (("case_created", "Dossier senior cree.", 126, "internal"), ("triage_scored", "Situation agee isolee qualifiee en vigilance.", 110, "internal"), ("note_added", "Absence de visite depuis plusieurs jours.", 94, "internal")), (("professional_lead", "primary_professional", None, "claire.martin.lead@boulogne.demo", None),)),
        CaseSeed("r7", "triaged", "high", 73, None, "dr.sarah.cohen.demo@boulogne.demo", 62, 49, (("case_created", "Dossier sante mentale ouvert.", 58, "internal"), ("triage_scored", "Premier niveau d'orientation retenu.", 50, "internal")), (("professional_lead", "primary_professional", None, "dr.sarah.cohen.demo@boulogne.demo", None),)),
        CaseSeed("r4", "assigned", "critical", 88, "ops.boulogne.demo", "ines.roche.demo@boulogne.demo", 40, 6, (("case_created", "Dossier protection ouvert.", 39, "internal"), ("owner_assigned", "Referent operationnel affecte.", 18, "internal"), ("professional_assigned", "Psychologue de reference mobilisee.", 6, "internal")), (("admin_user", "owner", "ops.boulogne.demo.user", None, None), ("professional_lead", "primary_professional", None, "ines.roche.demo@boulogne.demo", None))),
        CaseSeed("r5", "triaged", "critical", 89, None, "camille.laurent.demo@boulogne.demo", 82, 79, (("case_created", "Menage sans solution de nuit enregistre.", 80, "internal"), ("triage_scored", "Hebergement a declencher en priorite.", 79, "internal")), (("professional_lead", "primary_professional", None, "camille.laurent.demo@boulogne.demo", None),)),
        CaseSeed("r9", "assigned", "normal", 44, "admin", "antoine.lefevre.demo@boulogne.demo", 96, 80, (("case_created", "Dossier prefecture enregistre.", 95, "internal"), ("owner_assigned", "Prise en charge admin confirmee.", 90, "internal"), ("note_added", "Attente d'une piece bailleur et d'un rendez-vous prefectoral.", 80, "internal")), (("admin_user", "owner", "admin.user", None, None), ("professional_lead", "primary_professional", None, "antoine.lefevre.demo@boulogne.demo", None))),
        CaseSeed("r2", "in_progress", "high", 75, "admin", "dr.sarah.cohen.demo@boulogne.demo", 56, 4, (("case_created", "Suivi post-hospitalisation demarre.", 54, "internal"), ("owner_assigned", "Referent admin nomme.", 28, "internal"), ("professional_assigned", "Coordination soignante activee.", 8, "internal"), ("note_added", "Compte-rendu de visite transmis au CCAS.", 4, "internal")), (("admin_user", "owner", "admin.user", None, None), ("professional_lead", "primary_professional", None, "dr.sarah.cohen.demo@boulogne.demo", None), ("association", "coordinator", None, None, "CCAS Boulogne-Billancourt"))),
        CaseSeed("r11", "in_progress", "high", 70, "ops.boulogne.demo", "julien.moreau.demo@boulogne.demo", 28, 2, (("case_created", "Coordination multi-acteurs ouverte.", 26, "internal"), ("owner_assigned", "Referent pilotage designe.", 14, "internal"), ("participant_added", "Ajout d'un partenaire de sante.", 8, "internal"), ("note_added", "Point de coordination matinal consigne.", 2, "internal")), (("admin_user", "owner", "ops.boulogne.demo.user", None, None), ("professional_lead", "primary_professional", None, "julien.moreau.demo@boulogne.demo", None), ("association", "coordinator", None, None, "Reseau accompagnement Hauts-de-Seine"))),
        CaseSeed("r17", "assigned", "high", 68, "ops.boulogne.demo", "nathalie.dupont.demo@boulogne.demo", 50, 18, (("case_created", "Signalement aidant enregistre.", 48, "internal"), ("owner_assigned", "Referent senior mobilise.", 22, "internal"), ("note_added", "Un relais de jour est recherche.", 18, "internal")), (("admin_user", "owner", "ops.boulogne.demo.user", None, None), ("professional_lead", "primary_professional", None, "nathalie.dupont.demo@boulogne.demo", None))),
        CaseSeed("r19", "in_progress", "high", 64, "admin", "antoine.lefevre.demo@boulogne.demo", 64, 7, (("case_created", "Mediation bailleur ouverte.", 60, "internal"), ("owner_assigned", "Referent logement affecte.", 32, "internal"), ("contact_attempted", "Tentative de contact bailleur effectuee.", 7, "internal")), (("admin_user", "owner", "admin.user", None, None), ("professional_lead", "primary_professional", None, "antoine.lefevre.demo@boulogne.demo", None))),
        CaseSeed("r20", "triaged", "high", 72, None, "camille.laurent.demo@boulogne.demo", 72, 65, (("case_created", "Dossier CPAM enregistre.", 70, "internal"), ("triage_scored", "Risque de rupture de soins identifie.", 65, "internal")), (("professional_lead", "primary_professional", None, "camille.laurent.demo@boulogne.demo", None),)),
        CaseSeed("r21", "in_progress", "high", 63, "ops.boulogne.demo", "sophie.bernard.demo@boulogne.demo", 46, 3, (("case_created", "Dossier famille et handicap cree.", 44, "internal"), ("owner_assigned", "Coordination structure famille activee.", 16, "internal"), ("participant_added", "Echange avec l'ecole ajoute au dossier.", 9, "internal"), ("note_added", "Rendez-vous MDPH prepare.", 3, "internal")), (("admin_user", "owner", "ops.boulogne.demo.user", None, None), ("professional_lead", "primary_professional", None, "sophie.bernard.demo@boulogne.demo", None))),
        CaseSeed("r13", "resolved", "normal", 24, "admin", "claire.martin.lead@boulogne.demo", 44, 9, (("case_created", "Demande alimentaire enregistree.", 42, "internal"), ("owner_assigned", "Responsable affecte.", 24, "internal"), ("case_resolved", "Colis remis et confirmation obtenue.", 9, "public")), (("admin_user", "owner", "admin.user", None, None),)),
        CaseSeed("r14", "closed", "normal", 12, "ops.boulogne.demo", "sophie.bernard.demo@boulogne.demo", 68, 11, (("case_created", "Orientation sociale ouverte.", 66, "internal"), ("owner_assigned", "Referent nomme.", 34, "internal"), ("case_resolved", "Orientation realisee.", 18, "public"), ("case_closed", "Cloture apres confirmation du rendez-vous.", 11, "public")), (("admin_user", "owner", "ops.boulogne.demo.user", None, None),)),
        CaseSeed("r15", "cancelled", "low", 5, None, None, 20, 19, (("case_created", "Doublon detecte a l'accueil.", 19, "internal"), ("status_changed", "Annulation pour doublon de saisie.", 19, "internal")), ()),
    ]


def seed() -> dict[str, object]:
    uri = _ensure_demo_branch()
    print(f"Seeding against {_mask_db_url(uri)}")
    summary: dict[str, int] = {
        "structures_created": 0,
        "structures_reused": 0,
        "admins_created": 0,
        "admins_reused": 0,
        "users_created": 0,
        "users_reused": 0,
        "intervenants_created": 0,
        "intervenants_reused": 0,
        "leads_created": 0,
        "leads_reused": 0,
        "requests_created": 0,
        "requests_reused": 0,
        "notifications_created": 0,
        "notifications_reused": 0,
        "security_signals_created": 0,
        "security_signals_reused": 0,
    }
    demo_structure_slugs = [
        "ccas-boulogne-demo",
        "association-solidarite-92-demo-boulogne",
        "reseau-sante-boulogne-demo",
        "cellule-coordination-senior-demo-boulogne",
        "plateforme-protection-familles-92-demo-boulogne",
    ]
    existing_structure_slugs = {
        slug
        for (slug,) in db.session.query(Structure.slug)
        .filter(Structure.slug.in_(demo_structure_slugs))
        .all()
    }

    structures = {
        "ccas-boulogne-demo": _get_or_create_structure(
            "CCAS Boulogne-Billancourt",
            "ccas-boulogne-demo",
            summary=summary,
        ),
        "association-solidarite-92-demo-boulogne": _get_or_create_structure(
            "Association Solidarite 92",
            "association-solidarite-92-demo-boulogne",
            summary=summary,
        ),
        "reseau-sante-boulogne-demo": _get_or_create_structure(
            "Reseau accompagnement Hauts-de-Seine",
            "reseau-sante-boulogne-demo",
            summary=summary,
        ),
        "cellule-coordination-senior-demo-boulogne": _get_or_create_structure(
            "Maison des Familles Ouest",
            "cellule-coordination-senior-demo-boulogne",
            summary=summary,
        ),
        "plateforme-protection-familles-92-demo-boulogne": _get_or_create_structure(
            "Centre social Issy",
            "plateforme-protection-familles-92-demo-boulogne",
            summary=summary,
        ),
    }
    db.session.flush()
    summary["structures_created"] = sum(1 for slug in demo_structure_slugs if slug not in existing_structure_slugs)
    summary["structures_reused"] = len(demo_structure_slugs) - summary["structures_created"]

    existing_admin = AdminUser.query.filter_by(username="admin").first()
    if existing_admin is None:
        existing_admin = _get_or_create_admin(
            username="admin",
            email="admin.demo.boulogne@helpchain.demo",
            role="superadmin",
            structure_id=None,
            summary=summary,
        )
    else:
        existing_admin.is_active = True
        if not existing_admin.email:
            existing_admin.email = "admin.demo.boulogne@helpchain.demo"
        if not existing_admin.role:
            existing_admin.role = "superadmin"
        _bump(summary, "admins_reused")

    admins = {
        "admin": existing_admin,
        "ops.boulogne.demo": _get_or_create_admin(
            username="ops.boulogne.demo",
            email="ops.boulogne.demo@helpchain.demo",
            role="ops",
            structure_id=structures["ccas-boulogne-demo"].id,
            summary=summary,
        ),
    }
    db.session.flush()

    user_lookup: dict[str, User] = {
        "admin.user": _get_or_create_user(
            username="admin",
            email="admin.demo.boulogne@helpchain.demo",
            structure_id=structures["ccas-boulogne-demo"].id,
            role="superadmin",
            summary=summary,
        ),
        "ops.boulogne.demo.user": _get_or_create_user(
            username="ops.boulogne.demo",
            email="ops.boulogne.demo@helpchain.demo",
            structure_id=structures["ccas-boulogne-demo"].id,
            role="admin",
            summary=summary,
        ),
    }
    for seed in _request_seeds():
        if seed.requester_username not in user_lookup:
            user_lookup[seed.requester_username] = _get_or_create_user(
                username=seed.requester_username,
                email=f"{seed.requester_username}@helpchain.demo",
                structure_id=structures[seed.structure_slug].id,
                role="requester",
                summary=summary,
            )
    db.session.flush()

    intervenants_data = [
        ("Claire Martin", "claire.martin.demo@careresociale.demo", "+33 6 11 20 30 41", "Assistant social", "15 Rue de Billancourt", "Boulogne-Billancourt", "ccas-boulogne-demo", True, 240),
        ("Julien Moreau", "julien.moreau.demo@coordination.demo", "+33 6 11 20 30 42", "Coordinateur terrain", "12 Rue Nationale", "Boulogne-Billancourt", "ccas-boulogne-demo", True, 216),
        ("Sophie Bernard", "sophie.bernard.demo@solidarite92.demo", "+33 6 11 20 30 43", "Referent logement", "26 Avenue Victor Hugo", "Boulogne-Billancourt", "reseau-sante-boulogne-demo", True, 190),
        ("Nathalie Dupont", "nathalie.dupont.demo@solidarite92.demo", "+33 6 11 20 30 44", "Psychologue", "3 Rue Anna Jacquin", "Boulogne-Billancourt", "cellule-coordination-senior-demo-boulogne", True, 168),
        ("Antoine Lefevre", "antoine.lefevre.demo@justice.demo", "+33 6 11 20 30 45", "Conseiller orientation", "48 Rue de Paris", "Issy-les-Moulineaux", "plateforme-protection-familles-92-demo-boulogne", True, 154),
        ("Camille Laurent", "camille.laurent.demo@sante.demo", "+33 6 11 20 30 46", "Coordinateur terrain", "22 Rue de la Saussiere", "Boulogne-Billancourt", "reseau-sante-boulogne-demo", False, 144),
        ("Romain Petit", "romain.petit.demo@solidarite92.demo", "+33 6 11 20 30 47", "Mediateur social", "9 Rue Paul Bert", "Boulogne-Billancourt", "association-solidarite-92-demo-boulogne", True, 132),
        ("Elodie Garnier", "elodie.garnier.demo@coordination.demo", "+33 6 11 20 30 48", "Assistant social", "81 Boulevard de la Republique", "Boulogne-Billancourt", "reseau-sante-boulogne-demo", True, 120),
        ("Sarah Cohen", "dr.sarah.cohen.demo@medical.demo", "+33 6 11 20 30 49", "Psychologue", "19 Rue de Bellevue", "Boulogne-Billancourt", "reseau-sante-boulogne-demo", True, 108),
        ("Ines Roche", "ines.roche.demo@protection.demo", "+33 6 11 20 30 50", "Conseiller orientation", "2 Rue des Menus", "Issy-les-Moulineaux", "plateforme-protection-familles-92-demo-boulogne", True, 96),
        ("Thomas Mercier", "thomas.mercier.demo@ccas.demo", "+33 6 11 20 30 51", "Assistant social", "67 Rue Thiers", "Boulogne-Billancourt", "ccas-boulogne-demo", False, 84),
        ("Julie Perrin", "julie.perrin.demo@coordination.demo", "+33 6 11 20 30 52", "Mediateur social", "21 Rue de Meudon", "Issy-les-Moulineaux", "cellule-coordination-senior-demo-boulogne", True, 72),
        ("Karim Bensaid", "karim.bensaid.demo@sante.demo", "+33 6 11 20 30 53", "Referent logement", "5 Rue des 4 Cheminees", "Boulogne-Billancourt", "reseau-sante-boulogne-demo", True, 60),
        ("Melanie Faure", "melanie.faure.demo@familles.demo", "+33 6 11 20 30 54", "Coordinateur terrain", "28 Rue de Clamart", "Issy-les-Moulineaux", "plateforme-protection-familles-92-demo-boulogne", True, 48),
    ]
    if not _table_available(Intervenant):
        intervenants_data = []
    for (
        full_name,
        email,
        phone,
        profession,
        address,
        city,
        structure_slug,
        is_active,
        created_hours_ago,
    ) in intervenants_data:
        _get_or_create_intervenant(
            structure_id=structures[structure_slug].id,
            full_name=full_name,
            email=email,
            phone=phone,
            profession=profession,
            address=address,
            city=city,
            is_active=is_active,
            created_hours_ago=created_hours_ago,
            summary=summary,
        )

    lead_specs = [
        ("Claire Martin", "claire.martin.lead@boulogne.demo", "+33 6 21 31 41 51", "Assistant social", "CCAS Boulogne-Billancourt", "Disponible sous 24h", "15 Rue de Billancourt", "Boulogne-Billancourt", "new", 30, 6, None, None, None, "Premier contact CCAS a rappeler aujourd'hui."),
        ("Sarah Cohen", "dr.sarah.cohen.demo@boulogne.demo", "+33 6 21 31 41 52", "Psychologue", "Reseau accompagnement Hauts-de-Seine", "Visite prioritaire", "19 Rue de Bellevue", "Boulogne-Billancourt", "contacted", 76, 14, 36, 18, None, "Entretien telephonique realise, attente de confirmation du creneau."),
        ("Julien Moreau", "julien.moreau.demo@boulogne.demo", "+33 6 21 31 41 53", "Coordinateur terrain", "CCAS Boulogne-Billancourt", "Coordination rapide", "12 Rue Nationale", "Boulogne-Billancourt", "demo_scheduled", 54, 8, 30, 16, None, "Demo operationnelle cale avec l'equipe de direction."),
        ("Ines Roche", "ines.roche.demo@boulogne.demo", "+33 6 21 31 41 54", "Conseiller orientation", "Centre social Issy", "Creneau discret", "2 Rue des Menus", "Issy-les-Moulineaux", "pilot_discussion", 118, 10, 92, 72, 24, "Pilotage local en discussion avec le binome social et direction."),
        ("Antoine Lefevre", "antoine.lefevre.demo@boulogne.demo", "+33 6 21 31 41 55", "Conseiller orientation", "Centre social Issy", "Sous 48h", "48 Rue de Paris", "Issy-les-Moulineaux", "contacted", 144, 82, 96, 72, None, "Relance attendue apres envoi du recap fonctionnel."),
        ("Camille Laurent", "camille.laurent.demo@boulogne.demo", "+33 6 21 31 41 56", "Referent logement", "Reseau accompagnement Hauts-de-Seine", "Cabinet disponible", "22 Rue de la Saussiere", "Boulogne-Billancourt", "closed", 210, 32, 180, 156, 120, "Lead clos apres orientation vers une autre priorite territoriale."),
        ("Sophie Bernard", "sophie.bernard.demo@boulogne.demo", "+33 6 21 31 41 57", "Mediateur social", "Maison des Familles Ouest", "Passage a domicile", "26 Avenue Victor Hugo", "Boulogne-Billancourt", "new", 96, 80, None, 48, None, "Demande de rappel en attente, aucune prise de contact recente."),
        ("Nathalie Dupont", "nathalie.dupont.demo@boulogne.demo", "+33 6 21 31 41 58", "Psychologue", "Association Solidarite 92", "Disponible sous 72h", "31 Rue de Silly", "Boulogne-Billancourt", "pilot_discussion", 62, 5, 40, 20, None, "Echange prometteur pour un pilote de coordination sante mentale."),
    ]
    if not _table_available(ProfessionalLead):
        lead_specs = []
    leads: dict[str, ProfessionalLead] = {}
    for (
        full_name,
        email,
        phone,
        profession,
        organization,
        availability,
        address,
        city,
        status,
        created_hours_ago,
        touched_hours_ago,
        contacted_hours_ago,
        first_followup_hours_ago,
        second_followup_hours_ago,
        notes,
    ) in lead_specs:
        leads[email] = _get_or_create_professional_lead(
            owner_admin_id=admins["admin"].id,
            full_name=full_name,
            email=email,
            phone=phone,
            profession=profession,
            organization=organization,
            availability=availability,
            address=address,
            city=city,
            status=status,
            created_hours_ago=created_hours_ago,
            touched_hours_ago=touched_hours_ago,
            contacted_hours_ago=contacted_hours_ago,
            first_followup_hours_ago=first_followup_hours_ago,
            second_followup_hours_ago=second_followup_hours_ago,
            notes=notes,
            summary=summary,
        )
    db.session.flush()

    requests_map: dict[str, Request] = {}
    for seed_row in _request_seeds():
        requests_map[seed_row.key] = _upsert_request(
            seed_row,
            structures=structures,
            admins=admins,
            users=user_lookup,
            summary=summary,
        )
    db.session.flush()

    for seed_row in _request_seeds():
        req = requests_map[seed_row.key]
        activity_plan = [("request_created", f"{DEMO_MARKER} - demande creee", max(seed_row.created_hours_ago - 1, 1))]
        if seed_row.owner_username:
            activity_plan.append(("owner_assigned", f"{DEMO_MARKER} - responsable assigne", max(seed_row.updated_hours_ago + 4, 1)))
        for idx, hours in enumerate(seed_row.activity_hours_ago, start=1):
            if hours > 72:
                msg = f"{DEMO_MARKER} - relance envoyee"
                action = "followup_sent"
            elif seed_row.priority in {"critical", "high"} and idx == 1:
                msg = f"{DEMO_MARKER} - contact tente avec retour partiel"
                action = "contact_attempted"
            elif idx % 2 == 0:
                msg = f"{DEMO_MARKER} - statut mis a jour"
                action = "status_updated"
            else:
                msg = f"{DEMO_MARKER} - note operateur"
                action = "note_added"
            activity_plan.append((action, msg, hours))
        if seed_row.priority == "critical" and seed_row.status not in {"done", "cancelled"}:
            activity_plan.append(("escalated", f"{DEMO_MARKER} - escalade de vigilance", max(seed_row.updated_hours_ago + 1, 1)))
        if seed_row.status in {"done", "cancelled"}:
            activity_plan.append(("request_closed", f"{DEMO_MARKER} - cloture du dossier", seed_row.updated_hours_ago))
        for action, text, hours in activity_plan:
            _upsert_request_activity(
                req.id,
                actor_admin_id=admins["admin"].id if req.owner_id else None,
                action=action,
                text=text,
                created_at=NOW - timedelta(hours=hours),
            )

    cases_map: dict[str, Case] = {}
    if _table_available(Case) and _table_available(ProfessionalLead):
        for case_seed in _case_seeds():
            case_row = _upsert_case(case_seed, requests_map=requests_map, admins=admins, leads=leads)
            cases_map[case_seed.request_key] = case_row
        db.session.flush()

        for case_seed in _case_seeds():
            case_row = cases_map[case_seed.request_key]
            for event_type, message, hours, visibility in case_seed.events:
                actor_id = admins["admin"].id if case_seed.owner_username == "admin" else admins["ops.boulogne.demo"].id if case_seed.owner_username else None
                _upsert_case_event(
                    case_row.id,
                    actor_user_id=actor_id,
                    event_type=event_type,
                    message=f"{message} ({DEMO_MARKER})",
                    visibility=visibility,
                    created_at=NOW - timedelta(hours=hours),
                )
            for participant_type, role, user_key, lead_email, external_name in case_seed.participants:
                _upsert_case_participant(
                    case_row.id,
                    participant_type=participant_type,
                    role=role,
                    user_id=user_lookup[user_key].id if user_key else None,
                    professional_lead_id=leads[lead_email].id if lead_email else None,
                    external_name=external_name,
                )

    notification_specs = [
        ("email", "request_sla_owner_reminder", "ops.boulogne.demo@helpchain.demo", f"{DEMO_MARKER} - relance proprietaire logement", "pending", 0, 5, 2, None, structures["association-solidarite-92-demo-boulogne"].id),
        ("email", "request_sla_inactivity_reminder", "admin.demo.boulogne@helpchain.demo", f"{DEMO_MARKER} - suivi inactif senior", "retry", 2, 5, 4, 1, structures["cellule-coordination-senior-demo-boulogne"].id),
        ("sms", "request_sla_inactivity_escalation", "+33611203041", f"{DEMO_MARKER} - escalation hebergement", "dead_letter", 5, 5, 10, 3, structures["association-solidarite-92-demo-boulogne"].id),
        ("email", "case_assignment_digest", "coordination@boulogne.demo", f"{DEMO_MARKER} - digest coordination sante", "done", 1, 5, 8, None, structures["reseau-sante-boulogne-demo"].id),
        ("email", "owner_alert", "pilotage@boulogne.demo", f"{DEMO_MARKER} - alerte sans responsable", "pending", 1, 5, 1, 2, structures["ccas-boulogne-demo"].id),
        ("email", "closure_notice", "direction@solidarite92.demo", f"{DEMO_MARKER} - cloture orientation sociale", "sent", 1, 5, 12, None, structures["ccas-boulogne-demo"].id),
        ("email", "lead_followup", "direction@issy.demo", f"{DEMO_MARKER} - relance lead centre social", "failed", 3, 5, 18, 4, structures["plateforme-protection-familles-92-demo-boulogne"].id),
        ("email", "security_digest", "security@helpchain.demo", f"{DEMO_MARKER} - digest securite admin", "sent", 1, 3, 14, None, structures["ccas-boulogne-demo"].id),
        ("sms", "critical_case_alert", "+33611203054", f"{DEMO_MARKER} - alerte urgence sociale", "retry", 1, 4, 3, 1, structures["ccas-boulogne-demo"].id),
    ]
    if _table_available(NotificationJob):
        for channel, event_type, recipient, subject, status, attempts, max_attempts, created_hours_ago, next_retry_hours, structure_id in notification_specs:
            _upsert_notification_job(
                structure_id=structure_id,
                channel=channel,
                event_type=event_type,
                recipient=recipient,
                subject=subject,
                status=status,
                attempts=attempts,
                max_attempts=max_attempts,
                created_hours_ago=created_hours_ago,
                next_retry_hours_from_now=next_retry_hours,
                summary=summary,
            )

    if _table_available(AdminLoginAttempt) and _table_available(AdminAuditEvent):
        _reset_security_demo_rows(summary)
        _seed_security_events(
            summary=summary,
            admin_user=admins["admin"],
            ops_admin=admins["ops.boulogne.demo"],
            request_targets=requests_map,
        )

    db.session.commit()

    return {
        "marker": DEMO_MARKER,
        "summary": {
            "structures": {"created": summary["structures_created"], "reused": summary["structures_reused"]},
            "requests": {"created": summary["requests_created"], "reused": summary["requests_reused"]},
            "notifications": {"created": summary["notifications_created"], "reused": summary["notifications_reused"]},
            "security_signals": {
                "created": summary["security_signals_created"],
                "reused": summary["security_signals_reused"],
            },
            "leads": {"created": summary["leads_created"], "reused": summary["leads_reused"]},
            "intervenants": {
                "created": summary["intervenants_created"],
                "reused": summary["intervenants_reused"],
            },
        },
        "totals": {
            "AdminUser": db.session.query(AdminUser).count(),
            "Structure": db.session.query(Structure).count(),
            "Intervenant": db.session.query(Intervenant).count() if _table_available(Intervenant) else 0,
            "ProfessionalLead": db.session.query(ProfessionalLead).count() if _table_available(ProfessionalLead) else 0,
            "Request": db.session.query(Request).count(),
            "Case": db.session.query(Case).count() if _table_available(Case) else 0,
            "RequestActivity": db.session.query(RequestActivity).count(),
            "CaseEvent": db.session.query(CaseEvent).count() if _table_available(CaseEvent) else 0,
            "NotificationJob": db.session.query(NotificationJob).count() if _table_available(NotificationJob) else 0,
            "AdminLoginAttempt": db.session.query(AdminLoginAttempt).count() if _table_available(AdminLoginAttempt) else 0,
            "AdminAuditEvent": db.session.query(AdminAuditEvent).count() if _table_available(AdminAuditEvent) else 0,
        },
        "urls": [
            "/admin/home",
            "/admin/requests",
            "/admin/notifications",
            "/admin/security",
            "/admin/audit",
            "/admin/sla",
            "/admin/professional-leads/demo",
            "/admin/structures",
            "/admin/intervenants",
        ],
    }


def main() -> int:
    with app.app_context():
        try:
            result = seed()
        except Exception as exc:
            print(f"SEED_DEMO_BOULOGNE_ERROR: {exc}")
            return 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
