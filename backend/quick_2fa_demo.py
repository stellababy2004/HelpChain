#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Бърза демонстрация на двустепенна автентикация (2FA)
"""

import sys
import os
from datetime import datetime
import qrcode
import io
import base64

# Добавяме backend директорията към path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.appy import app, db, generate_totp_secret, verify_totp_token, generate_backup_codes
    from backend.models import AdminUser, AdminRole
    from werkzeug.security import generate_password_hash
    import pyotp
    import json
except ImportError as e:
    from appy import app, db, generate_totp_secret, verify_totp_token, generate_backup_codes
    from models import AdminUser, AdminRole
    from werkzeug.security import generate_password_hash
    import pyotp
    import json

def demo_2fa_live():
    """Демо на 2FA в реално време"""
    print("🔐 === ДЕМО НА ДВУСТЕПЕННА АВТЕНТИКАЦИЯ ===\n")
    
    with app.app_context():
        # Създаваме или намираме демо потребител
        demo_user = AdminUser.query.filter_by(username="demo_2fa").first()
        if not demo_user:
            demo_user = AdminUser(
                username="demo_2fa",
                email="demo@helpchain.bg",
                password_hash=generate_password_hash("demo123!"),
                role=AdminRole.ADMIN,
                is_active=True
            )
            db.session.add(demo_user)
            db.session.commit()
            print("✅ Създаден демо потребител")
        
        # Настройка на 2FA
        if not demo_user.totp_secret:
            demo_user.totp_secret = generate_totp_secret()
            db.session.commit()
        
        print(f"📱 TOTP Secret: {demo_user.totp_secret}")
        
        # Генериране на QR код
        totp = pyotp.TOTP(demo_user.totp_secret)
        qr_uri = totp.provisioning_uri(
            name=demo_user.email,
            issuer_name="HelpChain.bg"
        )
        
        print(f"📷 QR URI: {qr_uri}\n")
        
        # Генериране на backup кодове
        backup_codes = generate_backup_codes()
        demo_user.backup_codes = json.dumps(backup_codes)
        demo_user.two_factor_enabled = True
        db.session.commit()
        
        print("🔑 Backup кодове за спешни случаи:")
        for i, code in enumerate(backup_codes[:5], 1):
            print(f"   {i}. {code}")
        print(f"   ... и още {len(backup_codes) - 5} кода\n")
        
        # Демонстрация на генериране на кодове
        print("⏰ TOTP кодове (обновяват се на всеки 30 секунди):")
        print("-" * 50)
        
        for i in range(10):  # Показваме 10 кода
            current_token = totp.now()
            is_valid = verify_totp_token(demo_user, current_token)
            timestamp = datetime.now().strftime("%H:%M:%S")
            remaining_time = 30 - (datetime.now().second % 30)
            
            status = "✅ ВАЛИДЕН" if is_valid else "❌ НЕВАЛИДЕН"
            print(f"{timestamp}: {current_token} - {status} (остават {remaining_time}с)")
            
            # Чакаме 3 секунди за следващата проверка
            import time
            time.sleep(3)
        
        print("\n" + "=" * 50)
        print("🎯 Резултат от демото:")
        print(f"   👤 Потребител: {demo_user.username}")
        print(f"   📧 Email: {demo_user.email}")
        print(f"   🔐 2FA активирана: {'✅' if demo_user.two_factor_enabled else '❌'}")
        print(f"   🔑 Secret дължина: {len(demo_user.totp_secret)} символа")
        print(f"   💾 Backup кодове: {len(backup_codes)} броя")
        
        return demo_user

def show_current_codes():
    """Показва текущите кодове за демо потребителя"""
    with app.app_context():
        demo_user = AdminUser.query.filter_by(username="demo_2fa").first()
        if not demo_user or not demo_user.totp_secret:
            print("❌ Демо потребителят не е намерен или няма настроена 2FA")
            return
        
        totp = pyotp.TOTP(demo_user.totp_secret)
        
        print("🕐 Текущи TOTP кодове:")
        print("-" * 30)
        
        # Показваме предишния, текущия и следващия код
        for offset in [-1, 0, 1]:
            token = totp.at(datetime.now().timestamp() + offset * 30)
            time_desc = ["Предишен", "ТЕКУЩ", "Следващ"][offset + 1]
            marker = "👉 " if offset == 0 else "   "
            print(f"{marker}{time_desc}: {token}")

def generate_qr_code():
    """Генерира QR код за сканиране"""
    with app.app_context():
        demo_user = AdminUser.query.filter_by(username="demo_2fa").first()
        if not demo_user or not demo_user.totp_secret:
            print("❌ Демо потребителят не е намерен")
            return
        
        totp = pyotp.TOTP(demo_user.totp_secret)
        qr_uri = totp.provisioning_uri(
            name=demo_user.email,
            issuer_name="HelpChain.bg"
        )
        
        print("📱 Информация за мобилно приложение:")
        print("-" * 40)
        print(f"🔗 QR URI: {qr_uri}")
        print(f"🔑 Secret Key: {demo_user.totp_secret}")
        print(f"📧 Account: {demo_user.email}")
        print(f"🏢 Issuer: HelpChain.bg")
        print(f"⚙️  Algorithm: SHA1")
        print(f"🔢 Digits: 6")
        print(f"⏱️  Period: 30 seconds")
        
        # Опитваме се да генерираме ASCII QR код
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=1,
                border=1,
            )
            qr.add_data(qr_uri)
            qr.make(fit=True)
            
            print("\n📷 ASCII QR код (сканирайте с приложение за автентикация):")
            print("-" * 60)
            qr.print_ascii(invert=True)
        except Exception as e:
            print(f"\n⚠️  Не може да се генерира ASCII QR код: {e}")

def cleanup_demo():
    """Изчиства демо данните"""
    with app.app_context():
        demo_user = AdminUser.query.filter_by(username="demo_2fa").first()
        if demo_user:
            db.session.delete(demo_user)
            db.session.commit()
            print("🗑️  Демо данните са изчистени")
        else:
            print("ℹ️  Няма демо данни за изчистване")

def main():
    """Главна функция"""
    print("🔐 HelpChain.bg - Демо на двустепенна автентикация")
    print("=" * 55)
    
    while True:
        print("\n📋 Изберете опция:")
        print("1. 🚀 Пълно демо на 2FA (30 секунди)")
        print("2. 🕐 Показване на текущи кодове")
        print("3. 📱 Генериране на QR код")
        print("4. 🗑️  Изчистване на демо данни")
        print("5. 🚪 Изход")
        
        choice = input("\n➡️  Въведете номер (1-5): ").strip()
        
        if choice == "1":
            demo_2fa_live()
        elif choice == "2":
            show_current_codes()
        elif choice == "3":
            generate_qr_code()
        elif choice == "4":
            cleanup_demo()
        elif choice == "5":
            print("👋 Довиждане!")
            break
        else:
            print("❌ Невалиден избор. Моля опитайте отново.")

if __name__ == "__main__":
    main()