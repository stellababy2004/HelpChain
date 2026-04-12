#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path


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
    AdminUser,
    Intervenant,
    NotificationJob,
    Request,
    RequestActivity,
    Structure,
    User,
)


DEMO_MARKER = "Demo Boulogne"
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


def _ensure_demo_branch() -> str:
    uri = _runtime_uri().strip()
    norm = uri.lower()
    force_demo = (os.getenv("HC_ALLOW_DEMO_SEED") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not uri:
        raise RuntimeError("Refusing demo seed: runtime DB URL is empty.")
    if norm.startswith("sqlite:"):
        raise RuntimeError(
            f"Refusing demo seed: sqlite target is not allowed. Actual={_mask_db_url(uri)}"
        )
    if "-pooler" in norm:
        raise RuntimeError(
            f"Refusing demo seed: pooled Neon URL is not allowed. Actual={_mask_db_url(uri)}"
        )
    if not force_demo and not norm.startswith(("postgresql://", "postgresql+psycopg://")):
        raise RuntimeError(
            "Refusing demo seed: unsupported DB URL for demo execution. "
            f"Actual={_mask_db_url(uri)}"
        )
    return uri


def _get_or_create_structure(name: str, slug: str, *, status: str = "active") -> Structure:
    row = Structure.query.filter_by(slug=slug).first()
    if row is None:
        row = Structure(name=name, slug=slug, status=status)
        db.session.add(row)
    else:
        row.name = name
        row.status = status
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
) -> AdminUser:
    row = AdminUser.query.filter_by(username=username).first()
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
    return row


def _get_or_create_user(
    *,
    username: str,
    email: str,
    structure_id: int | None,
    role: str = "requester",
    password: str = "DemoBoulogne123!",
) -> User:
    row = User.query.filter_by(username=username).first()
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
) -> Intervenant:
    row = Intervenant.query.filter_by(email=email).first()
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
    row.is_active = True
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
    status: str = "qualified",
) -> ProfessionalLead:
    row = ProfessionalLead.query.filter_by(email=email).first()
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
    row.notes = f"{DEMO_MARKER} | adresse: {address}"
    row.last_touched_at = NOW
    row.last_touched_by_admin_id = owner_admin_id
    return row


def _upsert_request(
    seed: RequestSeed,
    *,
    structures: dict[str, Structure],
    admins: dict[str, AdminUser],
    users: dict[str, User],
) -> Request:
    row = Request.query.filter_by(title=seed.title).first()
    if row is None:
        row = Request(title=seed.title, user_id=users[seed.requester_username].id)
        db.session.add(row)
    created_at = NOW - timedelta(hours=seed.created_hours_ago)
    updated_at = NOW - timedelta(hours=seed.updated_hours_ago)
    row.title = seed.title
    row.description = seed.description
    row.message = seed.description
    row.name = f"{DEMO_MARKER} – demandeur"
    row.email = users[seed.requester_username].email
    row.phone = "+33 1 84 60 92 00"
    row.city = "Boulogne-Billancourt"
    row.region = "Île-de-France"
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
) -> None:
    row = NotificationJob.query.filter_by(subject=subject, recipient=recipient).first()
    created_at = NOW - timedelta(hours=created_hours_ago)
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


