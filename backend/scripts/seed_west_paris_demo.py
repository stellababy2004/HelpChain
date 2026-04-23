#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import random
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print(json.dumps({"step": "bootstrap_start", "script": "seed_west_paris_demo"}, ensure_ascii=False), flush=True)
from backend.local_db_guard import apply_local_runtime_db_contract

_runtime_db = apply_local_runtime_db_contract()
print(
    json.dumps(
        {
            "step": "db_contract_applied",
            "selected_db": _runtime_db.selected_uri,
            "reason": _runtime_db.reason,
        },
        ensure_ascii=False,
    ),
    flush=True,
)
from backend.extensions import db
from backend.helpchain_backend.src.app import create_app
from backend.helpchain_backend.src.models import (
    Case,
    CaseEvent,
    OrganizationAccessRequest,
    ProfessionalLead,
)
from backend.models import AdminUser, NotificationJob, Request, RequestActivity, Structure, User
from backend.models_with_analytics import AnalyticsEvent, UserBehavior

print(json.dumps({"step": "create_app_start"}, ensure_ascii=False), flush=True)
app = create_app()
print(json.dumps({"step": "create_app_ready"}, ensure_ascii=False), flush=True)


DEMO_SOURCE = "demo_seed_west_paris"
SESSION_PREFIX = "demo_west_paris_"
NOW = datetime.now(UTC)
RANDOM = random.Random(92075)
STEP_TIMEOUT_SECONDS = int(os.getenv("HC_SEED_STEP_TIMEOUT_SECONDS", "45"))
SQLITE_BUSY_TIMEOUT_MS = int(os.getenv("HC_SEED_SQLITE_BUSY_TIMEOUT_MS", "1500"))

CITY_META = {
    "Paris": {
        "count": 25,
        "postcode": "75016",
        "lat": 48.8566,
        "lng": 2.3522,
        "structure": "coordination-logement-paris-16-demo",
    },
    "Boulogne-Billancourt": {
        "count": 15,
        "postcode": "92100",
        "lat": 48.8397,
        "lng": 2.2399,
        "structure": "ccas-boulogne-billancourt-demo",
    },
    "Levallois-Perret": {
        "count": 10,
        "postcode": "92300",
        "lat": 48.8932,
        "lng": 2.2879,
        "structure": "mairie-levallois-perret-demo",
    },
    "Neuilly-sur-Seine": {
        "count": 10,
        "postcode": "92200",
        "lat": 48.8841,
        "lng": 2.2683,
        "structure": "centre-social-neuilly-demo",
    },
}

STRUCTURES = [
    ("CCAS Boulogne-Billancourt", "ccas-boulogne-billancourt-demo"),
    ("Mairie Levallois-Perret", "mairie-levallois-perret-demo"),
    ("Centre Social Neuilly", "centre-social-neuilly-demo"),
    ("Association Solidarite Paris Ouest", "association-solidarite-paris-ouest-demo"),
    ("Service Seniors Hauts-de-Seine", "service-seniors-hauts-de-seine-demo"),
    ("Coordination Logement Paris 16", "coordination-logement-paris-16-demo"),
    ("Aide Familles Levallois", "aide-familles-levallois-demo"),
    ("Reseau Handicap Neuilly", "reseau-handicap-neuilly-demo"),
]

OPS_USERS = [
    ("ops.paris", "ops.paris@helpchain.demo", "coordination-logement-paris-16-demo"),
    ("ops.boulogne", "ops.boulogne@helpchain.demo", "ccas-boulogne-billancourt-demo"),
    ("ops.neuilly", "ops.neuilly@helpchain.demo", "centre-social-neuilly-demo"),
]

REQUEST_TEMPLATES = [
    ("Demande aide alimentaire urgence", "Famille orientee par un partenaire local, besoin d'un relais alimentaire sous 24 heures.", "food"),
    ("Accompagnement rendez-vous medical", "Usager fragile sans solution d'accompagnement pour un rendez-vous hospitalier prioritaire.", "health"),
    ("Recherche hebergement temporaire", "Menage sans solution stable pour les prochains jours, coordination rapide demandee.", "housing"),
    ("Soutien administratif CAF", "Dossier CAF bloque par pieces manquantes, besoin d'aide pour remettre le parcours en mouvement.", "admin_help"),
    ("Isolement senior visite a domicile", "Signalement d'un senior isole, besoin d'une visite de verification et d'un suivi social.", "isolation"),
    ("Transport PMR hopital", "Personne a mobilite reduite sans transport adapte pour une consultation importante.", "mobility"),
    ("Soutien mere isolee", "Parent isole avec plusieurs demarches urgentes, coordination entre services necessaire.", "family"),
    ("Orientation logement social", "Demande d'orientation sur un parcours logement avec documents incomplets.", "housing"),
    ("Besoin interprete administratif", "Usager allophone bloque dans une demarche administrative sensible.", "admin_help"),
    ("Demande kit hygiene", "Demande ponctuelle de kit hygiene et orientation vers distribution locale.", "material_aid"),
]

