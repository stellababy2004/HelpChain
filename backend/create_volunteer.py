#!/usr/bin/env python3
"""
Create a test volunteer user for HelpChain
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from werkzeug.security import generate_password_hash

from appy import app

try:
    # Prefer canonical top-level imports
    from extensions import db
    from models import User, Volunteer
except Exception:
    # Fallback for package/script execution styles
    from backend.extensions import db
    from backend.models import User, Volunteer


DEFAULT_EMAIL = "ivan@example.com"
DEFAULT_PASSWORD = "volunteer123"
DEFAULT_NAME = "Ivan Tester"


def _resolve_credentials() -> tuple[str, str, str]:
    """Allow overriding default volunteer credentials via CLI arguments."""

    email = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EMAIL
    username = sys.argv[2] if len(sys.argv) > 2 else email.split("@")[0]
    password = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_PASSWORD

    return email.lower(), username, password


def main():
    print("🔄 Създаване или обновяване на тестов доброволец...")

    with app.app_context():
        try:
            email, username, password = _resolve_credentials()

            user = User.query.filter_by(email=email).first()
            if user:
                print("ℹ️ Наличие на потребител – актуализиране на данните...")
                user.username = username
                user.password_hash = generate_password_hash(password)
                user.role = "volunteer"
                user.is_active = True
            else:
                user = User(
                    username=username,
                    email=email,
                    password_hash=generate_password_hash(password),
                    role="volunteer",
                    is_active=True,
                )
                db.session.add(user)

            db.session.commit()

            volunteer = Volunteer.query.filter_by(email=email).first()
            if volunteer:
                print("ℹ️ Съществуващ доброволец – актуализиране на профил...")
                volunteer.name = volunteer.name or DEFAULT_NAME
                volunteer.phone = volunteer.phone or "000000000"
                volunteer.skills = volunteer.skills or "Обща помощ, пазаруване"
                volunteer.location = volunteer.location or "Varna, Bulgaria"
            else:
                volunteer = Volunteer(
                    name=DEFAULT_NAME,
                    email=email,
                    phone="000000000",
                    skills="Обща помощ, пазаруване",
                    location="Varna, Bulgaria",
                )
                db.session.add(volunteer)

            db.session.commit()

            print("✅ Доброволец е готов за вход!")
            print(f"👤 Email: {email}")
            print(f"🔑 Парола: {password}")
            print(f"📍 Потребителско име: {username}")

        except Exception as e:
            print(f"❌ Грешка при създаване: {e}")
            db.session.rollback()
            import traceback

            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
