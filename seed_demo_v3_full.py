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
    Request,
    Structure,
    Intervenant,
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


def has_field(model, name):
    return name in cols(model)


def set_if(obj, field_names, value):
    for name in field_names:
        if hasattr(obj, name):
            setattr(obj, name, value)
            return name
    return None


with app.app_context():
    now = datetime.now(UTC)

    admin = AdminUser.query.order_by(AdminUser.id.asc()).first()
    if not admin:
        raise RuntimeError("No AdminUser found.")

    all_requests = Request.query.order_by(Request.id.asc()).all()
    all_pros = ProfessionalLead.query.order_by(ProfessionalLead.id.asc()).all()
    all_structures = Structure.query.order_by(Structure.id.asc()).all()

    if not all_requests:
        raise RuntimeError("No Request rows found.")
    if not all_pros:
        raise RuntimeError("No ProfessionalLead rows found.")
    if len(all_structures) < 2:
        raise RuntimeError("Not enough structures found. Run structures/pros seed first.")

    request_cols = cols(Request)
    case_cols = cols(Case)
    cp_cols = cols(CaseParticipant)
    ce_cols = cols(CaseEvent)
    pro_cols = cols(ProfessionalLead)
    int_cols = cols(Intervenant)
    structure_cols = cols(Structure)

    # -------- Request field detection --------
    req_id_field = "id"
    req_title_field = first_field(Request, ["title", "name", "subject"])
    req_desc_field = first_field(Request, ["description", "details", "body", "message"])
    req_city_field = first_field(Request, ["city", "territory", "location"])
    req_category_field = first_field(Request, ["category", "service_category", "topic"])
    req_status_field = first_field(Request, ["status"])
    req_structure_field = first_field(Request, ["structure_id"])

    # -------- Case field detection --------
    case_request_field = first_field(Case, ["request_id", "source_request_id"])
    case_title_field = first_field(Case, ["title", "name"])
    case_desc_field = first_field(Case, ["description", "details", "summary"])
    case_city_field = first_field(Case, ["city", "territory", "location"])
    case_category_field = first_field(Case, ["category", "service_category"])
    case_status_field = first_field(Case, ["status"])
    case_priority_field = first_field(Case, ["priority"])
    case_opened_at_field = first_field(Case, ["opened_at", "created_at"])
    case_updated_at_field = first_field(Case, ["updated_at", "last_activity_at", "last_updated_at"])
    case_owner_field = first_field(Case, ["owner_admin_id", "assigned_admin_id", "admin_user_id"])
    case_structure_field = first_field(Case, ["structure_id"])
    case_professional_field = first_field(Case, ["professional_lead_id", "primary_professional_lead_id"])
    case_risk_score_field = first_field(Case, ["risk_score", "score", "social_risk_score"])

    # -------- CaseParticipant fields --------
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

    # -------- CaseEvent fields --------
    event_case_id_field = first_field(CaseEvent, ["case_id"])
    event_type_field = first_field(CaseEvent, ["event_type", "type"])
    event_message_field = first_field(CaseEvent, ["message", "body", "description", "note"])
    event_visibility_field = first_field(CaseEvent, ["visibility"])
    event_metadata_field = first_field(CaseEvent, ["metadata_json", "metadata"])
    event_created_by_field = first_field(CaseEvent, ["created_by_admin_id", "admin_user_id", "actor_admin_id"])
    event_created_at_field = first_field(CaseEvent, ["created_at", "occurred_at"])
    event_updated_at_field = first_field(CaseEvent, ["updated_at"])

    # -------- ProfessionalLead fields --------
    pro_city_field = first_field(ProfessionalLead, ["city", "territory", "location"])
    pro_profession_field = first_field(ProfessionalLead, ["profession", "specialty", "speciality", "role", "title"])
    pro_name_field = first_field(ProfessionalLead, ["full_name", "name"])
    pro_email_field = first_field(ProfessionalLead, ["email"])
    pro_phone_field = first_field(ProfessionalLead, ["phone", "mobile"])
    pro_org_field = first_field(ProfessionalLead, ["organization", "organisation", "company"])
    pro_address_field = first_field(ProfessionalLead, ["address", "street_address"])
    pro_structure_field = first_field(ProfessionalLead, ["structure_id"])

    # -------- Intervenant fields --------
    int_name_field = first_field(Intervenant, ["full_name", "name"])
    int_email_field = first_field(Intervenant, ["email"])
    int_phone_field = first_field(Intervenant, ["phone", "mobile"])
    int_profession_field = first_field(Intervenant, ["profession", "specialty", "speciality", "role", "title"])
    int_city_field = first_field(Intervenant, ["city", "territory", "location"])
    int_address_field = first_field(Intervenant, ["address", "street_address"])
    int_lat_field = first_field(Intervenant, ["lat", "latitude"])
    int_lng_field = first_field(Intervenant, ["lng", "lon", "longitude"])
    int_status_field = first_field(Intervenant, ["status"])
    int_availability_field = first_field(Intervenant, ["availability", "availability_status"])
    int_structure_field = first_field(Intervenant, ["structure_id"])
    int_active_field = first_field(Intervenant, ["is_active"])
    int_created_at_field = first_field(Intervenant, ["created_at"])
    int_updated_at_field = first_field(Intervenant, ["updated_at"])

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

    city_geo = {
        "Boulogne-Billancourt": (48.8397, 2.2399),
        "Paris": (48.8566, 2.3522),
        "Issy-les-Moulineaux": (48.8245, 2.2742),
        "Meudon": (48.8139, 2.2350),
        "Saint-Cloud": (48.8459, 2.2028),
        "Suresnes": (48.8714, 2.2293),
    }

    intervenant_seed = [
        {
            "name": "Marie Dubois",
            "email": "marie.dubois@demo.fr",
            "phone": "0601000001",
            "profession": "Assistante sociale",
            "city": "Boulogne-Billancourt",
            "address": "12 Rue de Billancourt, 92100 Boulogne-Billancourt",
            "status": "active",
            "availability": "Disponible",
            "structure_slug": "ccas-boulogne",
        },
        {
            "name": "Jean Martin",
            "email": "jean.martin@demo.fr",
            "phone": "0601000002",
            "profession": "Psychologue",
            "city": "Boulogne-Billancourt",
            "address": "8 Avenue Andre Morizet, 92100 Boulogne-Billancourt",
            "status": "active",
            "availability": "Disponible",
            "structure_slug": "association-solidarite-92",
        },
        {
            "name": "Claire Bernard",
            "email": "claire.bernard@demo.fr",
            "phone": "0601000003",
            "profession": "Juriste social",
            "city": "Paris",
            "address": "15 Rue de Vaugirard, 75015 Paris",
            "status": "active",
            "availability": "Disponible",
            "structure_slug": "protection-familles-92",
        },
        {
            "name": "Thomas Leroy",
            "email": "thomas.leroy@demo.fr",
            "phone": "0601000004",
            "profession": "Insertion emploi",
            "city": "Boulogne-Billancourt",
            "address": "22 Route de la Reine, 92100 Boulogne-Billancourt",
            "status": "active",
            "availability": "Disponible",
            "structure_slug": "reseau-sante-boulogne",
        },
        {
            "name": "Sophie Petit",
            "email": "sophie.petit@demo.fr",
            "phone": "0601000005",
            "profession": "Logement urgence",
            "city": "Issy-les-Moulineaux",
            "address": "5 Rue du General Leclerc, 92130 Issy-les-Moulineaux",
            "status": "active",
            "availability": "Disponible",
            "structure_slug": "association-solidarite-92",
        },
        {
            "name": "Camille Laurent",
            "email": "camille.laurent@demo.fr",
            "phone": "0601000006",
            "profession": "Infirmiere coordinatrice",
            "city": "Boulogne-Billancourt",
            "address": "30 Boulevard Jean Jaures, 92100 Boulogne-Billancourt",
            "status": "active",
            "availability": "Disponible",
            "structure_slug": "coordination-senior",
        },
    ]

    structure_by_slug = {}
    if "slug" in structure_cols:
        structure_by_slug = {s.slug: s for s in all_structures}

    created_intervenants = 0
    created_cases = 0
    updated_cases = 0
    added_participants = 0
    added_events = 0

    # ------------------------------------------------------------------
    # STEP 1: create intervenants for map / territorial pilotage
    # ------------------------------------------------------------------
    for row in intervenant_seed:
        existing = None
        if int_email_field:
            existing = Intervenant.query.filter(
                getattr(Intervenant, int_email_field) == row["email"]
            ).first()

        if existing:
            continue

        obj = Intervenant()

        if int_name_field:
            setattr(obj, int_name_field, row["name"])
        if int_email_field:
            setattr(obj, int_email_field, row["email"])
        if int_phone_field:
            setattr(obj, int_phone_field, row["phone"])
        if int_profession_field:
            setattr(obj, int_profession_field, row["profession"])
        if int_city_field:
            setattr(obj, int_city_field, row["city"])
        if int_address_field:
            setattr(obj, int_address_field, row["address"])
        if int_status_field:
            setattr(obj, int_status_field, row["status"])
        if int_availability_field:
            setattr(obj, int_availability_field, row["availability"])
        if int_active_field:
            setattr(obj, int_active_field, True)
        if int_created_at_field:
            setattr(obj, int_created_at_field, now)
        if int_updated_at_field:
            setattr(obj, int_updated_at_field, now)

        lat, lng = city_geo.get(row["city"], (48.8566, 2.3522))
        if int_lat_field:
            setattr(obj, int_lat_field, lat)
        if int_lng_field:
            setattr(obj, int_lng_field, lng)

        if int_structure_field and row["structure_slug"] in structure_by_slug:
            setattr(obj, int_structure_field, structure_by_slug[row["structure_slug"]].id)

        db.session.add(obj)
        created_intervenants += 1

    db.session.commit()

    # ------------------------------------------------------------------
    # STEP 2: create missing cases for all requests
    # ------------------------------------------------------------------
    existing_case_by_request_id = {}
    if case_request_field:
        for c in Case.query.all():
            existing_case_by_request_id[getattr(c, case_request_field, None)] = c

    def pick_professional_for_request(req_obj, fallback_index):
        req_city = getattr(req_obj, req_city_field, None) if req_city_field else None

        text_blob = " ".join(
            str(getattr(req_obj, field, "") or "")
            for field in [req_title_field, req_desc_field, req_category_field]
            if field
        ).lower()

        if "logement" in text_blob:
            preferred = "Logement urgence"
        elif "sante" in text_blob:
            preferred = "Sante mentale"
        elif "jur" in text_blob:
            preferred = "Juriste social"
        elif "emploi" in text_blob or "insertion" in text_blob:
            preferred = "Insertion emploi"
        elif "senior" in text_blob:
            preferred = "Referent senior"
        elif "fam" in text_blob:
            preferred = "Mediateur familial"
        else:
            preferred = professions_priority[fallback_index % len(professions_priority)]

        same_city = []
        if req_city and pro_city_field:
            same_city = [p for p in all_pros if getattr(p, pro_city_field, None) == req_city]

        pool = same_city if same_city else all_pros

        if pro_profession_field:
            exact = [p for p in pool if getattr(p, pro_profession_field, None) == preferred]
            if exact:
                return exact[0]

        return pool[fallback_index % len(pool)]

    for idx, req in enumerate(all_requests):
        req_id = getattr(req, req_id_field)

        case_obj = existing_case_by_request_id.get(req_id)
        created_now = False

        if case_obj is None:
            case_obj = Case()

            if case_request_field:
                setattr(case_obj, case_request_field, req_id)

            if case_title_field:
                req_title = getattr(req, req_title_field, None) if req_title_field else None
                setattr(case_obj, case_title_field, req_title or f"Case for request #{req_id}")

            if case_desc_field and req_desc_field:
                setattr(case_obj, case_desc_field, getattr(req, req_desc_field, None))

            if case_city_field and req_city_field:
                setattr(case_obj, case_city_field, getattr(req, req_city_field, None))

            if case_category_field and req_category_field:
                setattr(case_obj, case_category_field, getattr(req, req_category_field, None))

            if case_status_field:
                setattr(case_obj, case_status_field, "assigned")

            if case_priority_field:
                setattr(case_obj, case_priority_field, "normal")

            if case_owner_field:
                setattr(case_obj, case_owner_field, admin.id)

            if case_structure_field and req_structure_field:
                setattr(case_obj, case_structure_field, getattr(req, req_structure_field, None))

            if case_risk_score_field:
                setattr(case_obj, case_risk_score_field, 10)

            if case_opened_at_field:
                setattr(case_obj, case_opened_at_field, now - timedelta(minutes=idx + 10))
            if case_updated_at_field:
                setattr(case_obj, case_updated_at_field, now - timedelta(minutes=idx + 1))

            db.session.add(case_obj)
            db.session.flush()

            existing_case_by_request_id[req_id] = case_obj
            created_cases += 1
            created_now = True

        pro = pick_professional_for_request(req, idx)

        if case_professional_field and getattr(case_obj, case_professional_field, None) in (None, 0, ""):
            setattr(case_obj, case_professional_field, pro.id)

        if case_owner_field:
            setattr(case_obj, case_owner_field, admin.id)

        if case_status_field:
            status_value = str(getattr(case_obj, case_status_field, "") or "").strip().lower()
            if status_value in {"", "new", "open"}:
                setattr(case_obj, case_status_field, "assigned")

        if case_updated_at_field:
            setattr(case_obj, case_updated_at_field, now - timedelta(minutes=idx + 1))

        updated_cases += 1

        existing_participant = None
        if participant_case_id_field and participant_professional_id_field:
            existing_participant = (
                CaseParticipant.query.filter(
                    getattr(CaseParticipant, participant_case_id_field) == case_obj.id,
                    getattr(CaseParticipant, participant_professional_id_field) == pro.id,
                ).first()
            )

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
            if participant_name_field and pro_name_field:
                setattr(cp, participant_name_field, getattr(pro, pro_name_field, None))
            if participant_added_by_field:
                setattr(cp, participant_added_by_field, admin.id)
            if participant_created_at_field:
                setattr(cp, participant_created_at_field, now - timedelta(minutes=(idx + 1) * 3))
            if participant_updated_at_field:
                setattr(cp, participant_updated_at_field, now - timedelta(minutes=(idx + 1) * 2))

            db.session.add(cp)
            added_participants += 1

        # Event: case created if new
        if created_now:
            ev_create = CaseEvent()
            if event_case_id_field:
                setattr(ev_create, event_case_id_field, case_obj.id)
            if event_type_field:
                setattr(ev_create, event_type_field, "case_created")
            if event_message_field:
                setattr(ev_create, event_message_field, f"Case created from request #{req_id}")
            if event_visibility_field:
                setattr(ev_create, event_visibility_field, "interne")
            if event_metadata_field:
                setattr(ev_create, event_metadata_field, '{"seed":"demo_v3","kind":"case_created"}')
            if event_created_by_field:
                setattr(ev_create, event_created_by_field, admin.id)
            if event_created_at_field:
                setattr(ev_create, event_created_at_field, now - timedelta(minutes=(idx + 1) * 3))
            if event_updated_at_field:
                setattr(ev_create, event_updated_at_field, now - timedelta(minutes=(idx + 1) * 3))
            db.session.add(ev_create)
            added_events += 1

        # Event: participant added
        ev_participant = CaseEvent()
        if event_case_id_field:
            setattr(ev_participant, event_case_id_field, case_obj.id)
        if event_type_field:
            setattr(ev_participant, event_type_field, "participant_added")
        if event_message_field:
            pro_name = getattr(pro, pro_name_field, None) if pro_name_field else f"Professional #{pro.id}"
            pro_prof = getattr(pro, pro_profession_field, None) if pro_profession_field else ""
            msg = f"Professional linked to case: {pro_name}"
            if pro_prof:
                msg += f" ({pro_prof})"
            setattr(ev_participant, event_message_field, msg)
        if event_visibility_field:
            setattr(ev_participant, event_visibility_field, "interne")
        if event_metadata_field:
            setattr(ev_participant, event_metadata_field, '{"seed":"demo_v3","kind":"participant_added"}')
        if event_created_by_field:
            setattr(ev_participant, event_created_by_field, admin.id)
        if event_created_at_field:
            setattr(ev_participant, event_created_at_field, now - timedelta(minutes=(idx + 1) * 2))
        if event_updated_at_field:
            setattr(ev_participant, event_updated_at_field, now - timedelta(minutes=(idx + 1) * 2))
        db.session.add(ev_participant)
        added_events += 1

        # Event: internal note
        ev_note = CaseEvent()
        if event_case_id_field:
            setattr(ev_note, event_case_id_field, case_obj.id)
        if event_type_field:
            setattr(ev_note, event_type_field, "note_added")
        if event_message_field:
            pro_name = getattr(pro, pro_name_field, None) if pro_name_field else f"Professional #{pro.id}"
            pro_prof = getattr(pro, pro_profession_field, None) if pro_profession_field else ""
            pro_city = getattr(pro, pro_city_field, None) if pro_city_field else ""
            msg = f"Suggested routing to {pro_name}"
            if pro_prof:
                msg += f", {pro_prof}"
            if pro_city:
                msg += f", {pro_city}"
            msg += ". Initial contact prepared for operational follow-up."
            setattr(ev_note, event_message_field, msg)
        if event_visibility_field:
            setattr(ev_note, event_visibility_field, "interne")
        if event_metadata_field:
            setattr(ev_note, event_metadata_field, '{"seed":"demo_v3","kind":"internal_note"}')
        if event_created_by_field:
            setattr(ev_note, event_created_by_field, admin.id)
        if event_created_at_field:
            setattr(ev_note, event_created_at_field, now - timedelta(minutes=(idx + 1)))
        if event_updated_at_field:
            setattr(ev_note, event_updated_at_field, now - timedelta(minutes=(idx + 1)))
        db.session.add(ev_note)
        added_events += 1

    db.session.commit()

    print("Created intervenants:", created_intervenants)
    print("Created missing cases:", created_cases)
    print("Updated cases:", updated_cases)
    print("Participants added:", added_participants)
    print("Events added:", added_events)
    print("Total requests:", Request.query.count())
    print("Total cases:", Case.query.count())
    print("Total case participants:", CaseParticipant.query.count())
    print("Total case events:", CaseEvent.query.count())
    print("Total intervenants:", Intervenant.query.count())