STATUSES = ["open", "in_progress", "done", "cancelled"]
PRIORITIES = ["low", "normal", "high", "critical"]
CASE_STATUSES = ["new", "active", "blocked", "resolved"]
LEAD_STATUSES = ["new", "contacted", "qualified", "demo_booked", "pilot_discussion", "won"]
ACCESS_STATUSES = ["new", "reviewed", "approved", "need_info"]
NOTIFICATION_STATUSES = ["pending", "processing", "retry", "failed", "sent"]
PAGES = ["/", "/offre", "/deploiement", "/professionnels", "/demander-acces", "/contact"]
REFERRERS = {
    "Google": "https://www.google.com/search?q=logiciel+coordination+ccas",
    "LinkedIn": "https://www.linkedin.com/feed/",
    "Direct": None,
    "ChatGPT": "https://chat.openai.com/",
}


def _tables() -> set[str]:
    return set(inspect(db.session.get_bind()).get_table_names())


def _has_table(name: str) -> bool:
    return name in _tables()


def _has_column(table: str, column: str) -> bool:
    if not _has_table(table):
        return False
    return any(col["name"] == column for col in inspect(db.session.get_bind()).get_columns(table))


def _progress(step: str, **data: object) -> None:
    print(json.dumps({"step": step, **data}, ensure_ascii=False), flush=True)


def _sqlite_db_state() -> dict[str, object]:
    bind = db.session.get_bind()
    url = getattr(bind, "url", None)
    database = getattr(url, "database", None)
    state: dict[str, object] = {"database": database}
    if database:
        db_path = Path(database)
        journal_path = Path(f"{database}-journal")
        wal_path = Path(f"{database}-wal")
        state["db_exists"] = db_path.exists()
        state["db_size"] = db_path.stat().st_size if db_path.exists() else None
        state["journal_exists"] = journal_path.exists()
        state["journal_size"] = journal_path.stat().st_size if journal_path.exists() else 0
        state["wal_exists"] = wal_path.exists()
        state["wal_size"] = wal_path.stat().st_size if wal_path.exists() else 0
    return state