def _request_seeds() -> list[RequestSeed]:
    return [
        RequestSeed("r1", "Demo Boulogne – Personne âgée isolée sans visite récente", "Signalement d'une personne âgée vivant seule, sans passage familial récent et avec rupture de suivi de voisinage.", "ccas-boulogne-demo", "isolation", "open", "high", "critical", 94, None, "demo.requester.01", "15 Rue de Billancourt", 120, 96, [118], ("no_owner", "not_seen_72h")),
        RequestSeed("r2", "Demo Boulogne – Sortie d’hospitalisation sans relais infirmier", "Retour à domicile après hospitalisation, besoin d'une coordination infirmière et d'un passage rapide.", "reseau-sante-boulogne-demo", "health", "in_progress", "high", "attention", 72, "admin", "demo.requester.02", "32 Route de la Reine", 60, 10, [20, 9], ()),
        RequestSeed("r3", "Demo Boulogne – Aide alimentaire urgente pour parent isolé", "Parent isolé avec deux enfants, réfrigérateur vide et aucune aide disponible pour le week-end.", "association-solidarite-92-demo-boulogne", "food", "new", "critical", "critical", 96, None, "demo.requester.03", "41 Rue du Château", 30, 28, [29], ("no_owner",)),
        RequestSeed("r4", "Demo Boulogne – Orientation protection après violence intrafamiliale", "Demande d'orientation discrète vers un dispositif de protection après épisode de violence au domicile.", "plateforme-protection-familles-92-demo-boulogne", "violence", "open", "high", "critical", 93, "ops.boulogne.demo", "demo.requester.04", "8 Rue des Abondances", 44, 22, [40, 21], ()),
        RequestSeed("r5", "Demo Boulogne – Besoin d’hébergement temporaire immédiat", "Ménage sans solution d'hébergement pour la nuit, avec un enfant mineur à prendre en charge rapidement.", "association-solidarite-92-demo-boulogne", "housing", "open", "critical", "critical", 91, None, "demo.requester.05", "63 Avenue Jean-Baptiste Clément", 84, 80, [83], ("no_owner", "not_seen_72h")),
        RequestSeed("r6", "Demo Boulogne – Ouverture de droits sociaux bloquée", "Dossier RSA et complémentaire santé suspendus faute de pièces, demande d'appui administratif.", "ccas-boulogne-demo", "admin_help", "in_progress", "normal", "standard", 36, "ops.boulogne.demo", "demo.requester.06", "6 Rue Escudier", 72, 26, [48, 25], ()),
        RequestSeed("r7", "Demo Boulogne – Personne vulnérable sans médecin traitant", "Personne âgée fragile sans médecin traitant disponible, besoin d'orientation santé et coordination.", "reseau-sante-boulogne-demo", "health", "open", "high", "attention", 68, None, "demo.requester.07", "24 Rue Fessart", 55, 50, [52], ("no_owner",)),
        RequestSeed("r8", "Demo Boulogne – Suivi psychologique après rupture familiale", "Situation d'isolement après séparation brutale, demande de soutien psychologique et de relais social.", "cellule-coordination-senior-demo-boulogne", "isolation", "in_progress", "normal", "attention", 61, "admin", "demo.requester.08", "52 Boulevard Jean Jaurès", 38, 6, [18, 5], ()),
        RequestSeed("r9", "Demo Boulogne – Appui juridique maintien dans le logement", "Besoin d'un conseil juridique léger après réception d'une mise en demeure liée au bail.", "plateforme-protection-familles-92-demo-boulogne", "orientation", "open", "normal", "standard", 28, "ops.boulogne.demo", "demo.requester.09", "14 Rue de Sèvres", 96, 70, [92], ("not_seen_72h",)),
        RequestSeed("r10", "Demo Boulogne – Signalement d’isolement sévère senior", "Voisinage inquiet pour une senior très isolée, sans réponse au téléphone depuis plusieurs jours.", "cellule-coordination-senior-demo-boulogne", "isolation", "open", "high", "critical", 89, None, "demo.requester.10", "11 Rue Gambetta", 100, 98, [99], ("no_owner", "not_seen_72h")),
        RequestSeed("r11", "Demo Boulogne – Coordination multi-acteurs après hospitalisation", "Coordination entre CCAS, infirmière libérale et service social après sortie de chirurgie.", "reseau-sante-boulogne-demo", "orientation", "in_progress", "high", "attention", 66, "admin", "demo.requester.11", "17 Avenue Pierre Grenier", 42, 3, [24, 2], ()),
        RequestSeed("r12", "Demo Boulogne – Dossier administratif sans réponse récente", "Aucune réponse de l'usager depuis plusieurs relances sur un dossier d'aide administrative.", "ccas-boulogne-demo", "admin_help", "open", "normal", "attention", 60, "ops.boulogne.demo", "demo.requester.12", "29 Rue du Vieux Pont de Sèvres", 90, 88, [89], ("not_seen_72h",)),
        RequestSeed("r13", "Demo Boulogne – Demande alimentaire ponctuelle résolue", "Livraison d'un colis alimentaire exceptionnelle finalisée avec confirmation du bénéficiaire.", "association-solidarite-92-demo-boulogne", "food", "done", "normal", "standard", 18, "admin", "demo.requester.13", "4 Rue de l’Ancienne Mairie", 48, 12, [24, 11], ()),
        RequestSeed("r14", "Demo Boulogne – Orientation sociale clôturée avec succès", "Orientation vers assistante sociale de secteur finalisée et rendez-vous honoré.", "ccas-boulogne-demo", "orientation", "done", "normal", "standard", 12, "ops.boulogne.demo", "demo.requester.14", "36 Rue Gallieni", 65, 14, [36, 13], ()),
        RequestSeed("r15", "Demo Boulogne – Doublon de saisie hébergement", "Demande créée en doublon après un appel répété, à annuler sans suite.", "association-solidarite-92-demo-boulogne", "housing", "cancelled", "low", "standard", 8, None, "demo.requester.15", "7 Rue de Solférino", 22, 20, [21], ()),
        RequestSeed("r16", "Demo Boulogne – Urgence sociale critique sans responsable", "Situation critique : personne seule, sans ressources immédiates et sans responsable territorial affecté.", "ccas-boulogne-demo", "emergency", "new", "critical", "critical", 98, None, "demo.requester.16", "55 Rue d’Aguesseau", 18, 17, [17], ("no_owner",)),
    ]


