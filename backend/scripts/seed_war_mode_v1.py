
from datetime import datetime, timezone, timedelta
from sqlalchemy import inspect, text

from backend.appy import app
from backend.extensions import db

DOMAIN = "demo-paris-elite.local"

WAR_LEADS = [
    {
        "email": "ccas.montrouge@demo-paris-elite.local",
        "status": "qualified",
        "notes": "WAR MODE ? Priority target. Next action: propose 30-minute pilot demo this week. Estimated pilot value: EUR 600 MRR.",
        "value": 600,
        "score": 82,
    },
    {
        "email": "solidarite.vanves@demo-paris-elite.local",
        "status": "demo_pending",
        "notes": "WAR MODE ? Demo to book. Next action: send two possible slots. Estimated pilot value: EUR 700 MRR.",
        "value": 700,
        "score": 76,
    },
    {
        "email": "jeunesse92@demo-paris-elite.local",
        "status": "hot",
        "notes": "WAR MODE ? High-intent association lead. Next action: send short deck and ask for pilot sponsor. Estimated pilot value: EUR 700 MRR.",
        "value": 700,
        "score": 88,
    },
    {
        "email": "centre.social.levallois@demo-paris-elite.local",
        "status": "follow_up",
        "notes": "WAR MODE ? Follow-up required. No reply risk after 5 days. Estimated pilot value: EUR 400 MRR.",
        "value": 400,
        "score": 61,
    },
    {
        "email": "paris.ouest@demo-paris-elite.local",
        "status": "demo_pending",
        "notes": "WAR MODE ? Strategic network opportunity. Next action: book coordination demo. Estimated pilot value: EUR 900 MRR.",
        "value": 900,
        "score": 79,
    },
]


def find_lead_table(inspector):
    for table in inspector.get_table_names():
        low = table.lower()
        if "lead" in low or "access_request" in low:
            return table
    return None


def update_if_column_exists(table, columns, email, field, value):
    if field not in columns:
        return False

    db.session.execute(
        text(f"UPDATE {table} SET {field} = :value WHERE email = :email"),
        {"value": value, "email": email},
    )
    return True


def main():
    with app.app_context():
        inspector = inspect(db.engine)
        table = find_lead_table(inspector)

        if not table:
            print("No lead table found.")
            return

        columns = [c["name"] for c in inspector.get_columns(table)]
        print("Using lead table:", table)
        print("Columns:", columns)

        updated = 0

        for lead in WAR_LEADS:
            email = lead["email"]

            update_if_column_exists(table, columns, email, "status", lead["status"])
            update_if_column_exists(table, columns, email, "stage", lead["status"])
            update_if_column_exists(table, columns, email, "notes", lead["notes"])
            update_if_column_exists(table, columns, email, "message", lead["notes"])
            update_if_column_exists(table, columns, email, "score", lead["score"])
            update_if_column_exists(table, columns, email, "lead_score", lead["score"])
            update_if_column_exists(table, columns, email, "estimated_value", lead["value"])
            update_if_column_exists(table, columns, email, "value", lead["value"])
            update_if_column_exists(table, columns, email, "amount", lead["value"])
            update_if_column_exists(table, columns, email, "mrr", lead["value"])
            update_if_column_exists(table, columns, email, "updated_at", datetime.now(timezone.utc))
            update_if_column_exists(table, columns, email, "last_activity_at", datetime.now(timezone.utc) - timedelta(hours=updated + 1))

            updated += 1

        db.session.commit()

        print("")
        print("WAR MODE V1 SEEDED")
        print("Updated leads:", updated)
        print("Forecast:")
        print("Committed: EUR 0")
        print("Likely: EUR 2000")
        print("Stretch: EUR 3300")
        print("Next EUR 2000 path:")
        print("- CCAS Montrouge: EUR 600")
        print("- Mairie de Vanves: EUR 700")
        print("- Association Jeunesse 92: EUR 700")


if __name__ == "__main__":
    main()
