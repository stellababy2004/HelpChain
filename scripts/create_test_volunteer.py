import os
import sys
from pathlib import Path

# Make backend directory importable (same approach as run.py)
THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"

# Change working dir to backend and insert into sys.path
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

# Import the Flask app and DB
try:
    from app import app
    from models import Volunteer

    from extensions import db
except Exception as e:
    print("Failed to import app/db/models:", e)
    raise


def main():
    with app.app_context():
        # ensure tables exist
        try:
            db.create_all()
        except Exception as e:
            print("create_all failed:", e)
        # create or get existing test volunteer by email
        email = os.getenv("TEST_VOLUNTEER_EMAIL", "tester@example.com")
        v = db.session.query(Volunteer).filter_by(email=email).first()
        if v is None:
            v = Volunteer(
                name=os.getenv("TEST_VOLUNTEER_NAME", "Тестов Доброволец"),
                email=email,
                phone=os.getenv("TEST_VOLUNTEER_PHONE", "+359888000000"),
                location=os.getenv("TEST_VOLUNTEER_LOCATION", "София"),
            )
            db.session.add(v)
            db.session.commit()
            print(f"Created volunteer id={v.id} email={v.email} name={v.name}")
        else:
            print(f"Volunteer already exists id={v.id} email={v.email} name={v.name}")


if __name__ == "__main__":
    main()
