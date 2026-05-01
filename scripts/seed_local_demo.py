#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import inspect


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.appy import app
from backend.extensions import db
from backend.models import (
    AdminAuditEvent,
    AdminLoginAttempt,
    AdminUser,
    Assignment,
    Intervenant,
    NotificationJob,
    Request,
    RequestActivity,
    RequestLog,
    RequestMetric,
    Structure,
    StructureService,
    User,
    Volunteer,
)
from backend.helpchain_backend.src.models import (
    Case,
    CaseCollaborator,
    CaseEvent,
    CaseParticipant,
    OrganizationAccessRequest,
    ProfessionalLead,
    ProfessionalLeadActivity,
)


DEMO_MARKER = "[LOCAL_DEMO_SEED]"
# Local demo defaults only; override via environment variables in local development.
DEFAULT_ADMIN_PASSWORD = os.getenv("HC_DEMO_ADMIN_PASSWORD", "change-me-local-admin")
DEFAULT_USER_PASSWORD = os.getenv("HC_DEMO_USER_PASSWORD", "change-me-local-user")
DEFAULT_LOCAL_BASE_URL = "http://127.0.0.1:5000"
DEMO_EMAIL_DOMAIN = "helpchain.local"


def now_utc_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def slugify(value: str) -> str:
    normalized = (
        value.lower()
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("à", "a")
        .replace("î", "i")
        .replace("ï", "i")
        .replace("ô", "o")
        .replace("ù", "u")
        .replace("û", "u")
        .replace("ç", "c")
        .replace("'", "-")
        .replace("/", "-")
    )
    out = []
    for char in normalized:
        if char.isalnum():
            out.append(char)
        elif char in {" ", "-", "_"}:
            out.append("-")
    slug = "".join(out).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "demo"


def demo_tag(label: str) -> str:
    return f"{DEMO_MARKER} {label}".strip()


@dataclass(frozen=True)
class DemoAdminSpec:
    username: str
    email: str
    role: str
    structure_slug: str | None
    label: str


@dataclass(frozen=True)
class DemoUserSpec:
    username: str
    email: str
    role: str
    structure_slug: str
    full_name: str


@dataclass(frozen=True)
class DemoStructureSpec:
    name: str
    slug: str
    status: str = "active"


@dataclass(frozen=True)
class DemoRequestSpec:
    key: str
    structure_slug: str
    user_username: str
    owner_admin_username: str | None
    service_code: str | None
    title: str
    description: str
    name: str
    email: str
    phone: str
    city: str
    postcode: str
    address_line: str
    status: str
    priority: str
    category: str
    source_channel: str
    created_days_ago: int
    assigned_days_ago: int | None = None
    completed_days_ago: int | None = None


@dataclass(frozen=True)
class DemoProfessionalLeadSpec:
    key: str
    email: str
    full_name: str
    phone: str
    city: str
    profession: str
    organization: str
    availability: str
    message: str
    source: str
    status: str
    notes: str
    owner_admin_username: str | None


@dataclass(frozen=True)
class DemoOrgAccessRequestSpec:
    key: str
    organization_name: str
    contact_name: str
    email: str
    phone: str
    city: str
    org_type: str
    estimated_users: int
    message: str
    status: str
    internal_notes: str


DEMO_STRUCTURES = [
    DemoStructureSpec(name="CCAS de Nanterre", slug="ccas-nanterre"),
    DemoStructureSpec(name="Association Solidarite Paris", slug="association-solidarite-paris"),
    DemoStructureSpec(name="Centre Social Boulogne", slug="centre-social-boulogne"),
]

DEMO_ADMINS = [
    DemoAdminSpec(
        username="admin",
        email=f"admin@{DEMO_EMAIL_DOMAIN}",
        role="superadmin",
        structure_slug=None,
        label="Superadministrateur local",
    ),
    DemoAdminSpec(
        username="coord_nanterre",
        email=f"coord.nanterre@{DEMO_EMAIL_DOMAIN}",
        role="admin",
        structure_slug="ccas-nanterre",
        label="Coordinatrice Nanterre",
    ),
    DemoAdminSpec(
        username="ops_demo",
        email=f"ops.demo@{DEMO_EMAIL_DOMAIN}",
        role="ops",
        structure_slug="association-solidarite-paris",
        label="Operateur demo",
    ),
    DemoAdminSpec(
        username="readonly_demo",
        email=f"readonly.demo@{DEMO_EMAIL_DOMAIN}",
        role="readonly",
        structure_slug="centre-social-boulogne",
        label="Lecteur demo",
    ),
]

DEMO_USERS = [
    DemoUserSpec(
        username="requester_nanterre",
        email=f"requester.nanterre@{DEMO_EMAIL_DOMAIN}",
        role="requester",
        structure_slug="ccas-nanterre",
        full_name="Lucie Martin",
    ),
    DemoUserSpec(
        username="requester_paris",
        email=f"requester.paris@{DEMO_EMAIL_DOMAIN}",
        role="requester",
        structure_slug="association-solidarite-paris",
        full_name="Karim Bensalem",
    ),
    DemoUserSpec(
        username="requester_boulogne",
        email=f"requester.boulogne@{DEMO_EMAIL_DOMAIN}",
        role="requester",
        structure_slug="centre-social-boulogne",
        full_name="Claire Roche",
    ),
    DemoUserSpec(
        username="professional_coordination",
        email=f"pro.coordination@{DEMO_EMAIL_DOMAIN}",
        role="professional",
        structure_slug="ccas-nanterre",
        full_name="Sophie Bernard",
    ),
]

