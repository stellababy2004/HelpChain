import os
import sys

# Ensure repository root (backend) is on sys.path when running as a script
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(HERE)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app import app
from models import User, db


def main():
    with app.app_context():
        # 1) Check existing admin user and possible auto-migration
        a = User.query.filter_by(username="admin").first()
        print("Admin user found:", bool(a))
        if a:
            try:
                prefix_before = (
                    (a.password_hash or "").split("$")[0] if a.password_hash else None
                )
                print("Initial hash prefix:", prefix_before)
                ok = a.check_password("secret123")
                print("Password valid before upgrade:", ok)
                prefix_after = (
                    (a.password_hash or "").split("$")[0] if a.password_hash else None
                )
                print(
                    "Hash prefix after check (should be argon2id if migrated):",
                    prefix_after,
                )
            except Exception as e:
                print("Admin hash check error:", e)

        # 2) Optional check for an argon2 test user
        u = User.query.filter_by(username="argon_test").first()
        print("argon_test exists:", bool(u))
        if u and u.password_hash:
            print("argon_test hash prefix:", (u.password_hash or "").split("$")[0])

        # 3) Password policy smoke tests
        # Ensure a clean slate for the strong test user on repeated runs
        existing = User.query.filter_by(username="policy_strong").first()
        if existing:
            try:
                db.session.delete(existing)
                db.session.commit()
            except Exception:
                db.session.rollback()

        strong_user = User(username="policy_strong", email="policy_strong@example.com")
        try:
            strong_user.set_password("StrongPass123")
            db.session.add(strong_user)
            db.session.commit()
            print(
                "Strong hash prefix:", (strong_user.password_hash or "").split("$")[0]
            )
        except Exception as e:
            print("Strong password unexpected failure:", e)

        errors = []
        weak_passwords = [
            "short8A1",
            "nouppercase123",
            "NOLOWERCASE123",
            "NoDigitsAAAA",
            "short",
        ]
        for pwd in weak_passwords:
            try:
                tmp = User(username=f"tmp_{pwd}", email=f"{pwd}@example.com")
                tmp.set_password(pwd)
                errors.append(f"Unexpected accept: {pwd}")
            except Exception as e:
                errors.append(f"Expected fail {pwd}: {e}")
        print("\n".join(errors))


if __name__ == "__main__":
    main()
