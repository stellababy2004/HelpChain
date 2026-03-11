import csv
import argparse
from backend.appy import app
from backend.extensions import db
from backend.helpchain_backend.src.models import ProfessionalLead


def import_csv(file_path, commit=False):

    with app.app_context():

        created = 0

        with open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:

                email = (row.get("email") or "").strip()

                existing = None
                if email:
                    existing = ProfessionalLead.query.filter_by(email=email).first()

                if existing:
                    print("SKIP duplicate:", email)
                    continue

                lead = ProfessionalLead(
                    full_name=row.get("full_name"),
                    email=email,
                    phone=row.get("phone"),
                    profession=row.get("profession"),
                    city=row.get("city"),
                    organization=row.get("organization"),
                    source=row.get("source") or "csv_import",
                    status="imported",
                    notes=row.get("notes"),
                )

                db.session.add(lead)
                created += 1

        if commit:
            db.session.commit()
            print("IMPORT DONE:", created, "records")
        else:
            db.session.rollback()
            print("DRY RUN:", created, "records")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--commit", action="store_true")

    args = parser.parse_args()

    import_csv(args.file, args.commit)