DEMO_REQUESTS = [
    DemoRequestSpec(
        key="urgent_housing_nanterre",
        structure_slug="ccas-nanterre",
        user_username="requester_nanterre",
        owner_admin_username="coord_nanterre",
        service_code="housing",
        title="Hebergement d'urgence apres expulsion imminente",
        description=(
            "Signalement institutionnel transmis par le CCAS. Menace d'expulsion sous 48h, "
            "presence de deux enfants, besoin d'orientation immediate et coordination logement."
        ),
        name="Mme Nadia Khelifi",
        email="nadia.khelifi.demo@helpchain.local",
        phone="06 42 10 22 31",
        city="Nanterre",
        postcode="92000",
        address_line="12 rue Salvador Allende",
        status="new",
        priority="critical",
        category="logement",
        source_channel="admin_demo_seed",
        created_days_ago=0,
    ),
    DemoRequestSpec(
        key="rights_access_paris",
        structure_slug="association-solidarite-paris",
        user_username="requester_paris",
        owner_admin_username="ops_demo",
        service_code="legal",
        title="Qualification dossier acces aux droits",
        description=(
            "Premiere evaluation effectuee par l'association. Besoin d'accompagnement CAF, "
            "domiciliation et ouverture des droits maladie."
        ),
        name="M. Reda Meftah",
        email="reda.meftah.demo@helpchain.local",
        phone="06 74 22 19 03",
        city="Paris",
        postcode="75019",
        address_line="7 avenue Jean Jaures",
        status="qualified",
        priority="high",
        category="acces_aux_droits",
        source_channel="admin_demo_seed",
        created_days_ago=2,
        assigned_days_ago=1,
    ),
    DemoRequestSpec(
        key="food_assigned_boulogne",
        structure_slug="centre-social-boulogne",
        user_username="requester_boulogne",
        owner_admin_username="readonly_demo",
        service_code="food",
        title="Aide alimentaire attribuee au partenaire local",
        description=(
            "Menage monoparental en tension budgetaire. Dossier deja qualifie, attribution "
            "d'un relais de distribution et verification des droits complementaires."
        ),
        name="Mme Laura Petit",
        email="laura.petit.demo@helpchain.local",
        phone="07 88 31 44 15",
        city="Boulogne-Billancourt",
        postcode="92100",
        address_line="25 boulevard Jean Jaures",
        status="assigned",
        priority="standard",
        category="aide_alimentaire",
        source_channel="admin_demo_seed",
        created_days_ago=4,
        assigned_days_ago=2,
    ),
    DemoRequestSpec(
        key="medical_followup_nanterre",
        structure_slug="ccas-nanterre",
        user_username="professional_coordination",
        owner_admin_username="coord_nanterre",
        service_code="health",
        title="Coordination medico-sociale en cours",
        description=(
            "Personne isolee avec rupture de soins et fatigue importante. Suivi en cours "
            "avec infirmiere liberale et travailleur social de secteur."
        ),
        name="M. Philippe Garnier",
        email="philippe.garnier.demo@helpchain.local",
        phone="06 51 12 63 80",
        city="Nanterre",
        postcode="92000",
        address_line="4 place Gabriel Peri",
        status="in_progress",
        priority="urgent",
        category="sante",
        source_channel="admin_demo_seed",
        created_days_ago=6,
        assigned_days_ago=5,
    ),
    DemoRequestSpec(
        key="closed_housing_paris",
        structure_slug="association-solidarite-paris",
        user_username="requester_paris",
        owner_admin_username="ops_demo",
        service_code="housing",
        title="Accompagnement logement cloture",
        description=(
            "Demande finalisee apres mise a l'abri et ouverture des aides mobilisables. "
            "Cloture avec compte rendu institutionnel transmis."
        ),
        name="Mme Amina Sahnoune",
        email="amina.sahnoune.demo@helpchain.local",
        phone="07 63 88 11 25",
        city="Paris",
        postcode="75018",
        address_line="14 rue Ordener",
        status="done",
        priority="standard",
        category="logement",
        source_channel="admin_demo_seed",
        created_days_ago=12,
        assigned_days_ago=10,
        completed_days_ago=3,
    ),
]

DEMO_PROFESSIONAL_LEADS = [
    DemoProfessionalLeadSpec(
        key="lead_social_worker",
        email="sarah.leclerc.demo@helpchain.local",
        full_name="Sarah Leclerc",
        phone="06 22 11 33 44",
        city="Nanterre",
        profession="Travailleur social",
        organization="CCAS de Nanterre",
        availability="2 demi-journees par semaine",
        message="Souhaite rejoindre un dispositif de coordination locale pour les situations complexes.",
        source="professional_directory",
        status="qualified",
        notes=demo_tag("Referente sociale experimentee, bon ancrage territorial."),
        owner_admin_username="coord_nanterre",
    ),
    DemoProfessionalLeadSpec(
        key="lead_housing_support",
        email="mehdi.logement.demo@helpchain.local",
        full_name="Mehdi Benali",
        phone="06 48 55 71 82",
        city="Boulogne-Billancourt",
        profession="Accompagnement logement",
        organization="Association Toit et Liens",
        availability="Dispo le matin",
        message="Peut intervenir sur l'acces au logement et la mediation bailleur.",
        source="professional_directory",
        status="contacted",
        notes=demo_tag("Profil utile pour dossiers expulsion et maintien dans le logement."),
        owner_admin_username="ops_demo",
    ),
    DemoProfessionalLeadSpec(
        key="lead_legal_aid",
        email="camille.droits.demo@helpchain.local",
        full_name="Camille Dubreuil",
        phone="07 60 19 82 10",
        city="Paris",
        profession="Aide juridique",
        organization="Maison des droits Paris Nord",
        availability="Mercredi apres-midi",
        message="Peut appuyer les recours administratifs et l'acces aux droits sociaux.",
        source="professional_directory",
        status="new",
        notes=demo_tag("A relancer pour convention de partenariat."),
        owner_admin_username="admin",
    ),
    DemoProfessionalLeadSpec(
        key="lead_food_assistance",
        email="nora.epicerie.demo@helpchain.local",
        full_name="Nora Ait Said",
        phone="06 71 44 22 08",
        city="Paris",
        profession="Aide alimentaire",
        organization="Epicerie sociale Solidaire 19e",
        availability="Tous les jours sauf vendredi",
        message="Capacite de reorientation rapide vers epicerie sociale et colis d'urgence.",
        source="professional_directory",
        status="qualified",
        notes=demo_tag("Peut absorber les pics d'orientation alimentaire."),
        owner_admin_username="ops_demo",
    ),
    DemoProfessionalLeadSpec(
        key="lead_medical_coordination",
        email="julien.coordination.demo@helpchain.local",
        full_name="Julien Morel",
        phone="06 30 18 54 09",
        city="Nanterre",
        profession="Coordination medico-sociale",
        organization="Reseau Sante Territoriale Ouest",
        availability="Sur appel",
        message="Intervient sur les situations de rupture de soins et retour a domicile fragile.",
        source="professional_directory",
        status="contacted",
        notes=demo_tag("Partenaire cle pour les cas a forte criticite."),
        owner_admin_username="coord_nanterre",
    ),
]

DEMO_DEMO_LEADS = [
    DemoProfessionalLeadSpec(
        key="demo_mairie_interest",
        email="mairie.nanterre.demo@helpchain.local",
        full_name="Pauline Renaud",
        phone="01 44 10 20 30",
        city="Nanterre",
        profession="Direction action sociale",
        organization="Mairie de Nanterre",
        availability="Semaine prochaine",
        message="Souhaite une demonstration sur le pilotage des demandes et la coordination terrain.",
        source="demo_page",
        status="demo_scheduled",
        notes=demo_tag("Interet fort pour tableau de bord et gouvernance locale."),
        owner_admin_username="admin",
    ),
    DemoProfessionalLeadSpec(
        key="demo_ccas_interest",
        email="ccas.paris.demo@helpchain.local",
        full_name="Helene Garcin",
        phone="01 53 10 11 12",
        city="Paris",
        profession="Responsable innovation sociale",
        organization="CCAS Paris Centre",
        availability="Fin de mois",
        message="Recherche une solution pour fluidifier les orientations complexes.",
        source="demo_page",
        status="pilot_discussion",
        notes=demo_tag("A adresser avec angle performance et qualite de suivi."),
        owner_admin_username="admin",
    ),
    DemoProfessionalLeadSpec(
        key="demo_association_interest",
        email="asso.solidaire.demo@helpchain.local",
        full_name="Marc Delcourt",
        phone="06 11 90 82 54",
        city="Boulogne-Billancourt",
        profession="Direction de structure",
        organization="Association Passerelles Solidaires",
        availability="Matin",
        message="Demande une presentation produit et les modalites d'onboarding equipe.",
        source="demo_page",
        status="contacted",
        notes=demo_tag("Premier contact etabli, relance planifiee."),
        owner_admin_username="ops_demo",
    ),
]

