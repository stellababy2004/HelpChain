# -*- coding: utf-8 -*-
from backend.helpchain_backend.src.app import create_app
from backend.extensions import db
from backend.helpchain_backend.src.models import ProfessionalLead, Request, Structure

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
    created_structures = []
    created_pros = 0

    structure_name_field = first_field(Structure, ["name", "title", "label"])
    structure_slug_field = first_field(Structure, ["slug", "code", "identifier"])
    structure_active_field = first_field(Structure, ["is_active", "active"])

    structures_data = [
        {"name": "CCAS Boulogne-Billancourt", "slug": "ccas-boulogne"},
        {"name": "Association Solidarite 92", "slug": "association-solidarite-92"},
        {"name": "Reseau Sante Boulogne", "slug": "reseau-sante-boulogne"},
        {"name": "Cellule Coordination Senior", "slug": "coordination-senior"},
        {"name": "Protection Familles 92", "slug": "protection-familles-92"},
    ]

    structure_map = {}

    for row in structures_data:
        existing = None

        if structure_slug_field:
            existing = Structure.query.filter(
                getattr(Structure, structure_slug_field) == row["slug"]
            ).first()

        if existing is None and structure_name_field:
            existing = Structure.query.filter(
                getattr(Structure, structure_name_field) == row["name"]
            ).first()

        if existing is None:
            s = Structure()
            if structure_name_field:
                setattr(s, structure_name_field, row["name"])
            if structure_slug_field:
                setattr(s, structure_slug_field, row["slug"])
            if structure_active_field:
                setattr(s, structure_active_field, True)

            db.session.add(s)
            db.session.flush()
            existing = s
            created_structures.append(row["name"])

        structure_map[row["slug"]] = existing

    pro_cols = cols(ProfessionalLead)

    pro_name_field = first_field(ProfessionalLead, ["full_name", "name", "display_name"])
    pro_email_field = first_field(ProfessionalLead, ["email"])
    pro_profession_field = first_field(ProfessionalLead, ["profession", "specialty", "speciality", "role", "title"])
    pro_city_field = first_field(ProfessionalLead, ["city", "territory", "location"])
    pro_org_field = first_field(ProfessionalLead, ["organization", "organization_name", "organisation_name", "structure_name", "company"])
    pro_structure_id_field = first_field(ProfessionalLead, ["structure_id"])
    pro_active_field = first_field(ProfessionalLead, ["is_active", "active"])
    pro_source_field = first_field(ProfessionalLead, ["source"])

    pros_data = [
        {"full_name": "Marie Dubois", "email": "marie.dubois@demo.fr", "profession": "Assistante sociale", "city": "Boulogne-Billancourt", "org": "CCAS Boulogne-Billancourt", "structure_slug": "ccas-boulogne"},
        {"full_name": "Jean Martin", "email": "jean.martin@demo.fr", "profession": "Psychologue", "city": "Boulogne-Billancourt", "org": "Cellule Coordination Senior", "structure_slug": "coordination-senior"},
        {"full_name": "Claire Bernard", "email": "claire.bernard@demo.fr", "profession": "Juriste social", "city": "Boulogne-Billancourt", "org": "Protection Familles 92", "structure_slug": "protection-familles-92"},
        {"full_name": "Thomas Leroy", "email": "thomas.leroy@demo.fr", "profession": "Insertion emploi", "city": "Boulogne-Billancourt", "org": "Association Solidarite 92", "structure_slug": "association-solidarite-92"},
        {"full_name": "Sophie Petit", "email": "sophie.petit@demo.fr", "profession": "Logement urgence", "city": "Boulogne-Billancourt", "org": "Association Solidarite 92", "structure_slug": "association-solidarite-92"},
        {"full_name": "Nicolas Moreau", "email": "nicolas.moreau@demo.fr", "profession": "Mediateur familial", "city": "Paris", "org": "Protection Familles 92", "structure_slug": "protection-familles-92"},
        {"full_name": "Julie Simon", "email": "julie.simon@demo.fr", "profession": "Sante mentale", "city": "Paris", "org": "Reseau Sante Boulogne", "structure_slug": "reseau-sante-boulogne"},
        {"full_name": "Camille Laurent", "email": "camille.laurent@demo.fr", "profession": "Infirmiere coordinatrice", "city": "Boulogne-Billancourt", "org": "Reseau Sante Boulogne", "structure_slug": "reseau-sante-boulogne"},
        {"full_name": "Antoine Mercier", "email": "antoine.mercier@demo.fr", "profession": "Referent senior", "city": "Boulogne-Billancourt", "org": "Cellule Coordination Senior", "structure_slug": "coordination-senior"},
        {"full_name": "Sarah Cohen", "email": "sarah.cohen@demo.fr", "profession": "Medecin partenaire", "city": "Boulogne-Billancourt", "org": "Reseau Sante Boulogne", "structure_slug": "reseau-sante-boulogne"},
    ]

    for row in pros_data:
        existing = None
        if pro_email_field:
            existing = ProfessionalLead.query.filter(
                getattr(ProfessionalLead, pro_email_field) == row["email"]
            ).first()

        if existing is None:
            p = ProfessionalLead()

            if pro_name_field:
                setattr(p, pro_name_field, row["full_name"])
            if pro_email_field:
                setattr(p, pro_email_field, row["email"])
            if pro_profession_field:
                setattr(p, pro_profession_field, row["profession"])
            if pro_city_field:
                setattr(p, pro_city_field, row["city"])
            if pro_org_field:
                setattr(p, pro_org_field, row["org"])
            if pro_active_field:
                setattr(p, pro_active_field, True)
            if pro_source_field:
                setattr(p, pro_source_field, "demo_seed")

            linked_structure = structure_map.get(row["structure_slug"])
            if linked_structure is not None and pro_structure_id_field:
                setattr(p, pro_structure_id_field, linked_structure.id)

            db.session.add(p)
            created_pros += 1

    request_cols = cols(Request)
    if "structure_id" in request_cols:
        targets = [s for s in structure_map.values() if s is not None]
        requests = Request.query.order_by(Request.id.asc()).all()

        if targets:
            for idx, req in enumerate(requests):
                req.structure_id = targets[idx % len(targets)].id

    db.session.commit()

    print("Structures created:", len(created_structures))
    print("Structure names:", created_structures)
    print("Professionals added:", created_pros)
    print("Total professionals:", ProfessionalLead.query.count())
    print("Total structures:", Structure.query.count())
    print("Total requests:", Request.query.count())