def _case_seeds() -> list[CaseSeed]:
    return [
        CaseSeed("r16", "new", "critical", 97, None, None, 18, 17, (("case_created", "Demande créée et placée en file critique.", 17, "internal"), ("triage_scored", "Triage initial: risque critique confirmé.", 16, "internal")), ()),
        CaseSeed("r3", "new", "critical", 92, None, None, 30, 23, (("case_created", "Demande créée après signalement alimentaire.", 29, "internal"), ("note_added", "Besoin de colis alimentaire sous 24h.", 23, "internal")), ()),
        CaseSeed("r1", "triaged", "high", 84, None, "claire.martin.lead@boulogne.demo", 120, 94, (("case_created", "Dossier senior créé.", 118, "internal"), ("triage_scored", "Triage effectué par l'équipe senior.", 110, "internal"), ("note_added", "Absence de visite signalée depuis plusieurs jours.", 94, "internal")), (("professional_lead", "primary_professional", None, "claire.martin.lead@boulogne.demo", None),)),
        CaseSeed("r7", "triaged", "high", 73, None, "dr.sarah.cohen.demo@boulogne.demo", 55, 49, (("case_created", "Dossier santé ouvert.", 54, "internal"), ("triage_scored", "Niveau attention retenu.", 50, "internal")), (("professional_lead", "primary_professional", None, "dr.sarah.cohen.demo@boulogne.demo", None),)),
        CaseSeed("r4", "assigned", "high", 88, "ops.boulogne.demo", "ines.roche.demo@boulogne.demo", 44, 6, (("case_created", "Dossier protection ouvert.", 43, "internal"), ("owner_assigned", "Responsable territorial affecté.", 20, "internal"), ("professional_assigned", "Professionnelle de référence assignée.", 6, "internal")), (("admin_user", "owner", "ops.boulogne.demo.user", None, None), ("professional_lead", "primary_professional", None, "ines.roche.demo@boulogne.demo", None))),
        CaseSeed("r9", "assigned", "normal", 44, "admin", "antoine.lefevre.demo@boulogne.demo", 96, 80, (("case_created", "Dossier juridique enregistré.", 95, "internal"), ("owner_assigned", "Prise en charge par l'administrateur.", 90, "internal"), ("note_added", "En attente de retour du bailleur.", 80, "internal")), (("admin_user", "owner", "admin.user", None, None), ("professional_lead", "primary_professional", None, "antoine.lefevre.demo@boulogne.demo", None))),
        CaseSeed("r2", "in_progress", "high", 75, "admin", "dr.sarah.cohen.demo@boulogne.demo", 60, 4, (("case_created", "Suivi post-hospitalisation démarré.", 58, "internal"), ("owner_assigned", "Admin référent nommé.", 40, "internal"), ("professional_assigned", "Passage infirmier coordonné.", 10, "internal"), ("note_added", "Compte-rendu de visite transmis.", 4, "internal")), (("admin_user", "owner", "admin.user", None, None), ("professional_lead", "primary_professional", None, "dr.sarah.cohen.demo@boulogne.demo", None), ("association", "coordinator", None, None, "CCAS Boulogne-Billancourt - Demo Boulogne"))),
        CaseSeed("r11", "in_progress", "high", 70, "ops.boulogne.demo", "julien.moreau.demo@boulogne.demo", 42, 2, (("case_created", "Coordination multi-acteurs ouverte.", 41, "internal"), ("owner_assigned", "Référent pilotage nommé.", 20, "internal"), ("participant_added", "Ajout d'un partenaire santé.", 8, "internal"), ("note_added", "Point de coordination du matin saisi.", 2, "internal")), (("admin_user", "owner", "ops.boulogne.demo.user", None, None), ("professional_lead", "primary_professional", None, "julien.moreau.demo@boulogne.demo", None), ("association", "coordinator", None, None, "Réseau Santé Boulogne - Demo Boulogne"))),
        CaseSeed("r13", "resolved", "normal", 24, "admin", "camille.laurent.demo@boulogne.demo", 48, 11, (("case_created", "Demande alimentaire enregistrée.", 47, "internal"), ("owner_assigned", "Responsable affecté.", 35, "internal"), ("case_resolved", "Colis remis et confirmation obtenue.", 11, "public")), (("admin_user", "owner", "admin.user", None, None),)),
        CaseSeed("r14", "closed", "normal", 12, "ops.boulogne.demo", "sophie.bernard.demo@boulogne.demo", 65, 13, (("case_created", "Orientation sociale ouverte.", 64, "internal"), ("owner_assigned", "Référent nommé.", 40, "internal"), ("case_resolved", "Orientation réalisée.", 20, "public"), ("case_closed", "Clôture après confirmation du rendez-vous.", 13, "public")), (("admin_user", "owner", "ops.boulogne.demo.user", None, None),)),
        CaseSeed("r15", "cancelled", "low", 5, None, None, 22, 20, (("case_created", "Doublon détecté à l'accueil.", 21, "internal"), ("status_changed", "Annulation pour doublon de saisie.", 20, "internal")), ()),
    ]


