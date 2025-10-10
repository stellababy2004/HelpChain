#!/usr/bin/env python3
"""
Create a test volunteer user for HelpChain
"""

import sys

# Add current directory to path
sys.path.insert(0, ".")

from appy import app
from extensions import db
from models import User, Volunteer
from werkzeug.security import generate_password_hash


def main():
    print("🔄 Създаване на тестов доброволец...")

    with app.app_context():
        try:
            # Create volunteer user
            volunteer_user = User(
                username="volunteer1",
                email="ivan@example.com",
                password_hash=generate_password_hash("volunteer123"),
                role="volunteer",
                is_active=True,
            )

            db.session.add(volunteer_user)
            db.session.commit()

            # Also create Volunteer record
            volunteer = Volunteer(
                name="Иван Петров",
                email="ivan@example.com",
                phone="+359 88 123 4567",
                skills="Помощ при пазаруване, придружаване до лекар",
                location="София",
            )

            db.session.add(volunteer)
            db.session.commit()

            print("✅ Доброволец е успешно създаден!")
            print("👤 Email: ivan@example.com")
            print("🔑 Парола: volunteer123")
            print("📍 Име: Иван Петров")

        except Exception as e:
            print(f"❌ Грешка при създаване: {e}")
            db.session.rollback()
            import traceback

            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
