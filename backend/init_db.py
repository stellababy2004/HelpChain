#!/usr/bin/env python3
"""
Database initialization script for HelpChain
Creates default roles, permissions, and admin user
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, ".")

from appy import app
from .extensions import db
from .models import User, RoleEnum
from werkzeug.security import generate_password_hash
from permissions import initialize_default_roles_and_permissions


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
            # Create default admin user
            admin_user = User(
                username="admin",
                email="admin@helpchain.live",
                password_hash=generate_password_hash(
                    os.getenv("ADMIN_USER_PASSWORD", "admin123")
                ),
                role=RoleEnum.superadmin,
                is_active=True,
            )

            db.session.add(admin_user)
            db.session.commit()

            print("✅ Базата данни е успешно инициализирана!")
            print("✅ Администраторски потребител е създаден!")
            print("👤 Потребителско име: admin")
            print("🔑 Парола: admin123")
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
