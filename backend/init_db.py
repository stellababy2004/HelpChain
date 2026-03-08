#!/usr/bin/env python3
"""
Database initialization script for HelpChain
Creates default roles, permissions, and admin user

WARNING:
- Manual-only bootstrap helper.
- Do not use in production runtime startup/request paths.
- Use Alembic migrations for production schema changes.
"""

import os
import sys

# Ensure backend package is importable whether script is run as module or standalone
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CURRENT_DIR)
sys.path.insert(0, os.path.dirname(CURRENT_DIR))

from werkzeug.security import generate_password_hash

from appy import app
from permissions import initialize_default_roles_and_permissions

try:  # Prefer relative import when available
    from .extensions import db
    from .models import AdminUser, RoleEnum, User, Volunteer
except ImportError:  # Fallback for direct script execution
    from backend.extensions import db
    from backend.models import AdminUser, RoleEnum, User, Volunteer


def main():
    print("🔄 Инициализиране на базата данни на HelpChain...")

    with app.app_context():
        try:
            print("🔄 Изтриване на съществуващите таблици...")
            db.drop_all()

            print("🔄 Създаване на нови таблици...")
            db.create_all()

            print("🔄 Инициализиране на роли и разрешения...")
            initialize_default_roles_and_permissions()

            print("🔄 Създаване на администраторски потребител...")
            admin_user = AdminUser(
                username="admin",
                email="admin@helpchain.live",
                role=RoleEnum.ADMIN.value,
            )
            admin_user.set_password(os.getenv("ADMIN_USER_PASSWORD", "admin123"))
            db.session.add(admin_user)
            db.session.commit()

            print("🔄 Добавяне на тестов доброволец ivan@example.com...")

            volunteer = Volunteer(
                name="Ivan Tester",
                email="ivan@example.com",
                city="Varna",
            )

            db.session.add(volunteer)
            db.session.commit()

            print("✅ Базата данни е успешно инициализирана!")
            print("✅ Администраторски потребител е създаден!")
            print("👤 Потребителско име: admin")
            print("🔑 Парола: admin123")
            print("✅ Тестов доброволец е добавен!")
            print("📧 Email: ivan@example.com")
            print("")
            print("🚀 Можете да стартирате приложението с: python appy.py")

        except Exception as e:
            print(f"❌ Грешка при инициализация: {e}")
            db.session.rollback()
            import traceback

            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
