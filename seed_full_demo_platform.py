"""
Local-only full demo seed for HelpChain.

PowerShell:
  .\\.venv\\Scripts\\python.exe .\\seed_full_demo_platform.py
"""

from __future__ import annotations

import os
import random
import pathlib
import re
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import inspect
from werkzeug.security import generate_password_hash

ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.extensions import db
from backend.helpchain_backend.src.app import create_app
from backend.helpchain_backend.src.models import OrganizationAccessRequest, ProfessionalLead
from backend.models import (
    AdminUser,
    Intervenant,
    Request,
    Structure,
    StructureService,
    User,
    Volunteer,
)


ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "admin@local.dev"
# Local demo password placeholder. Override via HC_DEMO_ADMIN_PASSWORD.
# Do not commit real credentials.
ADMIN_PASSWORD = os.getenv("HC_DEMO_ADMIN_PASSWORD", "change-me-local-admin")
ADMIN_ROLE = "superadmin"
SEED_TAG = "seed_full_demo_platform"
NOW = datetime.now(UTC)

STRUCTURE_ROWS = [
    {"name": "CCAS Argenteuil", "slug": "ccas-argenteuil"},
    {"name": "Centre Social Paris 18", "slug": "centre-social-paris-18"},
    {"name": "Association Solidarite Locale", "slug": "association-solidarite-locale"},
    {"name": "Maison des Familles 92", "slug": "maison-des-familles-92"},
]

SERVICE_ROWS = [
    ("food", "Aide alimentaire"),
    ("housing", "Accompagnement logement"),
    ("health", "Acces sante"),
    ("paperwork", "Aide administrative"),
    ("transport", "Mobilite solidaire"),
    ("isolation", "Lien social"),
    ("family_support", "Soutien familial"),
]

REQUESTER_ROWS = [
    ("lea.martin", "lea.martin@demo.local"),
    ("amine.benali", "amine.benali@demo.local"),
    ("sarah.nguyen", "sarah.nguyen@demo.local"),
    ("karim.bensaid", "karim.bensaid@demo.local"),
    ("ines.bernard", "ines.bernard@demo.local"),
    ("nora.haddad", "nora.haddad@demo.local"),
]

PROFESSIONAL_ROWS = [
    {
        "name": "Claire Bernard",
        "email": "claire.bernard@demo.local",
        "phone": "+33 6 10 00 00 01",
        "location": "Argenteuil",
        "availability": "soir et week-end",
        "skills": "food,paperwork,family_support",
        "structure_slug": "ccas-argenteuil",
    },
    {
        "name": "Samir El Mansouri",
        "email": "samir.elmansouri@demo.local",
        "phone": "+33 6 10 00 00 02",
        "location": "Paris",
        "availability": "journee",
        "skills": "housing,paperwork,transport",
        "structure_slug": "centre-social-paris-18",
    },
    {
        "name": "Helene Pires",
        "email": "helene.pires@demo.local",
        "phone": "+33 6 10 00 00 03",
        "location": "Nanterre",
        "availability": "matin",
        "skills": "health,isolation",
        "structure_slug": "maison-des-familles-92",
    },
    {
        "name": "Moussa Diallo",
        "email": "moussa.diallo@demo.local",
        "phone": "+33 6 10 00 00 04",
        "location": "Saint-Denis",
        "availability": "apres-midi",
        "skills": "transport,food,isolation",
        "structure_slug": "association-solidarite-locale",
    },
    {
        "name": "Aurelie Garnier",
        "email": "aurelie.garnier@demo.local",
        "phone": "+33 6 10 00 00 05",
        "location": "Clichy",
        "availability": "soir",
        "skills": "family_support,health",
        "structure_slug": "maison-des-familles-92",
    },
]

