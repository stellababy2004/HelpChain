#!/usr/bin/env python
from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from werkzeug.security import generate_password_hash


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.appy import app
from backend.extensions import db
from backend.models import (
    AdminUser,
    Assignment,
    Intervenant,
    Request,
    Structure,
    StructureService,
    User,
)


LOCAL_DB_URI = "sqlite:///C:/dev/HelpChain/instance/hc_local_dev.db"
LOCAL_BASE_URL = "http://127.0.0.1:5005"
CCAS_STRUCTURE_ID = 2
CCAS_SLUG = "ccas-boulogne-billancourt"
CCAS_NAME = "CCAS Boulogne-Billancourt"
ADMIN_USERNAME = os.getenv("HC_LOCAL_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("HC_LOCAL_ADMIN_PASSWORD", "Admin123!")
DEMO_DOMAIN = "helpchain.local"


SERVICES = (
    ("food", "Aide alimentaire"),
    ("admin", "Accompagnement administratif"),
    ("housing", "Logement et hébergement"),
    ("legal", "Accès aux droits"),
    ("health", "Coordination santé"),
    ("orientation", "Orientation partenaire"),
)

INTERVENANTS = (
    ("Amélie Durand", "social_worker", "available", "amelie.durand"),
    ("Karim Benali", "coordinator", "busy", "karim.benali"),
    ("Sophie Martin", "psychologist", "in_intervention", "sophie.martin"),
    ("Lucas Petit", "field_referent", "available", "lucas.petit"),
    ("Nadia Leroy", "partner_association", "available", "nadia.leroy"),
    ("Thomas Bernard", "health_professional", "paused", "thomas.bernard"),
    ("Claire Moreau", "legal_advisor", "available", "claire.moreau"),
    ("Mehdi Rousseau", "mediator", "busy", "mehdi.rousseau"),
    ("Inès Garnier", "social_worker", "available", "ines.garnier"),
    ("Julien Lefèvre", "field_referent", "unavailable", "julien.lefevre"),
)

STATUSES = ("new", "pending", "in_progress", "closed")
PRIORITIES = ("normal", "élevée", "critique")
CATEGORIES = ("food", "admin", "housing", "legal", "health", "orientation")
REQUEST_TOPICS = (
    "Aide alimentaire urgente",
    "Dossier administratif bloqué",
    "Orientation logement",
    "Accès aux droits",
    "Suivi santé",
    "Coordination partenaire",
    "Situation familiale en attente",
    "Relance de justificatifs",
    "Appui mobilité",
    "Evaluation sociale rapide",
)


def now_utc_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def normalize_uri(value: str | None) -> str:
    text = (value or "").strip().replace("\\", "/")
    if text.lower().startswith("sqlite:///"):
        return "sqlite:///" + text[10:].lower()
    return text.lower()


def assert_local_only() -> None:
    public_base_url = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    database_url = (os.getenv("DATABASE_URL") or "").strip()
    local_dev = (os.getenv("HC_LOCAL_DEV") or "").strip() == "1"

    if not local_dev:
        raise RuntimeError("Refusing to seed: HC_LOCAL_DEV must be 1.")
    if public_base_url != LOCAL_BASE_URL:
        raise RuntimeError(
            f"Refusing to seed: PUBLIC_BASE_URL must be {LOCAL_BASE_URL!r}, got {public_base_url!r}."
        )
    if normalize_uri(database_url) != normalize_uri(LOCAL_DB_URI):
        raise RuntimeError(
            f"Refusing to seed: DATABASE_URL must point to {LOCAL_DB_URI!r}, got {database_url!r}."
        )


def ensure_required_columns() -> None:
    bind = db.session.get_bind()
    if hasattr(bind, "exec_driver_sql"):
        rows = bind.exec_driver_sql("pragma table_info(intervenants)").fetchall()
    else:
        with bind.connect() as conn:
            rows = conn.exec_driver_sql("pragma table_info(intervenants)").fetchall()
    columns = {row[1] for row in rows}
    missing = {"availability", "internal_notes"} - columns
    if missing:
        raise RuntimeError(
            "Local DB is missing intervenant columns "
            + ", ".join(sorted(missing))
            + ". Run .\\.venv\\Scripts\\python.exe -m flask db upgrade first."
        )


def ensure_admin() -> AdminUser:
    admin = AdminUser.query.filter_by(username=ADMIN_USERNAME).first()
    if admin is None:
        admin = AdminUser(
            username=ADMIN_USERNAME,
            email=f"{ADMIN_USERNAME}@localhost",
            role="superadmin",
            is_active=True,
        )
        db.session.add(admin)
    admin.email = f"{ADMIN_USERNAME}@localhost"
    admin.role = "superadmin"
    admin.structure_id = None
    admin.is_active = True
    if hasattr(admin, "mfa_enabled"):
        admin.mfa_enabled = False
    if hasattr(admin, "must_change_password"):
        admin.must_change_password = False
    admin.set_password(ADMIN_PASSWORD)
    return admin


def ensure_structure(*, structure_id: int | None, name: str, slug: str) -> Structure:
    existing_slug = Structure.query.filter_by(slug=slug).first()
    if existing_slug is not None and structure_id is not None and existing_slug.id != structure_id:
        existing_slug.slug = f"{slug}-legacy-{existing_slug.id}"

    structure = db.session.get(Structure, structure_id) if structure_id is not None else None
    if structure is None:
        structure = Structure.query.filter_by(slug=slug).first()
    if structure is None:
        structure = Structure(id=structure_id, name=name, slug=slug, status="active")
        db.session.add(structure)
        db.session.flush()

    structure.name = name
    structure.slug = slug
    structure.status = "active"
    return structure


def ensure_structures() -> tuple[Structure, Structure]:
    default = Structure.query.filter_by(slug="default").first()
    if default is None:
        default = Structure(name="Default", slug="default", status="active")
        db.session.add(default)
        db.session.flush()
    default.name = "Default"
    default.status = "active"

    ccas = ensure_structure(structure_id=CCAS_STRUCTURE_ID, name=CCAS_NAME, slug=CCAS_SLUG)
    return default, ccas


def ensure_services(structure: Structure) -> dict[str, StructureService]:
    services: dict[str, StructureService] = {}
    for code, name in SERVICES:
        service = StructureService.query.filter_by(structure_id=structure.id, code=code).first()
        if service is None:
            service = StructureService(structure_id=structure.id, code=code, name=name, is_active=True)
            db.session.add(service)
        service.name = name
        service.is_active = True
        services[code] = service
    db.session.flush()
    return services


def ensure_requester(index: int, structure: Structure) -> User:
    username = f"local_demo_requester_{index:02d}"
    user = User.query.filter_by(username=username).first()
    if user is None:
        user = User(
            username=username,
            email=f"{username}@{DEMO_DOMAIN}",
            password_hash=generate_password_hash("DemoUser123!"),
            role="requester",
            is_active=True,
        )
        db.session.add(user)
    user.email = f"{username}@{DEMO_DOMAIN}"
    user.role = "requester"
    user.is_active = True
    user.structure_id = structure.id
    return user


def ensure_structure_admin(structure: Structure) -> AdminUser:
    username = "ccas_boulogne_admin"
    admin = AdminUser.query.filter_by(username=username).first()
    if admin is None:
        admin = AdminUser(
            username=username,
            email=f"{username}@{DEMO_DOMAIN}",
            role="admin",
            is_active=True,
            structure_id=structure.id,
        )
        db.session.add(admin)
    admin.email = f"{username}@{DEMO_DOMAIN}"
    admin.role = "admin"
    admin.structure_id = structure.id
    admin.is_active = True
    admin.set_password(ADMIN_PASSWORD)
    return admin


def ensure_intervenants(structure: Structure) -> list[Intervenant]:
    rows: list[Intervenant] = []
    for name, actor_type, availability, email_name in INTERVENANTS:
        email = f"{email_name}@{DEMO_DOMAIN}"
        intervenant = Intervenant.query.filter_by(email=email).first()
        if intervenant is None:
            intervenant = Intervenant(email=email, structure_id=structure.id)
            db.session.add(intervenant)
        intervenant.structure_id = structure.id
        intervenant.name = name
        intervenant.actor_type = actor_type
        intervenant.phone = f"06 70 2{len(rows):02d} {len(rows):02d} {len(rows) + 10:02d}".replace(" ", "")
        intervenant.location = "Boulogne-Billancourt"
        intervenant.availability = availability
        intervenant.is_active = availability != "unavailable"
        intervenant.internal_notes = "Profil local de démonstration opérationnelle."
        rows.append(intervenant)
    db.session.flush()
    return rows


def request_spec(index: int) -> dict[str, object]:
    status = STATUSES[index % len(STATUSES)]
    priority = PRIORITIES[index % len(PRIORITIES)]
    category = CATEGORIES[index % len(CATEGORIES)]
    stale = index % 5 in {1, 3}
    owner_missing = index % 4 == 0
    days_ago = 5 + (index % 8) if stale else index % 3
    updated_days_ago = 4 + (index % 7) if stale else index % 2
    return {
        "title": f"DEMO OPS {index + 1:02d} - {REQUEST_TOPICS[index % len(REQUEST_TOPICS)]}",
        "status": status,
        "priority": priority,
        "category": category,
        "owner_missing": owner_missing,
        "created_at": now_utc_naive() - timedelta(days=days_ago, hours=index % 7),
        "updated_at": now_utc_naive() - timedelta(days=updated_days_ago, hours=index % 5),
        "completed_at": now_utc_naive() - timedelta(days=1) if status == "closed" else None,
        "service_code": category if category in {code for code, _name in SERVICES} else "orientation",
    }


def ensure_requests(
    *,
    structure: Structure,
    services: dict[str, StructureService],
    owner: AdminUser,
    requesters: list[User],
) -> list[Request]:
    rows: list[Request] = []
    for index in range(30):
        spec = request_spec(index)
        title = str(spec["title"])
        req = Request.query.filter_by(title=title).first()
        if req is None:
            req = Request(title=title, user_id=requesters[index % len(requesters)].id)
            db.session.add(req)
        service = services.get(str(spec["service_code"])) or services["orientation"]
        req.structure_id = structure.id
        req.user_id = requesters[index % len(requesters)].id
        req.service_id = service.id
        req.title = title
        req.description = (
            "Situation locale de démonstration pour tester la file de traitement, "
            "les relances et la coordination terrain."
        )
        req.name = f"Personne accompagnée {index + 1:02d}"
        req.email = f"beneficiaire{index + 1:02d}@{DEMO_DOMAIN}"
        req.phone = f"06{index + 10:08d}"
        req.city = "Boulogne-Billancourt"
        req.region = "Hauts-de-Seine"
        req.location_text = "Boulogne-Billancourt"
        req.address_line = f"{10 + index} rue de la Demo"
        req.postcode = "92100"
        req.country = "France"
        req.message = "Besoin de suivi actif et d'une coordination locale lisible."
        req.status = str(spec["status"])
        req.priority = str(spec["priority"])
        req.category = str(spec["category"])
        req.source_channel = "local_operational_demo"
        req.created_at = spec["created_at"]
        req.updated_at = spec["updated_at"]
        req.completed_at = spec["completed_at"]
        req.owner_id = None if spec["owner_missing"] or req.status == "new" else owner.id
        req.owned_at = None if req.owner_id is None else req.updated_at
        req.is_archived = False
        req.deleted_at = None
        rows.append(req)
    db.session.flush()
    return rows


def ensure_assignments(
    *,
    requests: list[Request],
    intervenants: list[Intervenant],
    structure: Structure,
    admin: AdminUser,
) -> None:
    for index, req in enumerate(requests):
        if req.status == "closed" or index % 4 == 0:
            continue
        intervenant = intervenants[index % len(intervenants)]
        assignment = Assignment.query.filter_by(
            request_id=req.id,
            intervenant_id=intervenant.id,
        ).first()
        if assignment is None:
            assignment = Assignment(
                request_id=req.id,
                intervenant_id=intervenant.id,
                structure_id=structure.id,
            )
            db.session.add(assignment)
        assignment.structure_id = structure.id
        assignment.assigned_by_admin_id = admin.id
        assignment.assigned_at = req.updated_at or req.created_at
        assignment.status = "active" if req.status != "pending" else "pending"
        assignment.notes = "Affectation locale de démonstration."


def print_summary(structure: Structure) -> None:
    requests_total = Request.query.count()
    requests_ccas = Request.query.filter_by(structure_id=structure.id).count()
    structures_total = Structure.query.count()
    intervenants_total = Intervenant.query.filter_by(structure_id=structure.id).count()
    services_total = StructureService.query.filter_by(structure_id=structure.id).count()
    unassigned = Request.query.filter_by(structure_id=structure.id, owner_id=None).count()
    stale_cutoff = now_utc_naive() - timedelta(hours=72)
    stale = (
        Request.query.filter(Request.structure_id == structure.id)
        .filter(Request.updated_at <= stale_cutoff)
        .count()
    )
    print("Local operational demo ready")
    print(f"requests_total={requests_total}")
    print(f"requests_structure_{structure.id}={requests_ccas}")
    print(f"structures_total={structures_total}")
    print(f"intervenants_structure_{structure.id}={intervenants_total}")
    print(f"services_structure_{structure.id}={services_total}")
    print(f"unassigned_structure_{structure.id}={unassigned}")
    print(f"stale_over_72h_structure_{structure.id}={stale}")
    first_intervenant = Intervenant.query.filter_by(structure_id=structure.id).order_by(Intervenant.id.asc()).first()
    if first_intervenant is not None:
        print(f"sample_intervenant_global=/admin/intervenants/{first_intervenant.id}")
        print(
            f"sample_intervenant_scoped=/admin/structures/{structure.id}/intervenants/{first_intervenant.id}"
        )


def main() -> int:
    with app.app_context():
        assert_local_only()
        ensure_required_columns()
        ensure_admin()
        _default, ccas = ensure_structures()
        services = ensure_services(ccas)
        ccas_admin = ensure_structure_admin(ccas)
        requesters = [ensure_requester(index, ccas) for index in range(6)]
        intervenants = ensure_intervenants(ccas)
        requests = ensure_requests(
            structure=ccas,
            services=services,
            owner=ccas_admin,
            requesters=requesters,
        )
        ensure_assignments(
            requests=requests,
            intervenants=intervenants,
            structure=ccas,
            admin=ccas_admin,
        )
        db.session.commit()
        print_summary(ccas)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
