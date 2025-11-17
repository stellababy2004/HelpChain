import os
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(HERE)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app import app, db  # type: ignore
from models import AdminUser  # type: ignore


def main():
    # Disable CSRF for this smoke test to allow programmatic POSTs
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        # Ensure admin user exists
        admin = AdminUser.query.filter_by(username="admin").first()
        if not admin:
            print("AdminUser not found; seeding one for test...")
            admin = AdminUser(username="admin", email="admin@example.com")
            admin.set_password("secret123")
            db.session.add(admin)
            db.session.commit()

        # Reset counters before test
        admin.failed_login_attempts = 0
        admin.locked_until = None
        db.session.add(admin)
        db.session.commit()

        client = app.test_client()

        # 1) Trigger lockout: 5 bad attempts
        for i in range(5):
            r = client.post(
                "/admin/login", data={"username": "admin", "password": "wrong"}
            )
            print(f"Attempt {i+1} bad -> status {r.status_code}")

        # 2) Check account is locked
        r = client.post(
            "/admin/login", data={"username": "admin", "password": "StrongPass123"}
        )
        print("Post-lockout login status (expect 423):", r.status_code)

        # 3) Manually expire lock and login successfully
        admin = AdminUser.query.filter_by(username="admin").first()
        admin.locked_until = datetime.utcnow() - timedelta(minutes=1)
        admin.failed_login_attempts = 0
        db.session.add(admin)
        db.session.commit()

        r = client.post(
            "/admin/login",
            data={"username": "admin", "password": "StrongPass123"},
            follow_redirects=False,
        )
        print("After unlock, login status (expect 302):", r.status_code)


if __name__ == "__main__":
    main()