LEAD_ROWS = [
    {
        "email": "caroline.morel@ccas-argenteuil.fr",
        "full_name": "Caroline Morel",
        "phone": "+33 1 39 10 00 01",
        "city": "Argenteuil",
        "profession": "Directrice adjointe action sociale",
        "organization": "CCAS Argenteuil",
        "availability": "RDV sous 7 jours",
        "message": "Souhaite tester un pilote pour fluidifier le suivi des situations complexes.",
        "source": "demo_page",
        "status": "new",
        "offer_note": "Piste pilote a 490 EUR / mois pour un premier perimetre.",
    },
    {
        "email": "m.thomas@paris18.fr",
        "full_name": "Mathieu Thomas",
        "phone": "+33 1 42 00 00 02",
        "city": "Paris",
        "profession": "Coordinateur insertion",
        "organization": "Centre Social Paris 18",
        "availability": "matin",
        "message": "Recherche une vue simple des demandes, de l'attribution et des relances.",
        "source": "demo_page",
        "status": "contacted",
        "offer_note": "Scenario demo suivi a 990 EUR / mois apres validation terrain.",
    },
    {
        "email": "amelie.rocher@solidarite-locale.org",
        "full_name": "Amelie Rocher",
        "phone": "+33 1 48 00 00 03",
        "city": "Saint-Denis",
        "profession": "Responsable de pole famille",
        "organization": "Association Solidarite Locale",
        "availability": "jeudi",
        "message": "Besoin d'un tableau de bord pour les parcours logement et aides urgentes.",
        "source": "demo_page",
        "status": "demo_scheduled",
        "offer_note": "Piste d'accompagnement a 2400 EUR pour un pilote multi-equipes.",
    },
    {
        "email": "nathalie.joly@mdf92.fr",
        "full_name": "Nathalie Joly",
        "phone": "+33 1 47 00 00 04",
        "city": "Nanterre",
        "profession": "Cheffe de service prevention",
        "organization": "Maison des Familles 92",
        "availability": "vendredi",
        "message": "Souhaite centraliser les demandes familles et suivre les suites donnees.",
        "source": "demo_page",
        "status": "pilot_discussion",
        "offer_note": "Scenario deploiement progressif a 5000 EUR avec cadrage initial.",
    },
    {
        "email": "contact@mission-locale-clichy.fr",
        "full_name": "Sonia Ferreira",
        "phone": "+33 1 46 00 00 05",
        "city": "Clichy",
        "profession": "Referente partenariats",
        "organization": "Mission Locale de Clichy",
        "availability": "apres-midi",
        "message": "Demande une demonstration orientee coordination jeunes et transport.",
        "source": "professionnels_pilote",
        "status": "new",
        "offer_note": "Evaluation initiale sans engagement, budget 0 EUR en phase de cadrage.",
    },
    {
        "email": "secretariat@cms-saintdenis.fr",
        "full_name": "Yassine Khelifi",
        "phone": "+33 1 49 00 00 06",
        "city": "Saint-Denis",
        "profession": "Cadre socio-educatif",
        "organization": "Centre medico-social Saint-Denis",
        "availability": "mercredi",
        "message": "Veut une solution simple pour qualifier les urgences et tracer les actions.",
        "source": "professionnels_pilote",
        "status": "contacted",
        "offer_note": "Budget projet estime a 990 EUR / mois si validation du pilote.",
    },
]

ACCESS_REQUEST_ROWS = [
    {
        "organization_name": "CCAS Argenteuil",
        "contact_name": "Caroline Morel",
        "email": "caroline.morel+access@ccas-argenteuil.fr",
        "phone": "+33 1 39 10 11 01",
        "city": "Argenteuil",
        "org_type": "ccas",
        "estimated_users": 18,
        "message": "Nous voulons tester un pilote local sur les demandes alimentaires et logement.",
        "status": "new",
    },
    {
        "organization_name": "Centre Social Paris 18",
        "contact_name": "Mathieu Thomas",
        "email": "matthieu.thomas+access@paris18.fr",
        "phone": "+33 1 42 00 11 02",
        "city": "Paris",
        "org_type": "centre_social",
        "estimated_users": 12,
        "message": "Besoin d'un espace structure avec trois administrateurs et des agents.",
        "status": "reviewed",
    },
]