DEMO_ORG_ACCESS_REQUESTS = [
    DemoOrgAccessRequestSpec(
        key="org_req_nanterre",
        organization_name="CCAS de Nanterre",
        contact_name="Marion Keller",
        email="marion.keller.demo@helpchain.local",
        phone="01 47 29 50 50",
        city="Nanterre",
        org_type="ccas",
        estimated_users=18,
        message="Souhaite ouvrir un espace d'administration local pour les equipes de coordination sociale.",
        status="new",
        internal_notes=demo_tag("A prioriser pour le cycle demo institutionnel."),
    ),
    DemoOrgAccessRequestSpec(
        key="org_req_paris",
        organization_name="Association Solidarite Paris",
        contact_name="Yasmine Touati",
        email="yasmine.touati.demo@helpchain.local",
        phone="01 42 20 55 10",
        city="Paris",
        org_type="association",
        estimated_users=9,
        message="Besoin d'un espace multi-operateurs pour le suivi des demandes logement et acces aux droits.",
        status="reviewed",
        internal_notes=demo_tag("Interet confirme, attente arbitrage budgetaire."),
    ),
    DemoOrgAccessRequestSpec(
        key="org_req_boulogne",
        organization_name="Centre Social Boulogne",
        contact_name="Claire Fontaine",
        email="claire.fontaine.demo@helpchain.local",
        phone="01 46 03 33 12",
        city="Boulogne-Billancourt",
        org_type="centre_social",
        estimated_users=6,
        message="Demande d'informations complementaires sur l'integration et la gouvernance locale.",
        status="need_info",
        internal_notes=demo_tag("Envoyer note d'usage et exemple de parcours."),
    ),
]


class SeedContext:
    def __init__(self, *, dry_run: bool, reset_demo: bool, allow_unsafe_target: bool) -> None:
        self.dry_run = dry_run
        self.reset_demo = reset_demo
        self.allow_unsafe_target = allow_unsafe_target
        self.created = defaultdict(int)
        self.updated = defaultdict(int)
        self.deleted = defaultdict(int)
        self.skipped = []
        self.warnings = []
        self.admin_lookup: dict[str, AdminUser] = {}
        self.user_lookup: dict[str, User] = {}
        self.structure_lookup: dict[str, Structure] = {}
        self.service_lookup: dict[tuple[str, str], StructureService] = {}
        self.request_lookup: dict[str, Request] = {}
        self.lead_lookup: dict[str, ProfessionalLead] = {}
        self.case_lookup: dict[str, Case] = {}
        self.inspector = inspect(db.engine)
        self.tables = set(self.inspector.get_table_names())

    def note_skip(self, message: str) -> None:
        self.skipped.append(message)

    def note_warning(self, message: str) -> None:
        self.warnings.append(message)

    def table_exists(self, table_name: str) -> bool:
        return table_name in self.tables

    def column_names(self, model: Any) -> set[str]:
        try:
            return set(model.__table__.columns.keys())
        except Exception:
            return set()

    def count(self, label: str, action: str, amount: int = 1) -> None:
        bucket = {"created": self.created, "updated": self.updated, "deleted": self.deleted}.get(action)
        if bucket is not None:
            bucket[label] += amount


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed a stable local HelpChain demo dataset into the active local SQLite database."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and validate the demo dataset, then roll the transaction back.",
    )
    parser.add_argument(
        "--reset-demo",
        action="store_true",
        help="Remove only demo rows previously created by this script, then stop.",
    )
    parser.add_argument(
        "--allow-unsafe-target",
        action="store_true",
        help="Bypass the default production-safety refusal checks.",
    )
    return parser.parse_args()


def runtime_config() -> dict[str, Any]:
    return {
        "SQLALCHEMY_DATABASE_URI": app.config.get("SQLALCHEMY_DATABASE_URI"),
        "DATABASE_URL": os.getenv("DATABASE_URL"),
        "HC_DB_PATH": os.getenv("HC_DB_PATH"),
        "PUBLIC_BASE_URL": app.config.get("PUBLIC_BASE_URL") or os.getenv("PUBLIC_BASE_URL"),
        "REQUIRE_ADMIN_MFA": app.config.get("REQUIRE_ADMIN_MFA"),
        "MFA_ENABLED": app.config.get("MFA_ENABLED"),
    }


def print_runtime_banner() -> dict[str, Any]:
    cfg = runtime_config()
    print("== HelpChain local demo seed runtime ==")
    for key in (
        "SQLALCHEMY_DATABASE_URI",
        "DATABASE_URL",
        "HC_DB_PATH",
        "PUBLIC_BASE_URL",
        "REQUIRE_ADMIN_MFA",
        "MFA_ENABLED",
    ):
        print(f"{key}={cfg.get(key)}")
    return cfg


def ensure_safe_target(args: argparse.Namespace, cfg: dict[str, Any]) -> None:
    if args.allow_unsafe_target:
        return

    uri = str(cfg.get("SQLALCHEMY_DATABASE_URI") or "")
    database_url = str(cfg.get("DATABASE_URL") or "")
    public_base_url = str(cfg.get("PUBLIC_BASE_URL") or "")
    target_text = " ".join((uri, database_url)).lower()

    if "helpchain.live" in public_base_url.lower():
        raise SystemExit(
            "Refusing to run because PUBLIC_BASE_URL targets helpchain.live. "
            "Use --allow-unsafe-target only if you intentionally want to override this."
        )

    if any(marker in target_text for marker in ("postgres://", "postgresql://", "neon.tech", "render.com")):
        raise SystemExit(
            "Refusing to run because the active database target looks non-local or production-like."
        )

    if not uri.lower().startswith("sqlite"):
        raise SystemExit(
            "Refusing to run because local demo seed only allows SQLite targets by default."
        )


def set_existing_fields(obj: Any, values: dict[str, Any]) -> None:
    columns = set(obj.__table__.columns.keys())
    for key, value in values.items():
        if key in columns:
            setattr(obj, key, value)


def upsert_row(
    ctx: SeedContext,
    model: Any,
    *,
    lookup: dict[str, Any],
    key: str,
    filters: dict[str, Any],
    values: dict[str, Any],
    label: str,
) -> Any:
    row = model.query.filter_by(**filters).first()
    if row is None:
        row = model(**{**filters, **values})
        db.session.add(row)
        ctx.count(label, "created")
    else:
        set_existing_fields(row, values)
        ctx.count(label, "updated")
    db.session.flush()
    lookup[key] = row
    return row


def ensure_structure(ctx: SeedContext, spec: DemoStructureSpec) -> Structure:
    return upsert_row(
        ctx,
        Structure,
        lookup=ctx.structure_lookup,
        key=spec.slug,
        filters={"slug": spec.slug},
        values={"name": spec.name, "status": spec.status},
        label="structures",
    )


def ensure_structure_service(
    ctx: SeedContext,
    *,
    structure: Structure,
    code: str,
    name: str,
) -> StructureService | None:
    if not ctx.table_exists("structure_services"):
        ctx.note_skip("structure_services table not found; request services were skipped.")
        return None

    key = (structure.slug, code)
    if key in ctx.service_lookup:
        return ctx.service_lookup[key]

    row = (
        StructureService.query.filter_by(structure_id=structure.id, code=code)
        .order_by(StructureService.id.asc())
        .first()
    )
    values = {"name": name, "is_active": True}
    if row is None:
        row = StructureService(structure_id=structure.id, code=code, **values)
        db.session.add(row)
        ctx.count("structure_services", "created")
    else:
        set_existing_fields(row, values)
        ctx.count("structure_services", "updated")
    db.session.flush()
    ctx.service_lookup[key] = row
    return row


