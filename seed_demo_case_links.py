# -*- coding: utf-8 -*-
from datetime import UTC, datetime, timedelta

from backend.helpchain_backend.src.app import create_app
from backend.extensions import db
from backend.helpchain_backend.src.models import (
    AdminUser,
    Case,
    CaseEvent,
    CaseParticipant,
    ProfessionalLead,
)

app = create_app()


def cols(model):
    return set(model.__table__.columns.keys())


def first_field(model, names):
    c = cols(model)
    for n in names:
        if n in c:
            return n
    return None


with app.app_context():
    now = datetime.now(UTC)

    admin = AdminUser.query.order_by(AdminUser.id.asc()).first()
    if not admin:
        raise RuntimeError("No AdminUser found.")

    all_cases = Case.query.order_by(Case.id.asc()).all()
    all_pros = ProfessionalLead.query.order_by(ProfessionalLead.id.asc()).all()

    if not all_cases:
        raise RuntimeError("No Case rows found.")
    if not all_pros:
        raise RuntimeError("No ProfessionalLead rows found.")

    pro_city_field = first_field(ProfessionalLead, ["city", "territory", "location"])
    pro_profession_field = first_field(ProfessionalLead, ["profession", "specialty", "speciality", "role", "title"])

    participant_case_id_field = first_field(CaseParticipant, ["case_id"])
    participant_professional_id_field = first_field(CaseParticipant, ["professional_lead_id"])
    participant_type_field = first_field(CaseParticipant, ["participant_type"])
    participant_status_field = first_field(CaseParticipant, ["status"])
    participant_role_field = first_field(CaseParticipant, ["role"])
    participant_user_id_field = first_field(CaseParticipant, ["user_id"])
    participant_admin_user_id_field = first_field(CaseParticipant, ["admin_user_id"])
    participant_actor_type_field = first_field(CaseParticipant, ["actor_type"])
    participant_name_field = first_field(CaseParticipant, ["external_name", "name", "display_name"])
    participant_added_by_field = first_field(CaseParticipant, ["added_by_admin_id", "created_by_admin_id"])
    participant_created_at_field = first_field(CaseParticipant, ["created_at", "added_at"])
    participant_updated_at_field = first_field(CaseParticipant, ["updated_at"])

    event_case_id_field = first_field(CaseEvent, ["case_id"])
    event_type_field = first_field(CaseEvent, ["event_type", "type"])
    event_message_field = first_field(CaseEvent, ["message", "body", "description", "note"])
    event_visibility_field = first_field(CaseEvent, ["visibility"])
    event_metadata_field = first_field(CaseEvent, ["metadata_json", "metadata"])
    event_created_by_field = first_field(CaseEvent, ["created_by_admin_id", "admin_user_id", "actor_admin_id"])
    event_created_at_field = first_field(CaseEvent, ["created_at", "occurred_at"])
    event_updated_at_field = first_field(CaseEvent, ["updated_at"])

    case_status_field = first_field(Case, ["status"])
    case_owner_field = first_field(Case, ["owner_admin_id", "assigned_admin_id", "admin_user_id"])
    case_updated_at_field = first_field(Case, ["updated_at", "last_activity_at", "last_updated_at"])
    case_professional_field = first_field(Case, ["professional_lead_id", "primary_professional_lead_id"])

    added_participants = 0
    added_events = 0
    updated_cases = 0

    professions_priority = [
        "Assistante sociale",
        "Psychologue",
        "Juriste social",
        "Insertion emploi",
        "Logement urgence",
        "Mediateur familial",
        "Sante mentale",
        "Infirmiere coordinatrice",
        "Referent senior",
        "Medecin partenaire",
    ]

    def pick_professional_for_case(case_obj, fallback_index):
        case_city = None
        for candidate in ["city", "territory", "location"]:
            if hasattr(case_obj, candidate):
                case_city = getattr(case_obj, candidate)
                break

        title_blob = " ".join(
            str(getattr(case_obj, field, "") or "")
            for field in ["title", "name", "description", "category"]
            if hasattr(case_obj, field)
        ).lower()

        if "logement" in title_blob:
            preferred = "Logement urgence"
        elif "sante" in title_blob:
            preferred = "Sante mentale"
        elif "jur" in title_blob:
            preferred = "Juriste social"
        elif "emploi" in title_blob or "insertion" in title_blob:
            preferred = "Insertion emploi"
        elif "senior" in title_blob:
            preferred = "Referent senior"
        elif "fam" in title_blob:
            preferred = "Mediateur familial"
        else:
            preferred = professions_priority[fallback_index % len(professions_priority)]

        same_city = []
        if case_city and pro_city_field:
            same_city = [p for p in all_pros if getattr(p, pro_city_field, None) == case_city]

        candidate_pool = same_city if same_city else all_pros

        if pro_profession_field:
            exact = [p for p in candidate_pool if getattr(p, pro_profession_field, None) == preferred]
            if exact:
                return exact[0]

        return candidate_pool[fallback_index % len(candidate_pool)]

    with db.session.no_autoflush:
        for idx, case_obj in enumerate(all_cases):
            pro = pick_professional_for_case(case_obj, idx)

            existing_participant = None
            if participant_case_id_field and participant_professional_id_field:
                existing_participant = (
                    CaseParticipant.query.filter(
                        getattr(CaseParticipant, participant_case_id_field) == case_obj.id,
                        getattr(CaseParticipant, participant_professional_id_field) == pro.id,
                    ).first()
                )

            participant_created = False
            if existing_participant is None:
                cp = CaseParticipant()

                if participant_case_id_field:
                    setattr(cp, participant_case_id_field, case_obj.id)
                if participant_professional_id_field:
                    setattr(cp, participant_professional_id_field, pro.id)
                if participant_type_field:
                    setattr(cp, participant_type_field, "professional_lead")
                if participant_status_field:
                    setattr(cp, participant_status_field, "active")
                if participant_role_field:
                    setattr(cp, participant_role_field, "professional_lead")
                if participant_user_id_field:
                    setattr(cp, participant_user_id_field, None)
                if participant_admin_user_id_field:
                    setattr(cp, participant_admin_user_id_field, admin.id)
                if participant_actor_type_field:
                    setattr(cp, participant_actor_type_field, "professional_lead")
                if participant_name_field and hasattr(pro, "full_name"):
                    setattr(cp, participant_name_field, getattr(pro, "full_name"))
                if participant_added_by_field:
                    setattr(cp, participant_added_by_field, admin.id)
                if participant_created_at_field:
                    setattr(cp, participant_created_at_field, now - timedelta(minutes=(idx + 1) * 3))
                if participant_updated_at_field:
                    setattr(cp, participant_updated_at_field, now - timedelta(minutes=(idx + 1) * 2))

                db.session.add(cp)
                added_participants += 1
                participant_created = True

            if case_professional_field:
                setattr(case_obj, case_professional_field, pro.id)

            if case_owner_field:
                setattr(case_obj, case_owner_field, admin.id)

            if case_status_field:
                current_status = str(getattr(case_obj, case_status_field, "") or "").strip().lower()
                if current_status in {"new", "open", ""}:
                    setattr(case_obj, case_status_field, "assigned")

            if case_updated_at_field:
                setattr(case_obj, case_updated_at_field, now - timedelta(minutes=idx + 1))

            updated_cases += 1

            if participant_created:
                ev1 = CaseEvent()
                if event_case_id_field:
                    setattr(ev1, event_case_id_field, case_obj.id)
                if event_type_field:
                    setattr(ev1, event_type_field, "participant_added")
                if event_message_field:
                    full_name = getattr(pro, "full_name", f"Professional #{pro.id}")
                    profession = getattr(pro, pro_profession_field, "") if pro_profession_field else ""
                    msg = f"Professionnel ajoute au dossier: {full_name}"
                    if profession:
                        msg += f" ({profession})"
                    setattr(ev1, event_message_field, msg)
                if event_visibility_field:
                    setattr(ev1, event_visibility_field, "interne")
                if event_metadata_field:
                    setattr(ev1, event_metadata_field, '{"seed":"demo_v2","kind":"participant_added"}')
                if event_created_by_field:
                    setattr(ev1, event_created_by_field, admin.id)
                if event_created_at_field:
                    setattr(ev1, event_created_at_field, now - timedelta(minutes=(idx + 1) * 2))
                if event_updated_at_field:
                    setattr(ev1, event_updated_at_field, now - timedelta(minutes=(idx + 1) * 2))

                db.session.add(ev1)
                added_events += 1

            ev2 = CaseEvent()
            if event_case_id_field:
                setattr(ev2, event_case_id_field, case_obj.id)
            if event_type_field:
                setattr(ev2, event_type_field, "note_added")
            if event_message_field:
                full_name = getattr(pro, "full_name", f"Professional #{pro.id}")
                profession = getattr(pro, pro_profession_field, "") if pro_profession_field else ""
                city = getattr(pro, pro_city_field, "") if pro_city_field else ""
                note = (
                    f"Orientation proposee vers {full_name}"
                    + (f", {profession}" if profession else "")
                    + (f", {city}" if city else "")
                    + ". Contact initie pour la prise en charge."
                )
                setattr(ev2, event_message_field, note)
            if event_visibility_field:
                setattr(ev2, event_visibility_field, "interne")
            if event_metadata_field:
                setattr(ev2, event_metadata_field, '{"seed":"demo_v2","kind":"internal_note"}')
            if event_created_by_field:
                setattr(ev2, event_created_by_field, admin.id)
            if event_created_at_field:
                setattr(ev2, event_created_at_field, now - timedelta(minutes=(idx + 1)))
            if event_updated_at_field:
                setattr(ev2, event_updated_at_field, now - timedelta(minutes=(idx + 1)))

            db.session.add(ev2)
            added_events += 1

    db.session.commit()

    print("Cases updated:", updated_cases)
    print("Participants added:", added_participants)
    print("Events added:", added_events)
    print("Total cases:", Case.query.count())
    print("Total case participants:", CaseParticipant.query.count())
    print("Total case events:", CaseEvent.query.count())
