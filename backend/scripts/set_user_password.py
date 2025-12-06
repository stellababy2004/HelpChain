"""Set or create a user and assign a password (dry-run by default).

Usage examples:
  python backend\scripts\set_user_password.py --username testuser --password secret123 --commit
  python backend\scripts\set_user_password.py --username volunteer --password NewPass123!

This script is intentionally conservative: by default it runs in dry-run mode
and only prints actions. Use `--commit` to apply changes to the database.
"""
import argparse
import os
import sys

# Ensure repo root and backend dir are importable when running from repo root
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
backend_dir = os.path.join(repo_root, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from backend import models
from backend.app import app

try:
    from backend.extensions import db as ext_db
except Exception:
    ext_db = None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--username", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--commit", action="store_true", help="Apply changes to DB")
    args = p.parse_args()

    with app.app_context():
        user = models.User.query.filter_by(username=args.username).first()
        if user is None:
            print(f"User {args.username} not found — will create (dry-run)")
            if args.commit:
                user = models.User(username=args.username, email=f"{args.username}@example.test")
                try:
                    user.set_password(args.password)
                except Exception:
                    user.password_hash = args.password
                # default role to 'user'
                try:
                    user.role = models.RoleEnum.USER.value
                except Exception:
                    user.role = "user"
                # Use the Flask-SQLAlchemy bound session if available
                if ext_db is not None:
                    ext_db.session.add(user)
                    ext_db.session.commit()
                else:
                    models.db.session.add(user)
                    models.db.session.commit()
                print(f"Created user {args.username} and set password")
            else:
                print("Run with --commit to actually create the user and set password.")
            return

        print(f"Found user {args.username} (id={getattr(user,'id',None)})")
        print("Current password_hash:", getattr(user, "password_hash", None))
        try:
            ok = user.check_password(args.password)
        except Exception as e:
            ok = False
            print("check_password raised:", e)
        print("check_password(...) =>", ok)
        if not ok:
            print("Password does not match; will update (dry-run)")
            if args.commit:
                try:
                    user.set_password(args.password)
                except Exception:
                    user.password_hash = args.password
                if ext_db is not None:
                    ext_db.session.add(user)
                    ext_db.session.commit()
                else:
                    models.db.session.add(user)
                    models.db.session.commit()
                print(f"Updated password for {args.username}")
            else:
                print("Run with --commit to update the password.")
        else:
            print("Password already matches; no action taken.")


if __name__ == "__main__":
    main()