def ensure_admin_user(ctx: SeedContext, spec: DemoAdminSpec) -> AdminUser:
    structure_id = None
    if spec.structure_slug:
        structure_id = ctx.structure_lookup[spec.structure_slug].id

    row = (
        AdminUser.query.filter(
            (AdminUser.username == spec.username) | (AdminUser.email == spec.email)
        )
        .order_by(AdminUser.id.asc())
        .first()
    )
    values = {
        "username": spec.username,
        "email": spec.email,
        "role": spec.role,
        "is_active": True,
        "structure_id": structure_id,
        "must_change_password": False,
        "mfa_enabled": False,
        "totp_secret": None,
        "mfa_enrolled_at": None,
        "backup_codes_hashes": None,
        "backup_codes_generated_at": None,
        "onboarding_step": None,
        "onboarding_data_json": None,
    }
    if row is None:
        row = AdminUser(**values)
        row.set_password(DEFAULT_ADMIN_PASSWORD)
        db.session.add(row)
        ctx.count("admin_users", "created")
    else:
        set_existing_fields(row, values)
        row.set_password(DEFAULT_ADMIN_PASSWORD)
        ctx.count("admin_users", "updated")
    db.session.flush()
    ctx.admin_lookup[spec.username] = row
    return row


def ensure_user(ctx: SeedContext, spec: DemoUserSpec) -> User:
    structure = ctx.structure_lookup[spec.structure_slug]
    row = (
        User.query.filter((User.username == spec.username) | (User.email == spec.email))
        .order_by(User.id.asc())
        .first()
    )
    values = {
        "username": spec.username,
        "email": spec.email,
        "role": spec.role,
        "is_active": True,
        "structure_id": structure.id,
    }
    if row is None:
        row = User(**values)
        row.set_password(DEFAULT_USER_PASSWORD)
        db.session.add(row)
        ctx.count("users", "created")
    else:
        set_existing_fields(row, values)
        row.set_password(DEFAULT_USER_PASSWORD)
        ctx.count("users", "updated")
    db.session.flush()
    ctx.user_lookup[spec.username] = row
    return row


def ensure_intervenant(ctx: SeedContext, *, username: str, structure_slug: str, name: str, email: str) -> Intervenant | None:
    if not ctx.table_exists("intervenants"):
        ctx.note_skip("intervenants table not found; assignment helper rows were skipped.")
        return None

    structure = ctx.structure_lookup[structure_slug]
    row = (
        Intervenant.query.filter_by(structure_id=structure.id, email=email)
        .order_by(Intervenant.id.asc())
        .first()
    )
    values = {
        "name": name,
        "actor_type": "professional",
        "email": email,
        "phone": "01 00 00 00 00",
        "location": structure.name,
        "is_active": True,
    }
    if row is None:
        row = Intervenant(structure_id=structure.id, **values)
        db.session.add(row)
        ctx.count("intervenants", "created")
    else:
        set_existing_fields(row, values)
        ctx.count("intervenants", "updated")
    db.session.flush()
    return row


def ensure_volunteer(ctx: SeedContext) -> Volunteer | None:
    if not ctx.table_exists("volunteers"):
        ctx.note_skip("volunteers table not found; volunteer notification rows were skipped.")
        return None
    row = Volunteer.query.filter_by(email=f"volunteer.demo@{DEMO_EMAIL_DOMAIN}").first()
    values = {
        "name": "Paul Demo",
        "email": f"volunteer.demo@{DEMO_EMAIL_DOMAIN}",
        "phone": "06 10 10 10 10",
        "location": "Nanterre",
        "availability": "semaine",
        "skills": demo_tag("renfort logistique"),
        "is_active": True,
    }
    if row is None:
        row = Volunteer(**values)
        db.session.add(row)
        ctx.count("volunteers", "created")
    else:
        set_existing_fields(row, values)
        ctx.count("volunteers", "updated")
    db.session.flush()
    return row


def ensure_request(ctx: SeedContext, spec: DemoRequestSpec) -> Request:
    structure = ctx.structure_lookup[spec.structure_slug]
    user = ctx.user_lookup[spec.user_username]
    owner = ctx.admin_lookup.get(spec.owner_admin_username) if spec.owner_admin_username else None
    service_id = None
    if spec.service_code:
        service = ctx.service_lookup.get((structure.slug, spec.service_code))
        service_id = getattr(service, "id", None)

    created_at = now_utc_naive() - timedelta(days=spec.created_days_ago)
    completed_at = None
    if spec.completed_days_ago is not None:
        completed_at = now_utc_naive() - timedelta(days=spec.completed_days_ago)
    owned_at = None
    if spec.assigned_days_ago is not None:
        owned_at = now_utc_naive() - timedelta(days=spec.assigned_days_ago)

    row = (
        Request.query.filter_by(email=spec.email)
        .order_by(Request.id.asc())
        .first()
    )
    values = {
        "title": spec.title,
        "description": spec.description,
        "message": demo_tag(f"{spec.description}"),
        "name": spec.name,
        "phone": spec.phone,
        "city": spec.city,
        "postcode": spec.postcode,
        "address_line": spec.address_line,
        "country": "France",
        "status": spec.status,
        "priority": spec.priority,
        "category": spec.category,
        "source_channel": spec.source_channel,
        "structure_id": structure.id,
        "service_id": service_id,
        "user_id": user.id,
        "owner_id": getattr(owner, "id", None),
        "owned_at": owned_at,
        "created_at": created_at,
        "updated_at": now_utc_naive(),
        "completed_at": completed_at,
        "is_archived": False,
    }
    if row is None:
        row = Request(email=spec.email, **values)
        db.session.add(row)
        ctx.count("requests", "created")
    else:
        set_existing_fields(row, values)
        ctx.count("requests", "updated")
    db.session.flush()
    ctx.request_lookup[spec.key] = row
    return row


def ensure_request_logs(ctx: SeedContext, req: Request, *, admin: AdminUser | None) -> None:
    if ctx.table_exists("request_logs"):
        actions = [
            f"{DEMO_MARKER}:created",
            f"{DEMO_MARKER}:reviewed",
        ]
        for action in actions:
            row = RequestLog.query.filter_by(request_id=req.id, action=action).first()
            if row is None:
                db.session.add(
                    RequestLog(
                        request_id=req.id,
                        action=action,
                        timestamp=now_utc_naive(),
                    )
                )
                ctx.count("request_logs", "created")
    else:
        ctx.note_skip("request_logs table not found; request timeline log rows were skipped.")

    if ctx.table_exists("request_activities"):
        activities = [
            ("status_seed", None, req.status),
            ("owner_seed", None, str(getattr(req, "owner_id", None) or "")),
        ]
        for action, old_value, new_value in activities:
            row = (
                RequestActivity.query.filter_by(
                    request_id=req.id,
                    actor_admin_id=getattr(admin, "id", None),
                    action=action,
                )
                .order_by(RequestActivity.id.asc())
                .first()
            )
            if row is None:
                db.session.add(
                    RequestActivity(
                        request_id=req.id,
                        actor_admin_id=getattr(admin, "id", None),
                        action=action,
                        old_value=old_value,
                        new_value=new_value,
                        created_at=now_utc_naive(),
                    )
                )
                ctx.count("request_activities", "created")
    else:
        ctx.note_skip("request_activities table not found; request activity rows were skipped.")

    if ctx.table_exists("request_metrics"):
        row = RequestMetric.query.filter_by(request_id=req.id).first()
        if row is None:
            row = RequestMetric(request_id=req.id)
            db.session.add(row)
            ctx.count("request_metrics", "created")
        else:
            ctx.count("request_metrics", "updated")
        row.time_to_assign = 7200 if getattr(req, "owner_id", None) else None
        row.time_to_complete = 86400 if getattr(req, "completed_at", None) else None
    else:
        ctx.note_skip("request_metrics table not found; request timing metrics were skipped.")


