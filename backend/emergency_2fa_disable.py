#!/usr/bin/env python3
"""
Emergency 2FA disable script for admin users
Use this when an admin loses access to their 2FA device
"""

import sys

# Add current directory to path
sys.path.insert(0, ".")

from appy import app

from .extensions import db
from .models import AdminUser


def main():
    print("🚨 Emergency 2FA Disable Tool")
    print("Този инструмент е само за спешни случаи!")
    print("")

    username = input("Въведете потребителско име на администратора: ").strip()

    if not username:
        print("❌ Потребителското име е задължително!")
        return

    with app.app_context():
        admin = AdminUser.query.filter_by(username=username).first()
        if not admin:
            print(f"❌ Администратор с потребителско име '{username}' не е намерен!")
            return

        print(f"👤 Намерен администратор: {admin.username}")
        print(f"📧 Имейл: {admin.email}")
        print(f"🔐 2FA статус: {'АКТИВИРАН' if admin.two_factor_enabled else 'ДЕАКТИВИРАН'}")
        print("")

        if not admin.two_factor_enabled:
            print("ℹ️ 2FA вече е деактивиран за този потребител.")
            return

        confirm = input(f"Сигурни ли сте че искате да ДЕАКТИВИРАТЕ 2FA за {username}? (да/не): ").strip().lower()

        if confirm not in ["да", "yes", "y"]:
            print("❌ Операцията е отменена.")
            return

        # Disable 2FA
        admin.two_factor_enabled = False
        admin.twofa_secret = None
        db.session.commit()

        print("✅ 2FA е успешно деактивиран!")
        print(f"🔓 Администраторът {username} вече може да влиза без 2FA код.")
        print("")
        print("⚠️  Препоръчваме да активирате 2FA отново след като възстановите достъпа до устройството си!")


if __name__ == "__main__":
    main()
