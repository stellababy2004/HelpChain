import os
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"

os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

from app import app
from models import Volunteer

from extensions import db

OUTPUT_DIR = Path("..") / "snapshots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VOL_ID = int(os.getenv("TEST_VOLUNTEER_ID", "6"))


def ensure_volunteer(vol_id: int):
    with app.app_context():
        db.create_all()
        v = db.session.query(Volunteer).get(vol_id)
        if v is None:
            # try to find by default email
            v = (
                db.session.query(Volunteer)
                .filter_by(
                    email=os.getenv("TEST_VOLUNTEER_EMAIL", "tester@example.com")
                )
                .first()
            )
        if v is None:
            v = Volunteer(
                name=os.getenv("TEST_VOLUNTEER_NAME", "Тестов Доброволец"),
                email=os.getenv("TEST_VOLUNTEER_EMAIL", "tester@example.com"),
                phone=os.getenv("TEST_VOLUNTEER_PHONE", "+359888000000"),
                location=os.getenv("TEST_VOLUNTEER_LOCATION", "София"),
            )
            db.session.add(v)
            db.session.commit()
        return v


def main():
    v = ensure_volunteer(VOL_ID)
    with app.test_client() as client:
        # set session directly so no password required
        with client.session_transaction() as sess:
            sess["volunteer_logged_in"] = True
            sess["volunteer_id"] = v.id
        resp = client.get("/volunteer_dashboard")
        html = resp.get_data(as_text=True)
        out_path = OUTPUT_DIR / f"volunteer_{v.id}.html"
        out_path.write_text(html, encoding="utf-8")
        print(f"Wrote snapshot: {out_path.resolve()}")


if __name__ == "__main__":
    main()