def seed() -> dict[str, int]:
    uri = _ensure_demo_branch()
    print(f"Seeding against {_mask_db_url(uri)}")

    structures = {
        "ccas-boulogne-demo": _get_or_create_structure("CCAS Boulogne-Billancourt - Demo Boulogne", "ccas-boulogne-demo"),
        "association-solidarite-92-demo-boulogne": _get_or_create_structure("Association Solidarité 92 - Demo Boulogne", "association-solidarite-92-demo-boulogne"),
        "reseau-sante-boulogne-demo": _get_or_create_structure("Réseau Santé Boulogne - Demo Boulogne", "reseau-sante-boulogne-demo"),
        "cellule-coordination-senior-demo-boulogne": _get_or_create_structure("Cellule Coordination Senior - Demo Boulogne", "cellule-coordination-senior-demo-boulogne"),
        "plateforme-protection-familles-92-demo-boulogne": _get_or_create_structure("Plateforme Protection Familles 92 - Demo Boulogne", "plateforme-protection-familles-92-demo-boulogne"),
    }
    db.session.flush()

    existing_admin = AdminUser.query.filter_by(username="admin").first()
    if existing_admin is None:
        existing_admin = _get_or_create_admin(
            username="admin",
            email="admin.demo.boulogne@helpchain.demo",
            role="superadmin",
            structure_id=None,
        )
    else:
        existing_admin.is_active = True
        if not existing_admin.email:
            existing_admin.email = "admin.demo.boulogne@helpchain.demo"
        if not existing_admin.role:
            existing_admin.role = "superadmin"

    admins = {
        "admin": existing_admin,
        "ops.boulogne.demo": _get_or_create_admin(
            username="ops.boulogne.demo",
            email="ops.boulogne.demo@helpchain.demo",
            role="ops",
            structure_id=structures["ccas-boulogne-demo"].id,
        ),
    }
    db.session.flush()

    user_lookup: dict[str, User] = {
        "admin.user": _get_or_create_user(
            username="admin",
            email="admin.demo.boulogne@helpchain.demo",
            structure_id=structures["ccas-boulogne-demo"].id,
            role="superadmin",
        ),
        "ops.boulogne.demo.user": _get_or_create_user(
            username="ops.boulogne.demo",
            email="ops.boulogne.demo@helpchain.demo",
            structure_id=structures["ccas-boulogne-demo"].id,
            role="admin",
        ),
    }
    for seed in _request_seeds():
        if seed.requester_username not in user_lookup:
            user_lookup[seed.requester_username] = _get_or_create_user(
                username=seed.requester_username,
                email=f"{seed.requester_username}@helpchain.demo",
                structure_id=structures[seed.structure_slug].id,
                role="requester",
            )
    db.session.flush()

    intervenants_data = [
        ("Claire Martin", "claire.martin.demo@careresociale.demo", "+33 6 11 20 30 41", "social_worker", "15 Rue de Billancourt", "ccas-boulogne-demo"),
        ("Julien Moreau", "julien.moreau.demo@coordination.demo", "+33 6 11 20 30 42", "social_worker", "12 Rue Nationale", "ccas-boulogne-demo"),
        ("Sophie Bernard", "sophie.bernard.demo@solidarite92.demo", "+33 6 11 20 30 43", "nurse", "26 Avenue Victor Hugo", "reseau-sante-boulogne-demo"),
        ("Nathalie Dupont", "nathalie.dupont.demo@solidarite92.demo", "+33 6 11 20 30 44", "psychologist", "3 Rue Anna Jacquin", "cellule-coordination-senior-demo-boulogne"),
        ("Antoine Lefèvre", "antoine.lefevre.demo@justice.demo", "+33 6 11 20 30 45", "lawyer", "48 Rue de Paris", "plateforme-protection-familles-92-demo-boulogne"),
        ("Camille Laurent", "camille.laurent.demo@sante.demo", "+33 6 11 20 30 46", "doctor", "22 Rue de la Saussière", "reseau-sante-boulogne-demo"),
        ("Romain Petit", "romain.petit.demo@solidarite92.demo", "+33 6 11 20 30 47", "social_worker", "9 Rue Paul Bert", "association-solidarite-92-demo-boulogne"),
        ("Élodie Garnier", "elodie.garnier.demo@coordination.demo", "+33 6 11 20 30 48", "nurse", "81 Boulevard de la République", "reseau-sante-boulogne-demo"),
        ("Dr Sarah Cohen", "dr.sarah.cohen.demo@medical.demo", "+33 6 11 20 30 49", "doctor", "19 Rue de Bellevue", "reseau-sante-boulogne-demo"),
        ("Inès Roche", "ines.roche.demo@protection.demo", "+33 6 11 20 30 50", "psychologist", "2 Rue des Menus", "plateforme-protection-familles-92-demo-boulogne"),
        ("Thomas Mercier", "thomas.mercier.demo@ccas.demo", "+33 6 11 20 30 51", "social_worker", "67 Rue Thiers", "ccas-boulogne-demo"),
        ("Julie Perrin", "julie.perrin.demo@coordination.demo", "+33 6 11 20 30 52", "nurse", "21 Rue de Meudon", "cellule-coordination-senior-demo-boulogne"),
        ("Karim Bensaïd", "karim.bensaid.demo@sante.demo", "+33 6 11 20 30 53", "doctor", "5 Rue des 4 Cheminées", "reseau-sante-boulogne-demo"),
        ("Mélanie Faure", "melanie.faure.demo@familles.demo", "+33 6 11 20 30 54", "lawyer", "28 Rue de Clamart", "plateforme-protection-familles-92-demo-boulogne"),
    ]
    for full_name, email, phone, profession, address, structure_slug in intervenants_data:
        _get_or_create_intervenant(
            structure_id=structures[structure_slug].id,
            full_name=f"{DEMO_MARKER} – {full_name}",
            email=email,
            phone=phone,
            profession=profession,
            address=address,
        )

    lead_specs = [
        ("Claire Martin", "claire.martin.lead@boulogne.demo", "+33 6 21 31 41 51", "assistant social", "CCAS Boulogne-Billancourt - Demo Boulogne", "Disponible sous 24h", "15 Rue de Billancourt"),
        ("Dr Sarah Cohen", "dr.sarah.cohen.demo@boulogne.demo", "+33 6 21 31 41 52", "doctor", "Réseau Santé Boulogne - Demo Boulogne", "Visite prioritaire", "19 Rue de Bellevue"),
        ("Julien Moreau", "julien.moreau.demo@boulogne.demo", "+33 6 21 31 41 53", "social worker", "CCAS Boulogne-Billancourt - Demo Boulogne", "Coordination rapide", "12 Rue Nationale"),
        ("Inès Roche", "ines.roche.demo@boulogne.demo", "+33 6 21 31 41 54", "psychologist", "Plateforme Protection Familles 92 - Demo Boulogne", "Créneau discret", "2 Rue des Menus"),
        ("Antoine Lefèvre", "antoine.lefevre.demo@boulogne.demo", "+33 6 21 31 41 55", "lawyer", "Plateforme Protection Familles 92 - Demo Boulogne", "Sous 48h", "48 Rue de Paris"),
        ("Camille Laurent", "camille.laurent.demo@boulogne.demo", "+33 6 21 31 41 56", "doctor", "Réseau Santé Boulogne - Demo Boulogne", "Cabinet disponible", "22 Rue de la Saussière"),
        ("Sophie Bernard", "sophie.bernard.demo@boulogne.demo", "+33 6 21 31 41 57", "nurse", "Réseau Santé Boulogne - Demo Boulogne", "Passage à domicile", "26 Avenue Victor Hugo"),
    ]
    leads: dict[str, ProfessionalLead] = {}
    for full_name, email, phone, profession, organization, availability, address in lead_specs:
        leads[email] = _get_or_create_professional_lead(
            owner_admin_id=admins["admin"].id,
            full_name=f"{DEMO_MARKER} – {full_name}",
            email=email,
            phone=phone,
            profession=profession,
            organization=organization,
            availability=availability,
            address=address,
        )
    db.session.flush()

    requests_map: dict[str, Request] = {}
    for seed_row in _request_seeds():
        requests_map[seed_row.key] = _upsert_request(
            seed_row,
            structures=structures,
            admins=admins,
            users=user_lookup,
        )
    db.session.flush()

    for seed_row in _request_seeds():
        req = requests_map[seed_row.key]
        activity_plan = [("request_created", f"{DEMO_MARKER} – demande créée", seed_row.created_hours_ago - 1)]
        if seed_row.owner_username:
            activity_plan.append(("owner_assigned", f"{DEMO_MARKER} – responsable assigné", max(seed_row.updated_hours_ago + 4, 1)))
        for idx, hours in enumerate(seed_row.activity_hours_ago, start=1):
            if hours > 72:
                msg = f"{DEMO_MARKER} – relance envoyée"
                action = "followup_sent"
            elif idx % 2 == 0:
                msg = f"{DEMO_MARKER} – suivi coordonné"
                action = "note_added"
            else:
                msg = f"{DEMO_MARKER} – note opérateur"
                action = "triage_scored"
            activity_plan.append((action, msg, hours))
        if seed_row.status in {"done", "cancelled"}:
            activity_plan.append(("request_closed", f"{DEMO_MARKER} – clôture du dossier", seed_row.updated_hours_ago))
        for action, text, hours in activity_plan:
            _upsert_request_activity(
                req.id,
                actor_admin_id=admins["admin"].id if req.owner_id else None,
                action=action,
                text=text,
                created_at=NOW - timedelta(hours=hours),
            )

    cases_map: dict[str, Case] = {}
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
        ("email", "request_sla_owner_reminder", "ops.boulogne.demo@helpchain.demo", f"{DEMO_MARKER} – relance responsable logement", "pending", 0, 5, 2, None, structures["association-solidarite-92-demo-boulogne"].id),
        ("email", "request_sla_inactivity_reminder", "admin.demo.boulogne@helpchain.demo", f"{DEMO_MARKER} – suivi inactif senior", "retry", 2, 5, 4, 1, structures["cellule-coordination-senior-demo-boulogne"].id),
        ("sms", "request_sla_inactivity_escalation", "+33611203041", f"{DEMO_MARKER} – escalation hebergement", "dead_letter", 5, 5, 10, 3, structures["association-solidarite-92-demo-boulogne"].id),
        ("email", "case_assignment_digest", "coordination@boulogne.demo", f"{DEMO_MARKER} – digest coordination santé", "done", 1, 5, 8, None, structures["reseau-sante-boulogne-demo"].id),
        ("email", "owner_alert", "pilotage@boulogne.demo", f"{DEMO_MARKER} – alerte sans responsable", "pending", 1, 5, 1, 2, structures["ccas-boulogne-demo"].id),
        ("email", "closure_notice", "direction@solidarite92.demo", f"{DEMO_MARKER} – clôture orientation sociale", "sent", 1, 5, 12, None, structures["ccas-boulogne-demo"].id),
    ]
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
        )

    db.session.commit()

    return {
        "AdminUser": db.session.query(AdminUser).count(),
        "Structure": db.session.query(Structure).count(),
        "Intervenant": db.session.query(Intervenant).count(),
        "ProfessionalLead": db.session.query(ProfessionalLead).count(),
        "Request": db.session.query(Request).count(),
        "Case": db.session.query(Case).count(),
        "RequestActivity": db.session.query(RequestActivity).count(),
        "CaseEvent": db.session.query(CaseEvent).count(),
        "NotificationJob": db.session.query(NotificationJob).count(),
    }


def main() -> int:
    with app.app_context():
        try:
            counts = seed()
        except Exception as exc:
            print(f"SEED_DEMO_BOULOGNE_ERROR: {exc}")
            return 1
        print(json.dumps({"marker": DEMO_MARKER, "counts": counts}, ensure_ascii=False, indent=2))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