REQUEST_ROWS = [
    ("Rupture de colis alimentaires pour une famille rue Jean Lurcat", "Besoin d'une mise en relation rapide avec une distribution et un suivi social.", "Argenteuil", "food", "new", "high", "ccas-argenteuil", "lea.martin", "admin_ccas_argenteuil", "claire.bernard@demo.local", 2),
    ("Demande de domiciliation administrative apres sortie d'hebergement", "La personne doit refaire ses droits et n'a plus de courrier stable.", "Paris", "paperwork", "qualified", "normal", "centre-social-paris-18", "amine.benali", "admin_centre_social_paris_18", "samir.elmansouri@demo.local", 4),
    ("Besoin de transport pour rendez-vous oncologie", "Accompagnement aller-retour vers l'hopital pour une personne isolee.", "Nanterre", "transport", "assigned", "urgent", "maison-des-familles-92", "sarah.nguyen", "admin_maison_des_familles_92", "helene.pires@demo.local", 1),
    ("Soutien pour dossier MDPH enfant TSA", "La mere a besoin d'aide pour les pieces et le calendrier de depot.", "Saint-Denis", "paperwork", "in_progress", "high", "association-solidarite-locale", "karim.bensaid", "admin_association_solidarite_locale", "moussa.diallo@demo.local", 7),
    ("Recherche de solution d'hebergement d'urgence apres separation", "Parent avec deux enfants sans solution stable a partir de ce soir.", "Clichy", "housing", "new", "urgent", "maison-des-familles-92", "ines.bernard", "admin_maison_des_familles_92", "aurelie.garnier@demo.local", 0),
    ("Isolement d'une personne agee sans visites depuis quinze jours", "Le voisinage alerte sur une rupture de lien et des courses non faites.", "Argenteuil", "isolation", "qualified", "normal", "ccas-argenteuil", "nora.haddad", "admin_ccas_argenteuil", "claire.bernard@demo.local", 12),
    ("Demande de panier bebe et couches", "Jeune mere en attente de versement, besoin ponctuel cette semaine.", "Paris", "food", "assigned", "high", "centre-social-paris-18", "lea.martin", "admin_centre_social_paris_18", "samir.elmansouri@demo.local", 5),
    ("Accompagnement pour maintien dans le logement", "Menace d'expulsion, besoin d'un point budget et d'une mediation bailleur.", "Saint-Denis", "housing", "in_progress", "high", "association-solidarite-locale", "amine.benali", "admin_association_solidarite_locale", "moussa.diallo@demo.local", 9),
    ("Besoin de mutuelle solidaire et orientation sante", "Personne sans medecin traitant qui renonce aux soins.", "Nanterre", "health", "resolved", "normal", "maison-des-familles-92", "sarah.nguyen", "admin_maison_des_familles_92", "helene.pires@demo.local", 14),
    ("Aide pour remplir dossier de surendettement", "Le foyer souhaite etre accompagne pour ne pas laisser expirer les delais.", "Clichy", "paperwork", "closed", "normal", "centre-social-paris-18", "karim.bensaid", "admin_centre_social_paris_18", "samir.elmansouri@demo.local", 20),
    ("Demande de tickets transport pour stage d'insertion", "Sans avance possible pour quatre trajets la semaine prochaine.", "Paris", "transport", "new", "low", "centre-social-paris-18", "ines.bernard", "admin_centre_social_paris_18", "samir.elmansouri@demo.local", 3),
    ("Famille monoparentale en attente d'aide alimentaire", "Stock vide jusqu'au prochain versement RSA dans six jours.", "Argenteuil", "food", "qualified", "high", "ccas-argenteuil", "nora.haddad", "admin_ccas_argenteuil", "claire.bernard@demo.local", 6),
    ("Besoin de relais pour rendez-vous CAF non honore", "Dossier suspendu, la personne ne comprend plus les pieces demandees.", "Saint-Denis", "paperwork", "assigned", "normal", "association-solidarite-locale", "lea.martin", "admin_association_solidarite_locale", "moussa.diallo@demo.local", 8),
    ("Demande de visites de convivialite pour une senior", "Perte d'autonomie legere et rupture de lien social depuis le deces du conjoint.", "Nanterre", "isolation", "in_progress", "normal", "maison-des-familles-92", "amine.benali", "admin_maison_des_familles_92", "helene.pires@demo.local", 11),
    ("Orientation vers PASS hospitaliere", "Sans droits ouverts, douleurs recurrentes et suivi interrompu.", "Paris", "health", "resolved", "high", "centre-social-paris-18", "sarah.nguyen", "admin_centre_social_paris_18", "samir.elmansouri@demo.local", 13),
    ("Besoin d'un accompagnement parental apres expulsion de l'ado", "Tensions fortes au domicile, besoin d'un relais educatif.", "Clichy", "family_support", "new", "high", "maison-des-familles-92", "karim.bensaid", "admin_maison_des_familles_92", "aurelie.garnier@demo.local", 2),
    ("Demande de soutien pour budget energie", "Impayes et menace de coupure, besoin d'un diagnostic rapide.", "Argenteuil", "housing", "qualified", "urgent", "ccas-argenteuil", "ines.bernard", "admin_ccas_argenteuil", "claire.bernard@demo.local", 10),
    ("Accompagnement numerique pour renouvellement titre de sejour", "La personne ne maitrise pas les demarches en ligne et a une echeance proche.", "Paris", "paperwork", "assigned", "urgent", "centre-social-paris-18", "nora.haddad", "admin_centre_social_paris_18", "samir.elmansouri@demo.local", 4),
    ("Aide transport pour consultation pedopsy", "Absence de solution pour amener l'enfant au rendez-vous mensuel.", "Nanterre", "transport", "in_progress", "normal", "maison-des-familles-92", "lea.martin", "admin_maison_des_familles_92", "helene.pires@demo.local", 16),
    ("Signalement d'isolement apres sortie d'hospitalisation", "Retour a domicile sans entourage, besoin de veille et de courses.", "Saint-Denis", "isolation", "resolved", "high", "association-solidarite-locale", "amine.benali", "admin_association_solidarite_locale", "moussa.diallo@demo.local", 18),
]

