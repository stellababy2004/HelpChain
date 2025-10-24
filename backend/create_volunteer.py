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
from backend.extensions import db
from backend.models import User, Volunteer


def main():
    print("🔄 Създаване на тестов доброволец...")

    with app.app_context():
        try:
            # Create volunteer user
            volunteer_user = User(
                username="volunteer1",
                email="stiliana.stoyanova@orange.fr",
                password_hash=generate_password_hash("volunteer123"),
                role="volunteer",
                is_active=True,
            )

            db.session.add(volunteer_user)
            db.session.commit()

            # Also create Volunteer record
            volunteer = Volunteer(
                name="Test Volunteer",
                email="stiliana.stoyanova@orange.fr",
                phone="000000000",
                skills="Помощ при пазаруване, придружаване до лекар",
                location="Sofia, Bulgaria",
            )

            db.session.add(volunteer)
            db.session.commit()

            print("✅ Доброволец е успешно създаден!")
            print("👤 Email: stiliana.stoyanova@orange.fr")
            print("🔑 Парола: volunteer123")
            print("📍 Име: Test Volunteer")

        except Exception as e:
            print(f"❌ Грешка при създаване: {e}")
            db.session.rollback()
            import traceback

            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
