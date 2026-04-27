
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash

from backend.appy import app
from backend.extensions import db
from backend.models import (
    AdminUser,
    Structure,
    Request,
)

ProfessionalLead = None

DEMO_MARKER = "DEMO_PARIS_ELITE_V1"


def set_if_exists(obj, **values):
    for key, value in values.items():
        if hasattr(obj, key):
            setattr(obj, key, value)


def get_or_create_structure():
    structure = Structure.query.filter_by(slug="paris-elite-demo").first()
    if structure:
        return structure

    structure = Structure()
    set_if_exists(
        structure,
        name="CCAS Boulogne-Billancourt ? D?mo",
        slug="paris-elite-demo",
        status="active",
        city="Boulogne-Billancourt",
        country="FR",
        notes=DEMO_MARKER,
    )
    db.session.add(structure)
    db.session.commit()
    return structure


def ensure_admin(structure):
    admin = AdminUser.query.filter_by(username="admin").first()
    if not admin:
        admin = AdminUser()
        db.session.add(admin)

    set_if_exists(
        admin,
        username="admin",
        email="admin@localhost",
        role="superadmin",
        is_active=True,
        structure_id=getattr(structure, "id", None),
        password_hash=generate_password_hash("admin123"),
    )
    db.session.commit()


def seed_requests(structure):
    existing = Request.query.filter(
        Request.title.like("[DEMO] Paris Elite%")
    ).count()

    if existing:
        print(f"Requests already seeded: {existing}")
        return

    rows = [
        ("[DEMO] Paris Elite ? Urgence alimentaire famille monoparentale", "Paris 15", "Alimentaire", "critical", "new"),
        ("[DEMO] Paris Elite ? Relogement temporaire apr?s rupture familiale", "Boulogne-Billancourt", "Logement", "high", "in_progress"),
        ("[DEMO] Paris Elite ? Isolement senior sans suivi r?gulier", "Neuilly-sur-Seine", "Senior", "medium", "assigned"),
        ("[DEMO] Paris Elite ? Aide administrative droits sociaux", "Issy-les-Moulineaux", "Administratif", "medium", "new"),
        ("[DEMO] Paris Elite ? Orientation jeune sans solution d?h?bergement", "Paris 16", "Insertion", "high", "in_progress"),
        ("[DEMO] Paris Elite ? Besoin colis alimentaire urgent", "Levallois-Perret", "Alimentaire", "critical", "new"),
        ("[DEMO] Paris Elite ? Suivi dossier sant? fragile", "Montrouge", "Sant?", "medium", "assigned"),
        ("[DEMO] Paris Elite ? Demande accompagnement mobilit?", "Vanves", "Mobilit?", "low", "done"),
        ("[DEMO] Paris Elite ? Situation familiale ? coordonner", "Boulogne-Billancourt", "Famille", "high", "in_progress"),
        ("[DEMO] Paris Elite ? Personne isol?e sans contact r?cent", "Paris 15", "Isolement", "medium", "new"),
        ("[DEMO] Paris Elite ? Demande urgente orientation sociale", "Issy-les-Moulineaux", "Urgence sociale", "critical", "new"),
        ("[DEMO] Paris Elite ? Suivi de dossier partenaire", "Neuilly-sur-Seine", "Partenaire", "medium", "pending"),
    ]

    now = datetime.now(timezone.utc)

    for i, (title, city, category, priority, status) in enumerate(rows):
        r = Request()
        set_if_exists(
            r,
            title=title,
            description=f"{DEMO_MARKER} ? Situation de d?monstration pour pilotage institutionnel.",
            city=city,
            category=category,
            priority=priority,
            status=status,
            structure_id=getattr(structure, "id", None),
            created_at=now - timedelta(days=i),
            updated_at=now - timedelta(hours=i * 3),
            requester_name=f"Usager Demo {i+1}",
            requester_email=f"demo.usager{i+1}@example.org",
            requester_phone=f"+331000000{i+1:02d}",
        )
        db.session.add(r)

    db.session.commit()
    print("Requests seeded: 12")


def seed_leads():
    if ProfessionalLead is None:
        print('ProfessionalLead model not found ? skipping leads seed')
        return

    existing = ProfessionalLead.query.filter(
        ProfessionalLead.email.like("%demo-paris-elite%")
    ).count()

    if existing:
        print(f"Leads already seeded: {existing}")
        return

    rows = [
        ("CCAS Montrouge", "Responsable action sociale", "montrouge@demo-paris-elite.local", "Montrouge", "hot"),
        ("Mairie de Vanves", "Direction solidarit?", "vanves@demo-paris-elite.local", "Vanves", "qualified"),
        ("Association Jeunesse 92", "Coordinatrice partenariats", "jeunesse92@demo-paris-elite.local", "Nanterre", "new"),
        ("Centre social Levallois", "Directeur", "levallois@demo-paris-elite.local", "Levallois-Perret", "follow_up"),
        ("R?seau Solidarit? Paris Ouest", "Charg?e de mission", "paris-ouest@demo-paris-elite.local", "Paris 16", "demo_pending"),
    ]

    now = datetime.now(timezone.utc)

    for i, (org, profession, email, city, status) in enumerate(rows):
        lead = ProfessionalLead()
        set_if_exists(
            lead,
            organization=org,
            organisation=org,
            name=profession,
            contact_name=profession,
            profession=profession,
            email=email,
            city=city,
            status=status,
            urgency="high" if status in ("hot", "demo_pending") else "medium",
            source="demo_seed",
            notes=f"{DEMO_MARKER} ? Lead institutionnel de d?monstration.",
            created_at=now - timedelta(days=i),
            updated_at=now - timedelta(hours=i * 2),
        )
        db.session.add(lead)

    db.session.commit()
    print("Professional leads seeded: 5")


def main():
    with app.app_context():
        structure = get_or_create_structure()
        ensure_admin(structure)
        seed_requests(structure)
        seed_leads()

        print("")
        print("SEED PARIS ELITE V1 DONE")
        print("Login: admin / admin123")
        print("Structure: paris-elite-demo")


if __name__ == "__main__":
    main()
