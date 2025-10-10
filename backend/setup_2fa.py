#!/usr/bin/env python3
"""
Setup 2FA for admin user
"""

import sys

# Add current directory to path
sys.path.insert(0, ".")

from appy import app
from models import AdminUser
from extensions import db
import pyotp


def main():
    print("🔐 Настройка на 2FA за администратор...")

    with app.app_context():
        admin = AdminUser.query.filter_by(username="admin").first()
        if not admin:
            print("❌ Администраторски потребител не е намерен!")
            return

        print(f"👤 Намерен администратор: {admin.username}")

        # Generate TOTP secret
        if not admin.twofa_secret:
            secret = pyotp.random_base32()
            admin.twofa_secret = secret
            print("🔑 Генериран нов TOTP secret")
        else:
            secret = admin.twofa_secret
            print("🔑 Използван съществуващ TOTP secret")

        # Create provisioning URI
        totp = pyotp.TOTP(secret)
        uri = totp.provisioning_uri(
            name=f"HelpChain Admin ({admin.username})", issuer_name="HelpChain.bg"
        )

        print("\n📱 За да настроите Microsoft Authenticator:")
        print("1. Отворете Microsoft Authenticator приложението")
        print("2. Натиснете '+' за добавяне на акаунт")
        print("3. Изберете 'Друг акаунт (Google, Facebook и др.)'")
        print("4. Сканирайте QR кода или въведете кода ръчно")
        print("")
        print("🔗 Provisioning URI (за ръчно въвеждане):")
        print(uri)
        print("")
        print("📋 Secret key (запазете го на сигурно място):")
        print(secret)
        print("")

        # Enable 2FA
        admin.twofa_enabled = True
        db.session.commit()

        print("✅ 2FA е активиран за администратора!")
        print("")
        print("🚀 Сега можете да влезете като администратор и да тествате 2FA")


if __name__ == "__main__":
    main()
