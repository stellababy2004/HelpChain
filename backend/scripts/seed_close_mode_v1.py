
from datetime import datetime, timezone, timedelta
from sqlalchemy import inspect, text

from backend.appy import app
from backend.extensions import db

CLOSE_MODE = [
    {
        "email": "ccas.montrouge@demo-paris-elite.local",
        "status": "proposal_sent",
        "score": 84,
        "value": 600,
        "notes": "CLOSE MODE ? Proposition envoy?e. Next: relance d?cision pilote sous 48h.",
        "next_action": "Relancer la proposition pilote",
    },
    {
        "email": "solidarite.vanves@demo-paris-elite.local",
        "status": "awaiting_signature",
        "score": 91,
        "value": 700,
        "notes": "CLOSE MODE ? Accord verbal obtenu. Next: envoyer r?capitulatif + validation ?crite.",
        "next_action": "Obtenir validation ?crite",
    },
    {
        "email": "jeunesse92@demo-paris-elite.local",
        "status": "pilot_live",
        "score": 88,
        "value": 700,
        "notes": "CLOSE MODE ? Pilote en discussion active. Next: cadrer p?rim?tre + r?f?rent.",
        "next_action": "Cadrer le pilote",
    },
    {
        "email": "centre.social.levallois@demo-paris-elite.local",
        "status": "payment_pending",
        "score": 73,
        "value": 400,
        "notes": "CLOSE MODE ? Paiement ou bon de commande attendu. Next: relance administrative.",
        "next_action": "Relancer paiement / bon de commande",
    },
    {
        "email": "paris.ouest@demo-paris-elite.local",
        "status": "won",
        "score": 100,
        "value": 1000,
        "notes": "CLOSE MODE ? Opportunit? gagn?e en d?monstration. Next: pr?parer onboarding.",
        "next_action": "Pr?parer onboarding pilote",
    },
]


def find_lead_table(inspector):
    for table in inspector.get_table_names():
        low = table.lower()
        if "lead" in low or "access_request" in low:
            return table
    return None


def set_col(table, columns, email, col, value):
    if col not in columns:
        return
    db.session.execute(
        text(f"UPDATE {table} SET {col} = :value WHERE email = :email"),
        {"value": value, "email": email},
    )


def main():
    with app.app_context():
        inspector = inspect(db.engine)
        table = find_lead_table(inspector)

        if not table:
            print("No lead table found.")
            return

        columns = [c["name"] for c in inspector.get_columns(table)]
        print("Using table:", table)
        print("Columns:", columns)

        now = datetime.now(timezone.utc)

        for i, lead in enumerate(CLOSE_MODE):
            email = lead["email"]

            set_col(table, columns, email, "status", lead["status"])
            set_col(table, columns, email, "stage", lead["status"])
            set_col(table, columns, email, "score", lead["score"])
            set_col(table, columns, email, "lead_score", lead["score"])
            set_col(table, columns, email, "estimated_value", lead["value"])
            set_col(table, columns, email, "value", lead["value"])
            set_col(table, columns, email, "amount", lead["value"])
            set_col(table, columns, email, "mrr", lead["value"])
            set_col(table, columns, email, "notes", lead["notes"])
            set_col(table, columns, email, "message", lead["notes"])
            set_col(table, columns, email, "next_action", lead["next_action"])
            set_col(table, columns, email, "updated_at", now - timedelta(hours=i))
            set_col(table, columns, email, "last_activity_at", now - timedelta(hours=i + 1))

        db.session.commit()

        print("")
        print("CLOSE MODE V1 DONE")
        print("Pipeline stages:")
        print("- proposal_sent")
        print("- awaiting_signature")
        print("- pilot_live")
        print("- payment_pending")
        print("- won")
        print("")
        print("Close path:")
        print("Won: EUR 1000")
        print("Near-close: EUR 1700")
        print("Open pipeline: EUR 3400")


if __name__ == "__main__":
    main()
