#!/usr/bin/env python3
"""Verify AdminUser password check in app context.

Usage:
  python backend/scripts/verify_admin_password.py
"""
import os
import sys

from flask import Flask

# Ensure package import path
HERE = os.path.abspath(os.path.dirname(__file__))
# Add repo root (one level above `backend`) so `import backend.app` works
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
# Also ensure the `backend` package directory is importable as top-level modules
# Some modules in `backend` use absolute imports like `from dependencies import ...`
backend_dir = os.path.join(ROOT, "backend")
if os.path.isdir(backend_dir):
    sys.path.insert(0, backend_dir)


def main():
    # Import app and models inside function to avoid import-time side effects
    try:
        from app import app  # backend.app
    except Exception:
        try:
            # fallback if module layout differs
            from backend.app import app
        except Exception as exc:
            print("Could not import app:", exc)
            return

    with app.app_context():
        try:
            from extensions import db
            from models import AdminUser
        except Exception as exc:
            print("Import models failed:", exc)
            return

        admin = None
        try:
            admin = db.session.query(AdminUser).filter_by(username="admin").first()
        except Exception:
            try:
                admin = AdminUser.query.filter_by(username="admin").first()
            except Exception as exc:
                print("Query admin failed:", exc)
                return

        if not admin:
            print("Admin user not found")
            return

        pw = "Admin12345!"
        try:
            ok = admin.check_password(pw)
        except Exception as exc:
            print("check_password raised:", exc)
            ok = None

        print("admin.id=", getattr(admin, "id", None))
        print("admin.username=", getattr(admin, "username", None))
        print("admin.password_hash=", getattr(admin, "password_hash", None))
        print("check_password(Admin12345!) ->", ok)


if __name__ == "__main__":
    main()