SUMMARY = {
    "admins_created": 0,
    "admins_updated": 0,
    "structures": 0,
    "requests": 0,
    "professionals": 0,
    "leads": 0,
}
SKIPPED: list[str] = []
TABLE_COLUMNS: dict[str, set[str]] = {}


def remember_skip(name: str, reason: str | None = None) -> None:
    message = name if not reason else f"{name} ({reason})"
    SKIPPED.append(message)
    print(f"Skipped: {message}")


def safe_commit(section: str) -> bool:
    try:
        db.session.commit()
        return True
    except Exception as exc:
        db.session.rollback()
        print(f"[ERROR] {section}: {exc}")
        return False


def get_or_create(model, **lookup):
    defaults = lookup.pop("defaults", None) or {}
    row = model.query.filter_by(**lookup).first()
    created = False
    if row is None:
        params = dict(lookup)
        params.update(defaults)
        row = model(**params)
        db.session.add(row)
        created = True
    return row, created


def model_table_name(model) -> str | None:
    table = getattr(model, "__table__", None)
    return getattr(table, "name", None)


def table_exists(model) -> bool:
    table_name = model_table_name(model)
    return bool(table_name and table_name in TABLE_COLUMNS)


def table_has_column(model, column_name: str) -> bool:
    table_name = model_table_name(model)
    return bool(table_name and column_name in TABLE_COLUMNS.get(table_name, set()))