def ensure_assignment(
    ctx: SeedContext,
    *,
    req: Request,
    intervenant: Intervenant | None,
    structure: Structure,
    admin: AdminUser | None,
) -> None:
    if intervenant is None or not ctx.table_exists("assignments") or not getattr(req, "owner_id", None):
        if not ctx.table_exists("assignments"):
            ctx.note_skip("assignments table not found; request assignments were skipped.")
        return

    row = Assignment.query.filter_by(request_id=req.id, intervenant_id=intervenant.id).first()
    values = {
        "structure_id": structure.id,
        "assigned_by_admin_id": getattr(admin, "id", None),
        "assigned_at": now_utc_naive() - timedelta(days=1),
        "status": "active",
        "notes": demo_tag("Affectation de demonstration locale"),
    }
    if row is None:
        row = Assignment(request_id=req.id, intervenant_id=intervenant.id, **values)
        db.session.add(row)
        ctx.count("assignments", "created")
    else:
        set_existing_fields(row, values)
        ctx.count("assignments", "updated")


def ensure_professional_lead(ctx: SeedContext, spec: DemoProfessionalLeadSpec) -> ProfessionalLead | None:
    if not ctx.table_exists("professional_leads"):
        ctx.note_skip("professional_leads table not found; professional leads and demo leads were skipped.")
        return None

    owner = ctx.admin_lookup.get(spec.owner_admin_username) if spec.owner_admin_username else None
    row = ProfessionalLead.query.filter_by(email=spec.email).first()
    values = {
        "full_name": spec.full_name,
        "phone": spec.phone,
        "city": spec.city,
        "profession": spec.profession,
        "organization": spec.organization,
        "availability": spec.availability,
        "message": demo_tag(spec.message),
        "source": spec.source,
        "locale": "fr",
        "ip": "127.0.0.1",
        "user_agent": "local-demo-seed",
        "owner_admin_id": getattr(owner, "id", None),
        "status": spec.status,
        "notes": spec.notes,
        "last_touched_at": now_utc_naive(),
        "last_touched_by_admin_id": getattr(owner, "id", None),
        "next_action_at": now_utc_naive() + timedelta(days=3),
        "next_action_note": demo_tag("Relance demo locale planifiee"),
        "created_at": now_utc_naive() - timedelta(days=5),
    }
    if spec.status in {"contacted", "qualified", "demo_scheduled", "pilot_discussion", "closed"}:
        values["contacted_at"] = now_utc_naive() - timedelta(days=2)
    if row is None:
        row = ProfessionalLead(email=spec.email, **values)
        db.session.add(row)
        ctx.count("professional_leads", "created")
    else:
        set_existing_fields(row, values)
        ctx.count("professional_leads", "updated")
    db.session.flush()
    ctx.lead_lookup[spec.key] = row
    return row


def ensure_professional_lead_activity(ctx: SeedContext, lead: ProfessionalLead | None, action: str, admin: AdminUser | None) -> None:
    if lead is None:
        return
    if not ctx.table_exists("professional_lead_activities"):
        ctx.note_skip("professional_lead_activities table not found; lead activity rows were skipped.")
        return

    row = (
        ProfessionalLeadActivity.query.filter_by(
            professional_lead_id=lead.id,
            admin_user_id=getattr(admin, "id", None),
            action=action,
        )
        .order_by(ProfessionalLeadActivity.id.asc())
        .first()
    )
    if row is None:
        db.session.add(
            ProfessionalLeadActivity(
                professional_lead_id=lead.id,
                admin_user_id=getattr(admin, "id", None),
                action=action,
                payload_json=json.dumps({"marker": DEMO_MARKER}, ensure_ascii=True),
                created_at=now_utc_naive(),
            )
        )
        ctx.count("professional_lead_activities", "created")


def ensure_org_access_request(ctx: SeedContext, spec: DemoOrgAccessRequestSpec, reviewer: AdminUser | None) -> OrganizationAccessRequest | None:
    if not ctx.table_exists("organization_access_requests"):
        ctx.note_skip("organization_access_requests table not found; organization onboarding requests were skipped.")
        return None

    row = OrganizationAccessRequest.query.filter_by(email=spec.email).first()
    values = {
        "organization_name": spec.organization_name,
        "contact_name": spec.contact_name,
        "phone": spec.phone,
        "city": spec.city,
        "org_type": spec.org_type,
        "estimated_users": spec.estimated_users,
        "message": demo_tag(spec.message),
        "status": spec.status,
        "reviewed_by_admin_id": getattr(reviewer, "id", None),
        "reviewed_at": now_utc_naive() if spec.status != "new" else None,
        "internal_notes": spec.internal_notes,
        "next_action_at": now_utc_naive() + timedelta(days=5),
        "next_action_note": demo_tag("Reprise du contact sous cinq jours"),
        "created_at": now_utc_naive() - timedelta(days=4),
        "updated_at": now_utc_naive(),
    }
    if row is None:
        row = OrganizationAccessRequest(email=spec.email, **values)
        db.session.add(row)
        ctx.count("organization_access_requests", "created")
    else:
        set_existing_fields(row, values)
        ctx.count("organization_access_requests", "updated")
    db.session.flush()
    return row


def ensure_case(
    ctx: SeedContext,
    *,
    key: str,
    req: Request,
    structure: Structure,
    owner: User | None,
    lead: ProfessionalLead | None,
    status: str,
    priority: str,
    risk_score: int,
) -> Case | None:
    if not ctx.table_exists("cases"):
        ctx.note_skip("cases table not found; case workflow rows were skipped.")
        return None

    row = Case.query.filter_by(request_id=req.id).first()
    values = {
        "structure_id": structure.id,
        "owner_user_id": getattr(owner, "id", None),
        "assigned_professional_lead_id": getattr(lead, "id", None),
        "status": status,
        "priority": priority,
        "risk_score": risk_score,
        "opened_at": getattr(req, "created_at", None) or now_utc_naive(),
        "assigned_at": now_utc_naive() - timedelta(days=1) if getattr(owner, "id", None) else None,
        "resolved_at": now_utc_naive() - timedelta(days=1) if status in {"resolved", "closed"} else None,
        "closed_at": now_utc_naive() - timedelta(hours=8) if status == "closed" else None,
        "last_activity_at": now_utc_naive() - timedelta(hours=3),
        "created_at": getattr(req, "created_at", None) or now_utc_naive(),
        "updated_at": now_utc_naive(),
    }
    if row is None:
        row = Case(request_id=req.id, **values)
        db.session.add(row)
        ctx.count("cases", "created")
    else:
        set_existing_fields(row, values)
        ctx.count("cases", "updated")
    db.session.flush()
    ctx.case_lookup[key] = row
    return row


