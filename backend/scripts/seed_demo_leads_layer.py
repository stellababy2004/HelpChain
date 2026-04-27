
from datetime import datetime, timezone, timedelta
from sqlalchemy import inspect, text

from backend.appy import app
from backend.extensions import db

DEMO_EMAIL_DOMAIN = "demo-paris-elite.local"

LEADS = [
    {
        "email": "ccas.montrouge@demo-paris-elite.local",
        "name": "Responsable action sociale",
        "organization": "CCAS Montrouge",
        "city": "Montrouge",
        "status": "hot",
        "source": "demo",
        "notes": "D?mo Paris Elite ? besoin de centraliser les demandes sociales et le suivi.",
    },
    {
        "email": "solidarite.vanves@demo-paris-elite.local",
        "name": "Direction Solidarit?s",
        "organization": "Mairie de Vanves",
        "city": "Vanves",
        "status": "qualified",
        "source": "demo",
        "notes": "Int?r?t pour un pilote court avec reporting institutionnel.",
    },
    {
        "email": "jeunesse92@demo-paris-elite.local",
        "name": "Coordinatrice partenariats",
        "organization": "Association Jeunesse 92",
        "city": "Nanterre",
        "status": "new",
        "source": "demo",
        "notes": "Lead association ? coordination jeunes et situations urgentes.",
    },
    {
        "email": "centre.social.levallois@demo-paris-elite.local",
        "name": "Directeur",
        "organization": "Centre social Levallois",
        "city": "Levallois-Perret",
        "status": "follow_up",
        "source": "demo",
        "notes": "Relance pr?vue apr?s ?change exploratoire.",
    },
    {
        "email": "paris.ouest@demo-paris-elite.local",
        "name": "Charg?e de mission",
        "organization": "R?seau Solidarit? Paris Ouest",
        "city": "Paris 16",
        "status": "demo_pending",
        "source": "demo",
        "notes": "Opportunit? d?monstration ? coordination inter-structures.",
    },
]


def pick_table(inspector):
    tables = inspector.get_table_names()
    candidates = [
        "professional_leads",
        "leads",
        "contact_leads",
        "organization_access_requests",
        "organisation_access_requests",
    ]

    for name in candidates:
        if name in tables:
            return name

    for name in tables:
        lowered = name.lower()
        if "lead" in lowered or "access_request" in lowered:
            return name

    return None


def compatible_value(column, lead, index):
    name = column["name"]
    now = datetime.now(timezone.utc) - timedelta(hours=index)

    mapping = {
        "email": lead["email"],
        "contact_email": lead["email"],
        "name": lead["name"],
        "contact_name": lead["name"],
        "full_name": lead["name"],
        "organization": lead["organization"],
        "organisation": lead["organization"],
        "organization_name": lead["organization"],
        "organisation_name": lead["organization"],
        "company": lead["organization"],
        "structure_name": lead["organization"],
        "city": lead["city"],
        "ville": lead["city"],
        "status": lead["status"],
        "stage": lead["status"],
        "source": lead["source"],
        "notes": lead["notes"],
        "message": lead["notes"],
        "created_at": now,
        "updated_at": now,
        "submitted_at": now,
        "profession": lead["name"],
        "role": lead["name"],
        "phone": "+33100000000",
        "consent": True,
        "is_demo": True,
    }

    return mapping.get(name)


def seed():
    inspector = inspect(db.engine)
    table = pick_table(inspector)

    if not table:
        print("No lead/access request table found.")
        print("Available tables:")
        print(inspector.get_table_names())
        return

    columns = inspector.get_columns(table)
    column_names = [c["name"] for c in columns]

    print(f"Using table: {table}")
    print(f"Columns: {column_names}")

    if "email" in column_names:
        existing = db.session.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE email LIKE :domain"),
            {"domain": f"%{DEMO_EMAIL_DOMAIN}%"},
        ).scalar()
        if existing:
            print(f"Demo leads already exist: {existing}")
            return

    inserted = 0

    for index, lead in enumerate(LEADS):
        data = {}

        for column in columns:
            name = column["name"]

            if name == "id":
                continue

            value = compatible_value(column, lead, index)

            if value is not None:
                data[name] = value

        if not data:
            continue

        keys = list(data.keys())
        sql = text(
            f"INSERT INTO {table} ({', '.join(keys)}) "
            f"VALUES ({', '.join(':' + k for k in keys)})"
        )

        db.session.execute(sql, data)
        inserted += 1

    db.session.commit()
    print(f"Inserted demo leads: {inserted}")


def main():
    with app.app_context():
        seed()


if __name__ == "__main__":
    main()