def can_seed_model(name: str, model, required_columns: list[str] | tuple[str, ...]) -> bool:
    if model is None:
        remember_skip(name, "model import unavailable")
        return False
    if not table_exists(model):
        remember_skip(name, "table missing")
        return False
    missing = [column for column in required_columns if not table_has_column(model, column)]
    if missing:
        remember_skip(name, f"missing columns: {', '.join(missing)}")
        return False
    return True


def set_if_hasattr(obj, attr_name: str, value) -> bool:
    if not table_has_column(type(obj), attr_name):
        return False
    try:
        setattr(obj, attr_name, value)
        return True
    except Exception:
        return False


def set_admin_password(admin: AdminUser, password: str) -> None:
    try:
        admin.set_password(password)
    except Exception:
        admin.password_hash = generate_password_hash(password)


def build_table_columns() -> None:
    inspector = inspect(db.session.get_bind())
    for table_name in inspector.get_table_names():
        TABLE_COLUMNS[table_name] = {column["name"] for column in inspector.get_columns(table_name)}


def assert_safe_local_sqlite(app) -> None:
    uri = (app.config.get("SQLALCHEMY_DATABASE_URI") or "").strip()
    env_uri = (os.getenv("DATABASE_URL") or "").strip()
    print(f"Effective DB URI: {uri or '<empty>'}")

    combined = " ".join(part for part in (uri, env_uri) if part).lower()
    if any(marker in combined for marker in ("postgres", "postgresql", "neon", "render")):
        raise SystemExit(
            "Refusing to seed: database target contains postgres/postgresql/neon/render."
        )

    if not uri.lower().startswith("sqlite:"):
        raise SystemExit("Refusing to seed: only local SQLite databases are allowed.")

    if uri.lower() != "sqlite:///:memory:" and not uri.lower().startswith("sqlite:///"):
        raise SystemExit("Refusing to seed: expected a local SQLite file URI.")


def ensure_structures() -> dict[str, Structure]:
    structure_map: dict[str, Structure] = {}
    if not can_seed_model("structures", Structure, ["name", "slug"]):
        return structure_map

    for row in STRUCTURE_ROWS:
        structure, _created = get_or_create(
            Structure,
            slug=row["slug"],
            defaults={"name": row["name"]},
        )
        set_if_hasattr(structure, "name", row["name"])
        set_if_hasattr(structure, "slug", row["slug"])
        set_if_hasattr(structure, "status", "active")
        structure_map[row["slug"]] = structure

    if safe_commit("structures"):
        SUMMARY["structures"] = len(structure_map)

    if can_seed_model("structure_services", StructureService, ["structure_id", "code", "name"]):
        for structure in structure_map.values():
            for code, name in SERVICE_ROWS:
                service, _created = get_or_create(
                    StructureService,
                    structure_id=structure.id,
                    code=code,
                    defaults={"name": name},
                )
                set_if_hasattr(service, "name", name)
                set_if_hasattr(service, "is_active", True)
        safe_commit("structure_services")

    return structure_map