def ensure_case_related(
    ctx: SeedContext,
    *,
    case_row: Case | None,
    req: Request,
    admin: AdminUser | None,
    lead: ProfessionalLead | None,
    collaborator_structure: Structure | None,
) -> None:
    if case_row is None:
        return

    if ctx.table_exists("case_events"):
        for event_type, message in (
            ("coordination_note", demo_tag("Point de situation institutionnel enregistre.")),
            ("status_sync", demo_tag(f"Statut dossier aligne avec la demande {req.status}.")),
        ):
            row = (
                CaseEvent.query.filter_by(case_id=case_row.id, event_type=event_type, message=message)
                .order_by(CaseEvent.id.asc())
                .first()
            )
            if row is None:
                db.session.add(
                    CaseEvent(
                        case_id=case_row.id,
                        actor_user_id=None,
                        event_type=event_type,
                        message=message,
                        metadata_json=json.dumps({"request_id": req.id}, ensure_ascii=True),
                        visibility="internal",
                        created_at=now_utc_naive(),
                    )
                )
                ctx.count("case_events", "created")
    else:
        ctx.note_skip("case_events table not found; case event timeline rows were skipped.")

    if ctx.table_exists("case_participants"):
        participant_specs = [
            {
                "participant_type": "admin",
                "admin_user_id": getattr(admin, "id", None),
                "role": "owner",
                "status": "active",
            },
            {
                "participant_type": "professional_lead",
                "professional_lead_id": getattr(lead, "id", None),
                "role": "advisor",
                "status": "active",
            },
        ]
        for participant in participant_specs:
            identity = participant.get("admin_user_id") or participant.get("professional_lead_id")
            if not identity:
                continue
            row = (
                CaseParticipant.query.filter_by(
                    case_id=case_row.id,
                    participant_type=participant["participant_type"],
                    admin_user_id=participant.get("admin_user_id"),
                    professional_lead_id=participant.get("professional_lead_id"),
                )
                .order_by(CaseParticipant.id.asc())
                .first()
            )
            if row is None:
                db.session.add(
                    CaseParticipant(
                        case_id=case_row.id,
                        participant_type=participant["participant_type"],
                        admin_user_id=participant.get("admin_user_id"),
                        professional_lead_id=participant.get("professional_lead_id"),
                        actor_type=participant["participant_type"],
                        role=participant["role"],
                        status=participant["status"],
                        added_at=now_utc_naive(),
                    )
                )
                ctx.count("case_participants", "created")
    else:
        ctx.note_skip("case_participants table not found; case participant rows were skipped.")

    if collaborator_structure is not None:
        if ctx.table_exists("case_collaborators"):
            row = CaseCollaborator.query.filter_by(
                case_id=case_row.id,
                structure_id=collaborator_structure.id,
            ).first()
            if row is None:
                db.session.add(
                    CaseCollaborator(
                        case_id=case_row.id,
                        structure_id=collaborator_structure.id,
                        role="support",
                        created_at=now_utc_naive(),
                    )
                )
                ctx.count("case_collaborators", "created")
        else:
            ctx.note_skip("case_collaborators table not found; cross-structure case support rows were skipped.")


def ensure_notification_jobs(ctx: SeedContext, *, structure: Structure) -> None:
    if not ctx.table_exists("notification_jobs"):
        ctx.note_skip("notification_jobs table not found; operational notifications were skipped.")
        return

    specs = [
        ("pending", "request.created", "coordination@helpchain.local", "A traiter en priorite"),
        ("failed", "case.followup", "pilotage@helpchain.local", "Echec de relance dossier"),
        ("sent", "lead.contacted", "direction@helpchain.local", "Relance partenaire envoyee"),
    ]
    for status, event_type, recipient, subject in specs:
        row = (
            NotificationJob.query.filter_by(
                recipient=recipient,
                event_type=event_type,
                subject=demo_tag(subject),
            )
            .order_by(NotificationJob.id.asc())
            .first()
        )
        values = {
            "channel": "email",
            "payload_json": json.dumps({"marker": DEMO_MARKER, "status": status}, ensure_ascii=True),
            "status": status,
            "attempts": 1 if status != "pending" else 0,
            "max_attempts": 5,
            "next_retry_at": now_utc_naive() + timedelta(hours=2) if status == "failed" else None,
            "locked_at": None,
            "processed_at": now_utc_naive() - timedelta(hours=1) if status == "sent" else None,
            "sent_at": now_utc_naive() - timedelta(hours=1) if status == "sent" else None,
            "last_error": "SMTP timeout demo" if status == "failed" else None,
            "structure_id": structure.id,
            "created_at": now_utc_naive() - timedelta(hours=6),
            "updated_at": now_utc_naive(),
        }
        if row is None:
            row = NotificationJob(
                recipient=recipient,
                event_type=event_type,
                subject=demo_tag(subject),
                **values,
            )
            db.session.add(row)
            ctx.count("notification_jobs", "created")
        else:
            set_existing_fields(row, values)
            ctx.count("notification_jobs", "updated")


def ensure_admin_audit_rows(ctx: SeedContext) -> None:
    if ctx.table_exists("admin_login_attempts"):
        for username, success in (("admin", True), ("coord_nanterre", True), ("ops_demo", False)):
            row = (
                AdminLoginAttempt.query.filter_by(
                    username=username,
                    ip="127.0.0.1",
                    success=success,
                )
                .order_by(AdminLoginAttempt.id.asc())
                .first()
            )
            if row is None:
                db.session.add(
                    AdminLoginAttempt(
                        username=username,
                        ip="127.0.0.1",
                        success=success,
                        user_agent=f"local-demo-seed:{DEMO_MARKER}",
                        created_at=now_utc_naive() - timedelta(hours=1),
                    )
                )
                ctx.count("admin_login_attempts", "created")
    else:
        ctx.note_skip("admin_login_attempts table not found; admin auth dashboard rows were skipped.")

    if ctx.table_exists("admin_audit_events"):
        for username, action, target_type in (
            ("admin", "LOCAL_DEMO_SEED_RUN", "seed"),
            ("coord_nanterre", "LOCAL_DEMO_REQUEST_TRIAGE_REVIEWED", "request"),
        ):
            admin = ctx.admin_lookup.get(username)
            row = (
                AdminAuditEvent.query.filter_by(
                    admin_username=username,
                    action=action,
                    target_type=target_type,
                    target_id=0,
                )
                .order_by(AdminAuditEvent.id.asc())
                .first()
            )
            if row is None:
                db.session.add(
                    AdminAuditEvent(
                        admin_user_id=getattr(admin, "id", None),
                        admin_username=username,
                        action=action,
                        target_type=target_type,
                        target_id=0,
                        ip="127.0.0.1",
                        user_agent="local-demo-seed",
                        payload={"marker": DEMO_MARKER},
                        created_at=now_utc_naive() - timedelta(minutes=35),
                    )
                )
                ctx.count("admin_audit_events", "created")
    else:
        ctx.note_skip("admin_audit_events table not found; admin audit dashboard rows were skipped.")