def _configure_db_for_seed() -> None:
    bind = db.session.get_bind()
    if bind.dialect.name == "sqlite":
        db.session.execute(text(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}"))
        _progress("db_state", **_sqlite_db_state())


def _is_fast_fail_db_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(token in message for token in ("database is locked", "database table is locked", "disk i/o error"))


def _commit_block(label: str, counts: dict[str, int], **updates: int) -> None:
    start = time.monotonic()
    try:
        db.session.commit()
    except OperationalError as exc:
        db.session.rollback()
        if _is_fast_fail_db_error(exc):
            _progress("db_fast_fail", block=label, error=str(exc), **_sqlite_db_state())
            raise
        raise
    elapsed = time.monotonic() - start
    counts.update(updates)
    _progress("block_committed", block=label, elapsed_seconds=round(elapsed, 2), **updates)
    if elapsed > STEP_TIMEOUT_SECONDS:
        raise TimeoutError(f"{label} commit took {elapsed:.1f}s, above guard {STEP_TIMEOUT_SECONDS}s")


def _run_block(label: str, fn):
    start = time.monotonic()
    _progress("block_start", block=label)
    result = fn()
    elapsed = time.monotonic() - start
    _progress("block_ready", block=label, elapsed_seconds=round(elapsed, 2))
    if elapsed > STEP_TIMEOUT_SECONDS:
        raise TimeoutError(f"{label} took {elapsed:.1f}s, above guard {STEP_TIMEOUT_SECONDS}s")
    return result


def _demo_payload(**extra: object) -> str:
    return json.dumps({"source": DEMO_SOURCE, **extra}, ensure_ascii=False, sort_keys=True)


def _safe_now_minus(days: int, hours: int = 0) -> datetime:
    return NOW - timedelta(days=days, hours=hours)


def _get_or_create_structure(name: str, slug: str) -> Structure:
    row = Structure.query.filter_by(slug=slug).first()
    if row is None:
        row = Structure(name=name, slug=slug, status="active")
        db.session.add(row)
    row.name = name
    row.status = "active"
    return row


def _get_or_create_admin(username: str, email: str, structure_id: int | None) -> AdminUser:
    row = AdminUser.query.filter_by(username=username).first()
    if row is None:
        row = AdminUser(username=username, email=email, role="ops", is_active=True, structure_id=structure_id)
        row.set_password("HelpChainDemo2026!")
        db.session.add(row)
    row.role = row.role or "ops"
    row.is_active = True
    row.structure_id = structure_id
    return row


def _get_or_create_requester(index: int, structure_id: int | None) -> User:
    username = f"demo.westparis.requester.{index:03d}"
    row = User.query.filter_by(username=username).first()
    if row is None:
        row = User(
            username=username,
            email=f"{username}@helpchain.demo",
            password_hash="demo_seed_disabled_login",
            role="requester",
            is_active=True,
            structure_id=structure_id,
        )
        db.session.add(row)
    row.structure_id = structure_id
    row.is_active = True
    return row


def _get_or_create_requester_key(key: str, structure_id: int | None) -> User:
    username = f"demo.westparis.requester.{key}"
    row = User.query.filter_by(username=username).first()
    if row is None:
        row = User(
            username=username,
            email=f"{username}@helpchain.demo",
            password_hash="demo_seed_disabled_login",
            role="requester",
            is_active=True,
            structure_id=structure_id,
        )
        db.session.add(row)
    row.structure_id = structure_id
    row.is_active = True
    return row


def _reset_demo_rows() -> None:
    request_ids = [rid for (rid,) in db.session.query(Request.id).filter(Request.source_channel == DEMO_SOURCE).all()]
    if request_ids and _has_table("case_events"):
        case_ids = [cid for (cid,) in db.session.query(Case.id).filter(Case.request_id.in_(request_ids)).all()]
        if case_ids:
            CaseEvent.query.filter(CaseEvent.case_id.in_(case_ids)).delete(synchronize_session=False)
        Case.query.filter(Case.request_id.in_(request_ids)).delete(synchronize_session=False)
    if request_ids:
        RequestActivity.query.filter(RequestActivity.request_id.in_(request_ids)).delete(synchronize_session=False)
        Request.query.filter(Request.id.in_(request_ids)).delete(synchronize_session=False)

    ProfessionalLead.query.filter(ProfessionalLead.source == DEMO_SOURCE).delete(synchronize_session=False)
    OrganizationAccessRequest.query.filter(
        OrganizationAccessRequest.internal_notes.like(f"%{DEMO_SOURCE}%")
    ).delete(synchronize_session=False)
    NotificationJob.query.filter(NotificationJob.payload_json.like(f"%{DEMO_SOURCE}%")).delete(
        synchronize_session=False
    )
    if _has_table("analytics_events"):
        AnalyticsEvent.query.filter(AnalyticsEvent.user_session.like(f"{SESSION_PREFIX}%")).delete(
            synchronize_session=False
        )
    if _has_table("user_behaviors"):
        UserBehavior.query.filter(UserBehavior.session_id.like(f"{SESSION_PREFIX}%")).delete(
            synchronize_session=False
        )
    db.session.commit()


def _seed_foundation() -> tuple[dict[str, Structure], dict[str, AdminUser]]:
    structures = {slug: _get_or_create_structure(name, slug) for name, slug in STRUCTURES}
    db.session.flush()
    admins = {
        username: _get_or_create_admin(username, email, structures[slug].id)
        for username, email, slug in OPS_USERS
    }
    fallback = AdminUser.query.filter_by(role="superadmin").first() or AdminUser.query.order_by(AdminUser.id.asc()).first()
    if fallback:
        admins["founder"] = fallback
    db.session.flush()
    return structures, admins


def _risk_for(priority: str, status: str, age_days: int) -> tuple[int, str]:
    base = {"low": 15, "normal": 35, "high": 62, "critical": 84}[priority]
    if status == "open" and age_days >= 7:
        base += 12
    if status == "done":
        base -= 20
    if status == "cancelled":
        base -= 28
    score = max(0, min(98, base + RANDOM.randint(-7, 7)))
    if score >= 80:
        return score, "critical"
    if score >= 55:
        return score, "attention"
    return score, "standard"


def _seed_requests_core(structures: dict[str, Structure]) -> list[Request]:
    rows: list[Request] = []
    index = 1
    existing_requests = {
        row.title: row
        for row in Request.query.filter(Request.source_channel == DEMO_SOURCE).all()
    }
    requesters = {
        city: _get_or_create_requester_key(
            city.lower().replace("-", "_").replace(" ", "_"),
            structures[meta["structure"]].id,
        )
        for city, meta in CITY_META.items()
    }
    status_cycle = ["open"] * 22 + ["in_progress"] * 22 + ["done"] * 11 + ["cancelled"] * 5
    priority_cycle = ["normal"] * 26 + ["high"] * 18 + ["critical"] * 8 + ["low"] * 8
    RANDOM.shuffle(status_cycle)
    RANDOM.shuffle(priority_cycle)

    for city, meta in CITY_META.items():
        for _ in range(meta["count"]):
            template = REQUEST_TEMPLATES[(index - 1) % len(REQUEST_TEMPLATES)]
            status = status_cycle[index - 1]
            priority = priority_cycle[index - 1]
            age_days = RANDOM.randint(0, 45)
            created_at = _safe_now_minus(age_days, RANDOM.randint(0, 20))
            updated_at = created_at + timedelta(days=RANDOM.randint(0, max(0, min(age_days, 12))), hours=RANDOM.randint(1, 8))
            if updated_at > NOW:
                updated_at = NOW - timedelta(hours=RANDOM.randint(1, 12))
            score, level = _risk_for(priority, status, age_days)
            structure = structures[meta["structure"]]
            requester = requesters[city]
            title = f"Demo Paris Ouest #{index:03d} - {template[0]} - {city}"
            row = existing_requests.get(title)
            if row is None:
                row = Request(title=title, user_id=requester.id)
                db.session.add(row)
            row.description = f"{template[1]} Zone: {city}. Donnees de demonstration HelpChain, sans beneficiaire reel."
            row.message = row.description
            row.name = f"Demandeur demo {city}"
            row.email = f"demandeur.{index:03d}@helpchain.demo"
            row.phone = "+33 1 00 00 00 00"
            row.city = city
            row.region = "Ile-de-France"
            row.address_line = f"Secteur {city} {index:03d}"
            row.postcode = str(meta["postcode"])
            row.country = "France"
            row.location_text = f"{city}, {meta['postcode']}, France"
            row.normalized_address = row.location_text
            row.geocoding_status = "needs_review"
            row.status = status
            row.priority = priority
            row.category = template[2]
            row.source_channel = DEMO_SOURCE
            row.user_id = requester.id
            row.structure_id = structure.id
            row.owner_id = None
            row.owned_at = None
            row.latitude = float(meta["lat"]) + RANDOM.uniform(-0.01, 0.01)
            row.longitude = float(meta["lng"]) + RANDOM.uniform(-0.01, 0.01)
            row.risk_score = score
            row.risk_level = level
            row.risk_signals = _demo_payload(city=city, priority=priority, status=status)
            row.risk_last_updated = updated_at
            row.created_at = created_at
            row.updated_at = updated_at
            row.completed_at = updated_at if status == "done" else None
            row.is_archived = False
            row.deleted_at = None
            rows.append(row)
            if index % 5 == 0:
                _progress("requests_core_rows_ready", city=city, rows=len(rows), last_index=index)
            index += 1
        _progress("requests_core_city_ready", city=city, rows=len(rows))

    _progress("requests_core_flush_start", rows=len(rows))
    db.session.flush()
    _progress("requests_core_flush_done", rows=len(rows))
    return rows


def _seed_request_assignments(requests: list[Request], admins: dict[str, AdminUser]) -> int:
    count = 0
    for req in requests:
        title = req.title or ""
        try:
            index = int(title.split("#", 1)[1].split(" ", 1)[0])
        except Exception:
            index = req.id or 0
        owner = None
        if req.status in {"in_progress", "done"} or index % 3 == 0:
            owner = admins.get("ops.boulogne") if req.city == "Boulogne-Billancourt" else admins.get("ops.paris")
            if req.city == "Neuilly-sur-Seine":
                owner = admins.get("ops.neuilly")
        req.owner_id = owner.id if owner else None
        req.owned_at = req.updated_at if owner else None
        count += 1
    db.session.flush()
    return count


def _seed_request_activity(requests: list[Request], admins: dict[str, AdminUser]) -> int:
    actions = [
        ("created", "Demande creee depuis le canal demo."),
        ("assigned", "Responsable territorial assigne."),
        ("note_added", "Note interne ajoutee apres verification terrain."),
        ("escalated", "Point de vigilance remonte au pilotage."),
        ("resolved", "Action principale finalisee."),
        ("reopened", "Dossier rouvert apres nouvelle information."),
    ]
    count = 0
    actor_id = (admins.get("founder") or next(iter(admins.values()))).id
    for idx, req in enumerate(requests, start=1):
        planned = actions[: 2 + (idx % 4)]
        if req.status == "done":
            planned.append(actions[4])
        if idx % 17 == 0:
            planned.append(actions[5])
        for step, (action, text) in enumerate(planned, start=1):
            created_at = (req.created_at or NOW) + timedelta(hours=step * 8)
            if created_at > NOW:
                created_at = NOW - timedelta(hours=step)
            value = f"{DEMO_SOURCE} | {text} | step={step}"
            row = RequestActivity.query.filter_by(
                request_id=req.id,
                action=action,
                new_value=value,
            ).first()
            if row is None:
                row = RequestActivity(
                    request_id=req.id,
                    actor_admin_id=actor_id if action != "created" else None,
                    action=action,
                    new_value=value,
                    created_at=created_at,
                )
                db.session.add(row)
            row.created_at = created_at
            count += 1
    db.session.flush()
    return count


def _seed_cases(requests: list[Request], admins: dict[str, AdminUser]) -> list[Case]:
    selected = sorted(requests, key=lambda r: int(r.risk_score or 0), reverse=True)[:30]
    rows: list[Case] = []
    actor_id = (admins.get("founder") or next(iter(admins.values()))).id
    for idx, req in enumerate(selected, start=1):
        status = CASE_STATUSES[(idx - 1) % len(CASE_STATUSES)]
        row = Case.query.filter_by(request_id=req.id).first()
        if row is None:
            row = Case(request_id=req.id)
            db.session.add(row)
        row.request_id = req.id
        row.structure_id = req.structure_id
        row.owner_user_id = req.owner_id or actor_id
        row.status = status
        row.priority = req.priority or "normal"
        row.risk_score = req.risk_score
        row.latitude = req.latitude
        row.longitude = req.longitude
        row.created_at = req.created_at or NOW
        row.opened_at = row.created_at
        row.assigned_at = row.created_at + timedelta(hours=12)
        row.last_activity_at = req.updated_at or NOW
        row.updated_at = row.last_activity_at
        row.resolved_at = row.last_activity_at if status == "resolved" else None
        row.closed_at = None
        rows.append(row)
    db.session.flush()

    for idx, case in enumerate(rows, start=1):
        for event_type, message, offset in (
            ("case_created", "Dossier ouvert depuis une demande prioritaire.", 1),
            ("owner_assigned", "Responsable operationnel affecte.", 10),
            ("note_added", "Point de coordination ajoute au dossier.", 20),
        ):
            value = f"{message} ({DEMO_SOURCE})"
            row = CaseEvent.query.filter_by(case_id=case.id, event_type=event_type, message=value).first()
            if row is None:
                row = CaseEvent(
                    case_id=case.id,
                    actor_user_id=actor_id,
                    event_type=event_type,
                    message=value,
                    visibility="internal",
                    created_at=(case.created_at or NOW) + timedelta(hours=offset),
                )
                db.session.add(row)
            row.created_at = min((case.created_at or NOW) + timedelta(hours=offset), NOW)
        if case.status == "blocked":
            value = f"Blocage: attente retour partenaire institutionnel. ({DEMO_SOURCE})"
            if CaseEvent.query.filter_by(case_id=case.id, event_type="blocked", message=value).first() is None:
                db.session.add(CaseEvent(case_id=case.id, actor_user_id=actor_id, event_type="blocked", message=value))
        if case.status == "resolved":
            value = f"Solution confirmee et dossier stabilise. ({DEMO_SOURCE})"
            if CaseEvent.query.filter_by(case_id=case.id, event_type="case_resolved", message=value).first() is None:
                db.session.add(CaseEvent(case_id=case.id, actor_user_id=actor_id, event_type="case_resolved", message=value))
    db.session.flush()
    return rows


def _seed_professional_leads(admins: dict[str, AdminUser]) -> list[ProfessionalLead]:
    professions = [
        "Direction CCAS",
        "Responsable association",
        "Service municipal solidarites",
        "Coordinateur reseau sante",
        "Coordination autonomie",
    ]
    orgs = [
        "CCAS Boulogne-Billancourt",
        "Association Solidarite Paris Ouest",
        "Service Seniors Hauts-de-Seine",
        "Centre Social Neuilly",
        "Aide Familles Levallois",
    ]
    cities = list(CITY_META)
    owner_id = (admins.get("founder") or next(iter(admins.values()))).id
    rows = []
    for idx in range(1, 21):
        city = cities[(idx - 1) % len(cities)]
        organization = orgs[(idx - 1) % len(orgs)]
        email = f"lead.{idx:02d}.westparis@helpchain.demo"
        row = ProfessionalLead.query.filter_by(email=email).first()
        if row is None:
            row = ProfessionalLead(email=email, profession=professions[(idx - 1) % len(professions)])
            db.session.add(row)
        row.full_name = f"Contact demo {organization}"
        row.phone = "+33 1 00 00 00 00"
        row.city = city
        row.profession = professions[(idx - 1) % len(professions)]
        row.organization = organization
        row.availability = ["Cette semaine", "Sous 48h", "Disponible pour demo", "Pilotage en discussion"][idx % 4]
        row.message = "Demande demo: besoin de structurer les suivis, les relances et le pilotage territorial."
        row.source = DEMO_SOURCE
        row.locale = "fr"
        row.ip = f"10.92.0.{idx}"
        row.user_agent = "HelpChain demo seed"
        row.owner_admin_id = owner_id
        row.status = LEAD_STATUSES[(idx - 1) % len(LEAD_STATUSES)]
        row.notes = f"{DEMO_SOURCE} | Signal commercial demo, segment={row.profession}, ville={city}."
        row.contacted_at = _safe_now_minus(RANDOM.randint(0, 18)) if row.status != "new" else None
        row.first_followup_sent_at = _safe_now_minus(RANDOM.randint(1, 14)) if idx % 3 == 0 else None
        row.second_followup_sent_at = _safe_now_minus(RANDOM.randint(1, 10)) if idx % 7 == 0 else None
        row.last_touched_at = _safe_now_minus(RANDOM.randint(0, 12))
        row.last_touched_by_admin_id = owner_id
        if _has_column("professional_leads", "next_action_at"):
            row.next_action_at = NOW + timedelta(days=(idx % 6) - 1)
            row.next_action_note = "Relancer pour caler une demo" if idx % 2 else "Envoyer proposition pilote"
        rows.append(row)
    db.session.flush()
    return rows


def _seed_access_requests(admins: dict[str, AdminUser]) -> list[OrganizationAccessRequest]:
    scenarios = [
        ("Centre social", "souhaite tester un espace de coordination pour les familles suivies."),
        ("Mairie", "cherche un outil de pilotage entre accueil, CCAS et partenaires."),
        ("Association", "veut fluidifier les benevoles, relances et orientations."),
    ]
    rows = []
    owner_id = (admins.get("founder") or next(iter(admins.values()))).id
    cities = list(CITY_META)
    for idx in range(1, 13):
        city = cities[(idx - 1) % len(cities)]
        org_type, need = scenarios[(idx - 1) % len(scenarios)]
        organization = f"{org_type} Demo {city} #{idx:02d}"
        email = f"access.{idx:02d}.westparis@helpchain.demo"
        row = OrganizationAccessRequest.query.filter_by(email=email).first()
        if row is None:
            row = OrganizationAccessRequest(
                organization_name=organization,
                contact_name=f"Responsable demo {city}",
                email=email,
            )
            db.session.add(row)
        row.organization_name = organization
        row.contact_name = f"Responsable demo {city}"
        row.phone = "+33 1 00 00 00 00"
        row.city = city
        row.org_type = org_type.lower().replace(" ", "_")
        row.estimated_users = [8, 15, 25, 40][idx % 4]
        row.message = f"{org_type} a demande un acces pilote: {need}"
        row.status = ACCESS_STATUSES[(idx - 1) % len(ACCESS_STATUSES)]
        row.reviewed_by_admin_id = owner_id if row.status in {"reviewed", "approved", "need_info"} else None
        row.reviewed_at = _safe_now_minus(RANDOM.randint(0, 10)) if row.reviewed_by_admin_id else None
        row.internal_notes = f"{DEMO_SOURCE} | Audience avant conversion rattachee au parcours demo_west_paris_org_{idx:02d}."
        if _has_column("organization_access_requests", "next_action_at"):
            row.next_action_at = NOW + timedelta(days=(idx % 5) - 1)
            row.next_action_note = "Verifier besoin pilote" if row.status == "need_info" else "Preparer validation interne"
        row.created_at = _safe_now_minus(RANDOM.randint(0, 25))
        row.updated_at = row.reviewed_at or row.created_at
        rows.append(row)
    db.session.flush()
    return rows


def _seed_notification_jobs(structures: dict[str, Structure]) -> list[NotificationJob]:
    rows = []
    slugs = list(structures)
    for idx in range(1, 36):
        status = NOTIFICATION_STATUSES[(idx - 1) % len(NOTIFICATION_STATUSES)]
        channel = "email" if idx % 4 else "system"
        subject = f"Demo Paris Ouest notification #{idx:02d}"
        recipient = "system" if channel == "system" else f"ops.{idx:02d}@helpchain.demo"
        row = NotificationJob.query.filter_by(subject=subject, recipient=recipient).first()
        if row is None:
            row = NotificationJob(channel=channel, event_type="demo_operational_signal", recipient=recipient, subject=subject)
            db.session.add(row)
        created_at = _safe_now_minus(RANDOM.randint(0, 14), RANDOM.randint(0, 20))
        row.channel = channel
        row.event_type = ["request_followup", "case_alert", "pilotage_digest", "lead_reminder"][idx % 4]
        row.recipient = recipient
        row.subject = subject
        row.payload_json = _demo_payload(index=idx, reason="west_paris_dashboard_activity")
        row.status = status
        row.attempts = {"pending": 0, "processing": 1, "retry": 2, "failed": 4, "sent": 1}[status]
        row.max_attempts = 5
        row.next_retry_at = NOW + timedelta(hours=idx % 12) if status in {"pending", "retry"} else None
        row.locked_at = NOW - timedelta(minutes=10) if status == "processing" else None
        row.processed_at = created_at if status in {"failed", "sent"} else None
        row.sent_at = created_at if status == "sent" else None
        row.last_error = "Erreur demo: partenaire indisponible" if status in {"retry", "failed"} else None
        row.structure_id = structures[slugs[idx % len(slugs)]].id
        row.created_at = created_at
        row.updated_at = created_at
        rows.append(row)
    db.session.flush()
    return rows


def _seed_audience() -> tuple[int, int]:
    AnalyticsEvent.query.filter(AnalyticsEvent.user_session.like(f"{SESSION_PREFIX}%")).delete(synchronize_session=False)
    UserBehavior.query.filter(UserBehavior.session_id.like(f"{SESSION_PREFIX}%")).delete(synchronize_session=False)
    db.session.flush()

    sessions = []
    cities = list(CITY_META)
    sources = list(REFERRERS)
    for idx in range(1, 51):
        city = cities[(idx - 1) % len(cities)]
        source = sources[idx % len(sources)]
        page_count = 2 + (idx % 7)
        if idx <= 12:
            page_count += 3
        session_id = f"{SESSION_PREFIX}{idx:03d}"
        first_seen = _safe_now_minus(RANDOM.randint(0, 7), RANDOM.randint(0, 18))
        sequence = ["/"]
        sequence.extend(RANDOM.choice(PAGES[1:]) for _ in range(page_count - 1))
        if idx <= 15 and "/demander-acces" not in sequence:
            sequence.append("/demander-acces")
        if idx % 5 == 0 and "/contact" not in sequence:
            sequence.append("/contact")
        sessions.append((session_id, city, source, first_seen, sequence))

    event_count = 0
    for idx, (session_id, city, source, first_seen, sequence) in enumerate(sessions, start=1):
        last_seen = first_seen
        for step, page in enumerate(sequence, start=1):
            event_time = first_seen + timedelta(minutes=step * RANDOM.randint(2, 9))
            if idx <= 10 and step > len(sequence) // 2:
                event_time = NOW - timedelta(hours=RANDOM.randint(0, 22), minutes=step * 3)
            last_seen = event_time
            db.session.add(
                AnalyticsEvent(
                    event_type="page_view",
                    event_category="audience",
                    event_action="view",
                    event_label="high_intent" if page != "/" else "public",
                    event_value=idx,
                    user_session=session_id,
                    user_type="guest",
                    user_ip=f"10.92.{idx // 255}.{idx % 255}",
                    user_agent="HelpChain west Paris demo browser",
                    page_url=page,
                    page_title=f"HelpChain {page}",
                    referrer=REFERRERS[source],
                    load_time=round(RANDOM.uniform(0.4, 1.8), 2),
                    screen_resolution=["1440x900", "1920x1080", "1366x768", "390x844"][idx % 4],
                    device_type=["desktop", "desktop", "mobile", "tablet"][idx % 4],
                    created_at=event_time,
                    updated_at=event_time,
                )
            )
            event_count += 1
            if event_count >= 250:
                break
        behavior = UserBehavior(
            session_id=session_id,
            user_type="guest",
            ip_address=f"10.92.{idx // 255}.{idx % 255}",
            user_agent="HelpChain west Paris demo browser",
            device_info=["desktop", "desktop", "mobile", "tablet"][idx % 4],
            location=f"{city}, France",
            session_start=first_seen,
            last_activity=last_seen,
            total_time_spent=max(90, len(sequence) * RANDOM.randint(45, 140)),
            pages_visited=len(sequence),
            entry_page=sequence[0],
            exit_page=sequence[-1],
            bounce_rate=len(sequence) <= 1,
            conversion_action="organization_access_request" if "/demander-acces" in sequence and idx <= 12 else None,
            pages_sequence=json.dumps(sequence, ensure_ascii=False),
        )
        db.session.add(behavior)
        if event_count >= 250:
            break

    db.session.flush()
    return event_count, len(sessions)


def seed() -> dict[str, int]:
    counts: dict[str, int] = {}
    if os.getenv("HC_RESET_DEMO") == "1":
        _run_block("reset_demo_rows", _reset_demo_rows)
        counts["reset_demo_rows"] = 1

    structures, admins = _run_block("foundation_structures_admins", _seed_foundation)
    _commit_block("foundation_structures_admins", counts, structures_demo=len(structures), ops_users_demo=len(OPS_USERS))

    requests = _run_block("requests_core", lambda: _seed_requests_core(structures))
    _commit_block("requests_core", counts, requests_demo=len(requests))

    assignment_count = _run_block("requests_assignments", lambda: _seed_request_assignments(requests, admins))
    _commit_block("requests_assignments", counts, requests_assignments_demo=assignment_count)

    activity_count = _run_block("requests_activity", lambda: _seed_request_activity(requests, admins))
    _commit_block("requests_activity", counts, request_activity_demo=activity_count)

    cases = _run_block("cases", lambda: _seed_cases(requests, admins))
    _commit_block("cases", counts, cases_demo=len(cases))

    leads = _run_block("professional_leads", lambda: _seed_professional_leads(admins))
    _commit_block("professional_leads", counts, professional_leads_demo=len(leads))

    access_requests = _run_block("organization_access_requests", lambda: _seed_access_requests(admins))
    _commit_block(
        "organization_access_requests",
        counts,
        organization_access_requests_demo=len(access_requests),
    )

    notifications = _run_block("notification_jobs", lambda: _seed_notification_jobs(structures))
    _commit_block("notification_jobs", counts, notification_jobs_demo=len(notifications))

    analytics_events, behavior_sessions = _run_block("audience_telemetry", _seed_audience)
    _commit_block(
        "audience_telemetry",
        counts,
        analytics_events_demo=analytics_events,
        user_behaviors_demo=behavior_sessions,
    )

    return counts


def main() -> int:
    with app.app_context():
        _configure_db_for_seed()
        required = {
            "admin_users",
            "structures",
            "users",
            "requests",
            "request_activities",
            "cases",
            "case_events",
            "professional_leads",
            "organization_access_requests",
            "notification_jobs",
            "analytics_events",
            "user_behaviors",
        }
        missing = sorted(required - _tables())
        if missing:
            print(json.dumps({"ok": False, "missing_tables": missing}, indent=2))
            return 1
        missing_columns = []
        for table, columns in {
            "professional_leads": ("next_action_at", "next_action_note"),
            "organization_access_requests": ("next_action_at", "next_action_note"),
        }.items():
            for column in columns:
                if not _has_column(table, column):
                    missing_columns.append(f"{table}.{column}")
        if missing_columns:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "missing_columns": missing_columns,
                        "next_step": "Run migrations before seeding: flask db upgrade",
                    },
                    indent=2,
                )
            )
            return 1
        try:
            counts = seed()
        except OperationalError as exc:
            db.session.rollback()
            print(
                json.dumps(
                    {
                        "ok": False,
                        "source": DEMO_SOURCE,
                        "error_type": "database_operational_error",
                        "fast_fail": _is_fast_fail_db_error(exc),
                        "error": str(exc),
                        "db_state": _sqlite_db_state(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                flush=True,
            )
            return 1
        except TimeoutError as exc:
            db.session.rollback()
            print(
                json.dumps(
                    {
                        "ok": False,
                        "source": DEMO_SOURCE,
                        "error_type": "seed_timeout_guard",
                        "error": str(exc),
                        "db_state": _sqlite_db_state(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                flush=True,
            )
            return 1
        city_counts = Counter(row.city for row in Request.query.filter_by(source_channel=DEMO_SOURCE).all())
        print(
            json.dumps(
                {
                    "ok": True,
                    "source": DEMO_SOURCE,
                    "reset": os.getenv("HC_RESET_DEMO") == "1",
                    "counts": counts,
                    "requests_by_city": dict(city_counts),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