def ensure_admins(structure_map: dict[str, Structure]) -> dict[str, AdminUser]:
    admin_map: dict[str, AdminUser] = {}
    if not can_seed_model("admin_users", AdminUser, ["username", "email", "password_hash"]):
        return admin_map

    default_structure = structure_map.get("ccas-argenteuil") or next(iter(structure_map.values()), None)
    admin = AdminUser.query.filter(
        (AdminUser.username == ADMIN_USERNAME) | (AdminUser.email == ADMIN_EMAIL)
    ).first()
    created = admin is None
    if admin is None:
        admin = AdminUser(
            username=ADMIN_USERNAME,
            email=ADMIN_EMAIL,
            role=ADMIN_ROLE,
            is_active=True,
            structure_id=getattr(default_structure, "id", None),
        )
        db.session.add(admin)
    set_if_hasattr(admin, "username", ADMIN_USERNAME)
    set_if_hasattr(admin, "email", ADMIN_EMAIL)
    set_if_hasattr(admin, "role", ADMIN_ROLE)
    set_if_hasattr(admin, "is_active", True)
    set_if_hasattr(admin, "structure_id", getattr(default_structure, "id", None))
    set_admin_password(admin, ADMIN_PASSWORD)
    admin_map[ADMIN_USERNAME] = admin
    SUMMARY["admins_created"] += 1 if created else 0
    SUMMARY["admins_updated"] += 0 if created else 1

    for structure in structure_map.values():
        username = f"admin_{structure.slug.replace('-', '_')}"
        email = f"{username}@local.dev"
        row = AdminUser.query.filter_by(username=username).first()
        row_created = row is None
        if row is None:
            row = AdminUser(
                username=username,
                email=email,
                role="admin",
                is_active=True,
                structure_id=structure.id,
            )
            db.session.add(row)
        set_if_hasattr(row, "email", email)
        set_if_hasattr(row, "role", "admin")
        set_if_hasattr(row, "is_active", True)
        set_if_hasattr(row, "structure_id", structure.id)
        set_admin_password(row, ADMIN_PASSWORD)
        admin_map[username] = row
        SUMMARY["admins_created"] += 1 if row_created else 0
        SUMMARY["admins_updated"] += 0 if row_created else 1

    safe_commit("admin_users")
    return admin_map


def ensure_requesters(structure_map: dict[str, Structure]) -> dict[str, User]:
    user_map: dict[str, User] = {}
    if not can_seed_model("users", User, ["username", "email", "password_hash"]):
        return user_map

    structures = list(structure_map.values())
    for index, (username, email) in enumerate(REQUESTER_ROWS):
        row = User.query.filter_by(username=username).first()
        if row is None:
            row = User(
                username=username,
                email=email,
                password_hash="placeholder",
                role="requester",
                is_active=True,
                structure_id=structures[index % len(structures)].id if structures else None,
            )
            db.session.add(row)
        set_if_hasattr(row, "email", email)
        set_if_hasattr(row, "role", "requester")
        set_if_hasattr(row, "is_active", True)
        if structures:
            set_if_hasattr(row, "structure_id", structures[index % len(structures)].id)
        row.set_password("RequesterDemo2026!")
        user_map[username] = row

    safe_commit("users")
    return user_map


def ensure_professionals(structure_map: dict[str, Structure]) -> dict[str, int]:
    professional_ids: dict[str, int] = {}

    volunteer_enabled = can_seed_model("volunteers", Volunteer, ["email"])
    intervenant_enabled = can_seed_model("intervenants", Intervenant, ["structure_id"])

    if not volunteer_enabled and not intervenant_enabled:
        return professional_ids

    created_count = 0
    for row in PROFESSIONAL_ROWS:
        structure = structure_map.get(row["structure_slug"])
        if structure is None:
            continue

        volunteer = None
        if volunteer_enabled:
            volunteer = Volunteer.query.filter_by(email=row["email"]).first()
            if volunteer is None:
                volunteer = Volunteer(email=row["email"])
                db.session.add(volunteer)
                created_count += 1
            set_if_hasattr(volunteer, "name", row["name"])
            set_if_hasattr(volunteer, "phone", row["phone"])
            set_if_hasattr(volunteer, "location", row["location"])
            set_if_hasattr(volunteer, "availability", row["availability"])
            set_if_hasattr(volunteer, "skills", row["skills"])
            set_if_hasattr(volunteer, "is_active", True)
            professional_ids[row["email"]] = getattr(volunteer, "id", 0)

        if intervenant_enabled:
            intervenant = Intervenant.query.filter_by(
                structure_id=structure.id,
                email=row["email"],
            ).first()
            if intervenant is None:
                intervenant = Intervenant(structure_id=structure.id, email=row["email"])
                db.session.add(intervenant)
                created_count += 1
            set_if_hasattr(intervenant, "name", row["name"])
            set_if_hasattr(intervenant, "phone", row["phone"])
            set_if_hasattr(intervenant, "location", row["location"])
            set_if_hasattr(intervenant, "actor_type", "volunteer")
            set_if_hasattr(intervenant, "is_active", True)
            if volunteer is not None:
                set_if_hasattr(intervenant, "legacy_volunteer_id", getattr(volunteer, "id", None))

    if safe_commit("professionals"):
        SUMMARY["professionals"] = created_count

    return professional_ids