def reset_demo_rows(ctx: SeedContext) -> None:
    demo_request_ids = [
        row.id
        for row in Request.query.filter(Request.email.like(f"%.demo@{DEMO_EMAIL_DOMAIN}")).all()
    ]
    demo_lead_ids = [
        row.id
        for row in ProfessionalLead.query.filter(ProfessionalLead.email.like(f"%.demo@{DEMO_EMAIL_DOMAIN}")).all()
    ] if ctx.table_exists("professional_leads") else []
    demo_case_ids = [
        row.id
        for row in Case.query.filter(Case.request_id.in_(demo_request_ids)).all()
    ] if ctx.table_exists("cases") and demo_request_ids else []

    if ctx.table_exists("case_events") and demo_case_ids:
        deleted = CaseEvent.query.filter(CaseEvent.case_id.in_(demo_case_ids)).delete(synchronize_session=False)
        ctx.count("case_events", "deleted", deleted)
    if ctx.table_exists("case_participants") and demo_case_ids:
        deleted = CaseParticipant.query.filter(CaseParticipant.case_id.in_(demo_case_ids)).delete(synchronize_session=False)
        ctx.count("case_participants", "deleted", deleted)
    if ctx.table_exists("case_collaborators") and demo_case_ids:
        deleted = CaseCollaborator.query.filter(CaseCollaborator.case_id.in_(demo_case_ids)).delete(synchronize_session=False)
        ctx.count("case_collaborators", "deleted", deleted)
    if ctx.table_exists("cases") and demo_request_ids:
        deleted = Case.query.filter(Case.request_id.in_(demo_request_ids)).delete(synchronize_session=False)
        ctx.count("cases", "deleted", deleted)

    if ctx.table_exists("professional_lead_activities") and demo_lead_ids:
        deleted = ProfessionalLeadActivity.query.filter(
            ProfessionalLeadActivity.professional_lead_id.in_(demo_lead_ids)
        ).delete(synchronize_session=False)
        ctx.count("professional_lead_activities", "deleted", deleted)
    if ctx.table_exists("professional_leads"):
        deleted = ProfessionalLead.query.filter(
            ProfessionalLead.email.like(f"%.demo@{DEMO_EMAIL_DOMAIN}")
        ).delete(synchronize_session=False)
        ctx.count("professional_leads", "deleted", deleted)

    if ctx.table_exists("organization_access_requests"):
        deleted = OrganizationAccessRequest.query.filter(
            OrganizationAccessRequest.email.like(f"%.demo@{DEMO_EMAIL_DOMAIN}")
        ).delete(synchronize_session=False)
        ctx.count("organization_access_requests", "deleted", deleted)

    if ctx.table_exists("notification_jobs"):
        deleted = NotificationJob.query.filter(NotificationJob.subject.like(f"{DEMO_MARKER}%")).delete(
            synchronize_session=False
        )
        ctx.count("notification_jobs", "deleted", deleted)

    if ctx.table_exists("request_activities") and demo_request_ids:
        deleted = RequestActivity.query.filter(RequestActivity.request_id.in_(demo_request_ids)).delete(
            synchronize_session=False
        )
        ctx.count("request_activities", "deleted", deleted)
    if ctx.table_exists("request_logs") and demo_request_ids:
        deleted = RequestLog.query.filter(RequestLog.request_id.in_(demo_request_ids)).delete(synchronize_session=False)
        ctx.count("request_logs", "deleted", deleted)
    if ctx.table_exists("request_metrics") and demo_request_ids:
        deleted = RequestMetric.query.filter(RequestMetric.request_id.in_(demo_request_ids)).delete(
            synchronize_session=False
        )
        ctx.count("request_metrics", "deleted", deleted)
    if ctx.table_exists("assignments") and demo_request_ids:
        deleted = Assignment.query.filter(Assignment.request_id.in_(demo_request_ids)).delete(synchronize_session=False)
        ctx.count("assignments", "deleted", deleted)
    if demo_request_ids:
        deleted = Request.query.filter(Request.id.in_(demo_request_ids)).delete(synchronize_session=False)
        ctx.count("requests", "deleted", deleted)

    if ctx.table_exists("intervenants"):
        deleted = Intervenant.query.filter(Intervenant.email.like(f"%.{DEMO_EMAIL_DOMAIN}")).delete(
            synchronize_session=False
        )
        ctx.count("intervenants", "deleted", deleted)
    if ctx.table_exists("volunteers"):
        deleted = Volunteer.query.filter(Volunteer.email.like(f"%.{DEMO_EMAIL_DOMAIN}")).delete(synchronize_session=False)
        ctx.count("volunteers", "deleted", deleted)
    if ctx.table_exists("users"):
        deleted = User.query.filter(User.email.like(f"%@{DEMO_EMAIL_DOMAIN}")).delete(synchronize_session=False)
        ctx.count("users", "deleted", deleted)
    if ctx.table_exists("admin_users"):
        deleted = AdminUser.query.filter(AdminUser.email.like(f"%@{DEMO_EMAIL_DOMAIN}")).delete(synchronize_session=False)
        ctx.count("admin_users", "deleted", deleted)

    if ctx.table_exists("structure_services"):
        demo_structure_ids = [
            row.id for row in Structure.query.filter(Structure.slug.in_([spec.slug for spec in DEMO_STRUCTURES])).all()
        ]
        if demo_structure_ids:
            deleted = StructureService.query.filter(
                StructureService.structure_id.in_(demo_structure_ids)
            ).delete(synchronize_session=False)
            ctx.count("structure_services", "deleted", deleted)

    if ctx.table_exists("admin_audit_events"):
        deleted = AdminAuditEvent.query.filter(
            AdminAuditEvent.action.in_(("LOCAL_DEMO_SEED_RUN", "LOCAL_DEMO_REQUEST_TRIAGE_REVIEWED"))
        ).delete(synchronize_session=False)
        ctx.count("admin_audit_events", "deleted", deleted)
    if ctx.table_exists("admin_login_attempts"):
        deleted = AdminLoginAttempt.query.filter(
            AdminLoginAttempt.user_agent.like(f"%{DEMO_MARKER}%")
        ).delete(synchronize_session=False)
        ctx.count("admin_login_attempts", "deleted", deleted)

    for spec in DEMO_STRUCTURES:
        structure = Structure.query.filter_by(slug=spec.slug).first()
        if structure is None:
            continue
        has_other_requests = Request.query.filter(Request.structure_id == structure.id).count() > 0
        has_other_users = User.query.filter(User.structure_id == structure.id).count() > 0
        has_other_admins = AdminUser.query.filter(AdminUser.structure_id == structure.id).count() > 0
        if has_other_requests or has_other_users or has_other_admins:
            ctx.note_warning(
                f"Kept structure '{structure.slug}' because related rows still exist after demo cleanup."
            )
            continue
        db.session.delete(structure)
        ctx.count("structures", "deleted")


