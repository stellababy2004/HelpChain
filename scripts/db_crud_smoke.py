import os
import sys
import argparse

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend import models as m
from backend.appy import app
from backend.extensions import db
from backend.local_db_guard import (
    canonical_confirmation_error,
    canonical_mismatch_error,
    is_canonical_db_uri,
    print_app_db_preflight,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="DB CRUD smoke (rollback-only)")
    parser.add_argument(
        "--confirm-canonical-db",
        action="store_true",
        help="Required safety flag to run write-in-transaction smoke",
    )
    args = parser.parse_args()

    with app.app_context():
        runtime_uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
        print_app_db_preflight(runtime_uri)
        if not args.confirm_canonical_db:
            print(canonical_confirmation_error())
            return 2
        if not is_canonical_db_uri(runtime_uri):
            print(canonical_mismatch_error(runtime_uri))
            return 2

        session = db.session

        # =====================
        # VOLUNTEER CRUD
        # =====================
        print("\n== VOLUNTEER CRUD (rollback) ==")
        v = m.Volunteer()
        session.add(v)
        session.flush()
        assert v.id is not None
        created_vid = v.id
        print("Created Volunteer.id =", created_vid)
        v2 = session.get(m.Volunteer, created_vid)
        assert v2 is not None
        print("Read Volunteer OK:", v2.id)
        v2.name = "Smoke Volunteer"
        v2.email = "volunteer_smoke@test.com"
        v2.is_active = True
        session.flush()
        session.refresh(v2)
        assert v2.name == "Smoke Volunteer"
        assert v2.email == "volunteer_smoke@test.com"
        assert v2.is_active is True
        print("Update Volunteer OK:", v2.name, v2.email, v2.is_active)

        # =====================
        # USER CRUD
        # =====================
        u = m.User(username="u1", email="u1@test.com", password_hash="x")
        session.add(u)
        session.flush()
        assert u.id is not None
        user_id = u.id
        print("Created User.id =", user_id)
        u2 = session.get(m.User, user_id)
        assert u2 is not None
        u2.role = "tester"
        session.flush()

        # =====================
        # REQUEST CRUD
        # =====================
        if hasattr(m, "Request"):
            r = m.Request(
                title="T",
                description="D",
                name="N",
                email="n@test.com",
                phone="000",
                city="Paris",
                region="IDF",
                location_text="Paris",
                message="Hello",
                status="new",
                priority="normal",
                source_channel="web",
                user_id=user_id,
            )
            session.add(r)
            session.flush()
            assert r.id is not None
            assert r.user_id == user_id
            print("Created Request.id =", r.id, "user_id =", r.user_id)
            r.status = "in_progress"
            r.priority = "high"
            session.flush()
            assert r.user_id == user_id, "Request.user_id changed unexpectedly"
            print("Updated Request OK, user_id still =", r.user_id)

        # =====================
        # GLOBAL ROLLBACK
        # =====================
        session.rollback()
        print("Rollback OK — DB clean")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