def ensure_leads(admin_map: dict[str, AdminUser]) -> None:
    if not can_seed_model("professional_leads", ProfessionalLead, ["email", "profession", "status"]):
        return

    owners = [row for key, row in admin_map.items() if key != ADMIN_USERNAME]
    for index, row in enumerate(LEAD_ROWS):
        lead = ProfessionalLead.query.filter_by(email=row["email"]).first()
        if lead is None:
            lead = ProfessionalLead(email=row["email"], profession=row["profession"], status=row["status"])
            db.session.add(lead)
        owner = owners[index % len(owners)] if owners else None
        created_at = NOW - timedelta(days=12 - min(index, 11), hours=index)
        set_if_hasattr(lead, "email", row["email"])
        set_if_hasattr(lead, "full_name", row["full_name"])
        set_if_hasattr(lead, "phone", row["phone"])
        set_if_hasattr(lead, "city", row["city"])
        set_if_hasattr(lead, "profession", row["profession"])
        set_if_hasattr(lead, "organization", row["organization"])
        set_if_hasattr(lead, "availability", row["availability"])
        set_if_hasattr(lead, "message", row["message"])
        set_if_hasattr(lead, "source", row["source"])
        set_if_hasattr(lead, "locale", "fr")
        set_if_hasattr(lead, "status", row["status"])
        set_if_hasattr(lead, "owner_admin_id", getattr(owner, "id", None))
        set_if_hasattr(lead, "last_touched_by_admin_id", getattr(owner, "id", None))
        set_if_hasattr(lead, "notes", row["offer_note"])
        set_if_hasattr(lead, "created_at", created_at)
        set_if_hasattr(lead, "contacted_at", created_at + timedelta(days=1))
        set_if_hasattr(lead, "last_touched_at", created_at + timedelta(days=2))
        set_if_hasattr(lead, "next_action_at", created_at + timedelta(days=4))
        set_if_hasattr(lead, "next_action_note", "Relancer le contact pour cadrer le pilote.")

    if safe_commit("professional_leads"):
        SUMMARY["leads"] = len(LEAD_ROWS)


def ensure_access_requests(admin_map: dict[str, AdminUser]) -> None:
    if not can_seed_model("organization_access_requests", OrganizationAccessRequest, ["organization_name", "contact_name", "email", "status"]):
        return

    reviewer = admin_map.get(ADMIN_USERNAME)
    for index, row in enumerate(ACCESS_REQUEST_ROWS):
        access_request = OrganizationAccessRequest.query.filter_by(email=row["email"]).first()
        if access_request is None:
            access_request = OrganizationAccessRequest(
                organization_name=row["organization_name"],
                contact_name=row["contact_name"],
                email=row["email"],
            )
            db.session.add(access_request)
        set_if_hasattr(access_request, "organization_name", row["organization_name"])
        set_if_hasattr(access_request, "contact_name", row["contact_name"])
        set_if_hasattr(access_request, "email", row["email"])
        set_if_hasattr(access_request, "phone", row["phone"])
        set_if_hasattr(access_request, "city", row["city"])
        set_if_hasattr(access_request, "org_type", row["org_type"])
        set_if_hasattr(access_request, "estimated_users", row["estimated_users"])
        set_if_hasattr(access_request, "message", row["message"])
        set_if_hasattr(access_request, "status", row["status"])
        set_if_hasattr(access_request, "reviewed_by_admin_id", getattr(reviewer, "id", None))
        set_if_hasattr(access_request, "reviewed_at", NOW - timedelta(days=6 - index))
        set_if_hasattr(access_request, "internal_notes", f"{SEED_TAG}: demande demo locale.")
        set_if_hasattr(access_request, "next_action_at", NOW + timedelta(days=index + 1))
        set_if_hasattr(access_request, "next_action_note", "Prevoir un point cadrage structure et acces.")

    safe_commit("organization_access_requests")