def seed_demo(ctx: SeedContext) -> None:
    for spec in DEMO_STRUCTURES:
        ensure_structure(ctx, spec)

    service_catalog = {
        "housing": "Accompagnement logement",
        "food": "Aide alimentaire",
        "legal": "Acces aux droits",
        "health": "Coordination medico-sociale",
    }
    for structure in list(ctx.structure_lookup.values()):
        for code, name in service_catalog.items():
            ensure_structure_service(ctx, structure=structure, code=code, name=name)

    for spec in DEMO_ADMINS:
        ensure_admin_user(ctx, spec)

    for spec in DEMO_USERS:
        ensure_user(ctx, spec)

    ensure_intervenant(
        ctx,
        username="intervenant_nanterre",
        structure_slug="ccas-nanterre",
        name="Sophie Bernard",
        email=f"intervenant.nanterre@{DEMO_EMAIL_DOMAIN}",
    )
    ensure_intervenant(
        ctx,
        username="intervenant_paris",
        structure_slug="association-solidarite-paris",
        name="Nicolas Petit",
        email=f"intervenant.paris@{DEMO_EMAIL_DOMAIN}",
    )
    ensure_intervenant(
        ctx,
        username="intervenant_boulogne",
        structure_slug="centre-social-boulogne",
        name="Lea Robin",
        email=f"intervenant.boulogne@{DEMO_EMAIL_DOMAIN}",
    )
    ensure_volunteer(ctx)

    for spec in DEMO_REQUESTS:
        req = ensure_request(ctx, spec)
        structure = ctx.structure_lookup[spec.structure_slug]
        admin = ctx.admin_lookup.get(spec.owner_admin_username) if spec.owner_admin_username else None
        ensure_request_logs(ctx, req, admin=admin)
        intervenant_email = f"intervenant.{structure.slug.split('-')[-1]}@{DEMO_EMAIL_DOMAIN}"
        intervenant = Intervenant.query.filter_by(email=intervenant_email).first() if ctx.table_exists("intervenants") else None
        ensure_assignment(ctx, req=req, intervenant=intervenant, structure=structure, admin=admin)

    for spec in [*DEMO_PROFESSIONAL_LEADS, *DEMO_DEMO_LEADS]:
        lead = ensure_professional_lead(ctx, spec)
        ensure_professional_lead_activity(
            ctx,
            lead,
            action="demo_seed_contact",
            admin=ctx.admin_lookup.get(spec.owner_admin_username) if spec.owner_admin_username else None,
        )

    for spec in DEMO_ORG_ACCESS_REQUESTS:
        ensure_org_access_request(ctx, spec, reviewer=ctx.admin_lookup.get("admin"))

    request_case_specs = [
        ("urgent_housing_nanterre", "new", "critical", 92, "lead_social_worker"),
        ("rights_access_paris", "triaged", "high", 71, "lead_legal_aid"),
        ("food_assigned_boulogne", "assigned", "standard", 44, "lead_food_assistance"),
        ("medical_followup_nanterre", "in_progress", "urgent", 88, "lead_medical_coordination"),
        ("closed_housing_paris", "closed", "standard", 25, "lead_housing_support"),
    ]
    for request_key, status, priority, risk_score, lead_key in request_case_specs:
        req = ctx.request_lookup[request_key]
        structure = ctx.structure_lookup[
            next(spec.structure_slug for spec in DEMO_REQUESTS if spec.key == request_key)
        ]
        owner_user = ctx.user_lookup.get("professional_coordination")
        if request_key in {"rights_access_paris", "closed_housing_paris"}:
            owner_user = ctx.user_lookup.get("requester_paris")
        elif request_key == "food_assigned_boulogne":
            owner_user = ctx.user_lookup.get("requester_boulogne")
        lead = ctx.lead_lookup.get(lead_key)
        case_row = ensure_case(
            ctx,
            key=request_key,
            req=req,
            structure=structure,
            owner=owner_user,
            lead=lead,
            status=status,
            priority=priority,
            risk_score=risk_score,
        )
        ensure_case_related(
            ctx,
            case_row=case_row,
            req=req,
            admin=ctx.admin_lookup.get("coord_nanterre"),
            lead=lead,
            collaborator_structure=ctx.structure_lookup.get("association-solidarite-paris")
            if request_key == "urgent_housing_nanterre"
            else None,
        )

    ensure_notification_jobs(ctx, structure=ctx.structure_lookup["ccas-nanterre"])
    ensure_admin_audit_rows(ctx)


def print_counts(ctx: SeedContext) -> None:
    print("\n== Major table counts ==")
    count_specs = [
        ("admin_users", AdminUser),
        ("users", User),
        ("structures", Structure),
        ("structure_services", StructureService),
        ("requests", Request),
        ("cases", Case),
        ("professional_leads", ProfessionalLead),
        ("organization_access_requests", OrganizationAccessRequest),
        ("notification_jobs", NotificationJob),
        ("request_activities", RequestActivity),
        ("request_logs", RequestLog),
        ("assignments", Assignment),
        ("admin_login_attempts", AdminLoginAttempt),
        ("admin_audit_events", AdminAuditEvent),
    ]
    for table_name, model in count_specs:
        if not ctx.table_exists(table_name):
            print(f"{table_name}=missing")
            continue
        try:
            print(f"{table_name}={model.query.count()}")
        except Exception as exc:
            print(f"{table_name}=error:{exc}")


def print_credentials_and_urls(cfg: dict[str, Any]) -> None:
    configured_base = str(cfg.get("PUBLIC_BASE_URL") or "").strip()
    parsed = urlparse(configured_base) if configured_base else None
    if parsed and parsed.hostname in {"127.0.0.1", "localhost"}:
        base_url = configured_base.rstrip("/")
    else:
        base_url = DEFAULT_LOCAL_BASE_URL
    print("\n== Demo credentials ==")
    admin_password_hint = "set via HC_DEMO_ADMIN_PASSWORD or local placeholder"
    user_password_hint = "set via HC_DEMO_USER_PASSWORD or local placeholder"
    print(f"superadmin: username=admin email=admin@{DEMO_EMAIL_DOMAIN} password={admin_password_hint}")
    print(f"coordinator: username=coord_nanterre email=coord.nanterre@{DEMO_EMAIL_DOMAIN} password={admin_password_hint}")
    print(f"ops: username=ops_demo email=ops.demo@{DEMO_EMAIL_DOMAIN} password={admin_password_hint}")
    print(f"readonly: username=readonly_demo email=readonly.demo@{DEMO_EMAIL_DOMAIN} password={admin_password_hint}")
    print(f"requester: username=requester_nanterre email=requester.nanterre@{DEMO_EMAIL_DOMAIN} password={user_password_hint}")

    print("\n== Demo admin MFA state ==")
    for spec in DEMO_ADMINS:
        print(
            f"{spec.username}: mfa_enabled=False totp_secret=absent "
            "(local demo state: MFA setup required when REQUIRE_ADMIN_MFA=True)"
        )

    print("\n== Local URLs to test ==")
    for path in (
        "/admin/login",
        "/admin/home",
        "/admin/requests",
        "/admin/cases",
        "/admin/risk",
        "/admin/professional-leads",
        "/admin/professional-leads/demo",
        "/admin/organizations/requests",
    ):
        print(f"{base_url}{path}")

    print("\nNote: this branch exposes demo leads at /admin/professional-leads/demo.")


def print_mutation_summary(ctx: SeedContext, *, mode: str) -> None:
    print(f"\n== Seed summary ({mode}) ==")
    for label, values in (
        ("created", ctx.created),
        ("updated", ctx.updated),
        ("deleted", ctx.deleted),
    ):
        if not values:
            continue
        print(f"{label}:")
        for key in sorted(values):
            print(f"  {key}={values[key]}")
    if ctx.skipped:
        print("skipped:")
        for item in sorted(set(ctx.skipped)):
            print(f"  {item}")
    if ctx.warnings:
        print("warnings:")
        for item in ctx.warnings:
            print(f"  {item}")


def main() -> int:
    args = parse_args()
    with app.app_context():
        cfg = print_runtime_banner()
        ensure_safe_target(args, cfg)
        ctx = SeedContext(
            dry_run=args.dry_run,
            reset_demo=args.reset_demo,
            allow_unsafe_target=args.allow_unsafe_target,
        )

        if args.reset_demo:
            reset_demo_rows(ctx)
            if args.dry_run:
                db.session.rollback()
                print_mutation_summary(ctx, mode="dry-run reset")
                print("\nDry-run reset completed; transaction rolled back.")
                return 0
            db.session.commit()
            print_mutation_summary(ctx, mode="reset")
            print_counts(ctx)
            print("\nDemo cleanup committed.")
            return 0

        seed_demo(ctx)

        if args.dry_run:
            db.session.rollback()
            print_mutation_summary(ctx, mode="dry-run")
            print_counts(ctx)
            print_credentials_and_urls(cfg)
            print("\nDry-run completed; transaction rolled back.")
            return 0

        db.session.commit()
        print_mutation_summary(ctx, mode="commit")
        print_counts(ctx)
        print_credentials_and_urls(cfg)
        print("\nLocal demo seed committed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