def service_for(structure: Structure, category: str):
    if not table_exists(StructureService):
        return None
    return StructureService.query.filter_by(structure_id=structure.id, code=category).first()


def ensure_requests(
    structure_map: dict[str, Structure],
    admin_map: dict[str, AdminUser],
    requester_map: dict[str, User],
) -> None:
    if not can_seed_model("requests", Request, ["title", "user_id"]):
        return

    for index, row in enumerate(REQUEST_ROWS):
        title, description, city, category, status, priority, structure_slug, requester_username, owner_username, professional_email, days_ago = row
        structure = structure_map.get(structure_slug)
        requester = requester_map.get(requester_username)
        owner = admin_map.get(owner_username)
        if structure is None or requester is None:
            continue

        request_obj = Request.query.filter_by(title=title).first()
        if request_obj is None:
            request_obj = Request(title=title, user_id=requester.id)
            db.session.add(request_obj)

        created_at = NOW - timedelta(days=days_ago, hours=(index % 5) + 1)
        updated_at = created_at + timedelta(hours=12 + (index % 6))

        set_if_hasattr(request_obj, "title", title)
        set_if_hasattr(request_obj, "description", description)
        set_if_hasattr(request_obj, "message", description)
        set_if_hasattr(request_obj, "email", requester.email)
        set_if_hasattr(request_obj, "city", city)
        set_if_hasattr(request_obj, "region", "Ile-de-France")
        set_if_hasattr(request_obj, "country", "France")
        set_if_hasattr(request_obj, "category", category)
        set_if_hasattr(request_obj, "status", status)
        set_if_hasattr(request_obj, "priority", priority)
        set_if_hasattr(request_obj, "source_channel", SEED_TAG)
        set_if_hasattr(request_obj, "user_id", requester.id)
        set_if_hasattr(request_obj, "structure_id", structure.id)
        set_if_hasattr(request_obj, "owner_id", getattr(owner, "id", None))
        set_if_hasattr(request_obj, "owned_at", created_at + timedelta(hours=2))
        set_if_hasattr(request_obj, "created_at", created_at)
        set_if_hasattr(request_obj, "updated_at", updated_at)
        set_if_hasattr(request_obj, "location_text", f"{city}, France")
        set_if_hasattr(request_obj, "postcode", f"75{index:03d}")
        service = service_for(structure, category)
        if service is not None:
            set_if_hasattr(request_obj, "service_id", service.id)
        if status in {"resolved", "closed"}:
            set_if_hasattr(request_obj, "completed_at", updated_at + timedelta(hours=6))

    if safe_commit("requests"):
        SUMMARY["requests"] = len(REQUEST_ROWS)


def print_summary() -> None:
    print("")
    print("Seed summary")
    print(f"admins created/updated: {SUMMARY['admins_created']} / {SUMMARY['admins_updated']}")
    print(f"structures: {SUMMARY['structures']}")
    print(f"requests: {SUMMARY['requests']}")
    print(f"volunteers/professionals: {SUMMARY['professionals']}")
    print(f"leads: {SUMMARY['leads']}")
    print("skipped sections:")
    if SKIPPED:
        for item in SKIPPED:
            print(f"- {item}")
    else:
        print("- none")


def main() -> int:
    app = create_app()
    with app.app_context():
        assert_safe_local_sqlite(app)
        build_table_columns()

        structure_map = ensure_structures()
        admin_map = ensure_admins(structure_map) if structure_map else {}
        requester_map = ensure_requesters(structure_map) if structure_map else {}
        ensure_professionals(structure_map)
        ensure_leads(admin_map)
        ensure_access_requests(admin_map)
        ensure_requests(structure_map, admin_map, requester_map)
        print_summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
