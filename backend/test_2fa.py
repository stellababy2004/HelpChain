#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тестов скрипт за двустепенна автентикация (2FA)
"""

import sys
import os
from datetime import datetime

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

def test_2fa_setup():
    """Тест за настройка на 2FA"""
    print("=== Тест за настройка на 2FA ===\n")
    
    with app.app_context():
        # Създаваме тестов потребител ако не съществува
        test_user = AdminUser.query.filter_by(username="test_2fa").first()
        if not test_user:
            test_user = AdminUser(
                username="test_2fa",
                email="test_2fa@helpchain.bg",
                password_hash=generate_password_hash("test123!"),
                role=AdminRole.ADMIN,
                is_active=True
            )
            db.session.add(test_user)
            db.session.commit()
            print("✓ Създаден тестов потребител: test_2fa")
        
        # Тест 1: Генериране на TOTP secret
        if not test_user.totp_secret:
            test_user.totp_secret = generate_totp_secret()
            db.session.commit()
        
        print(f"✓ TOTP Secret: {test_user.totp_secret}")
        
        # Тест 2: Генериране на QR код URI
        totp = pyotp.TOTP(test_user.totp_secret)
        qr_uri = totp.provisioning_uri(
            name=test_user.email,
            issuer_name="HelpChain.bg Admin"
        )
        print(f"✓ QR URI: {qr_uri}")
        
        # Тест 3: Генериране на backup кодове
        backup_codes = generate_backup_codes()
        test_user.backup_codes = json.dumps(backup_codes)
        print(f"✓ Backup кодове: {backup_codes[:3]}... (показани първите 3)")
        
        # Тест 4: Генериране и проверка на TOTP токен
        current_token = totp.now()
        print(f"✓ Текущ TOTP токен: {current_token}")
        
        # Проверка на токена
        is_valid = verify_totp_token(test_user, current_token)
        print(f"✓ Валидация на токен: {'Успешна' if is_valid else 'Неуспешна'}")
        
        # Тест 5: Активиране на 2FA
        test_user.two_factor_enabled = True
        db.session.commit()
        print(f"✓ 2FA активирана: {test_user.two_factor_enabled}")
        
        # Резултати
        print(f"\n=== Резултат ===")
        print(f"Потребител: {test_user.username}")
        print(f"2FA активирана: {test_user.two_factor_enabled}")
        print(f"TOTP Secret дължина: {len(test_user.totp_secret) if test_user.totp_secret else 0}")
        print(f"Backup кодове: {len(backup_codes)} броя")
        
        return test_user

def test_totp_codes():
    """Тест за генериране на няколко TOTP кода"""
    print("\n=== Тест за TOTP кодове ===\n")
    
    with app.app_context():
        test_user = AdminUser.query.filter_by(username="test_2fa").first()
        if not test_user or not test_user.totp_secret:
            print("Грешка: Тестовият потребител не е намерен или няма TOTP secret")
            return
        
        totp = pyotp.TOTP(test_user.totp_secret)
        
        print("Генериране на 5 последователни кода:")
        import time
        for i in range(5):
            current_token = totp.now()
            is_valid = verify_totp_token(test_user, current_token)
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            print(f"{timestamp}: {current_token} - {'✓ Валиден' if is_valid else '✗ Невалиден'}")
            
            if i < 4:  # Не чакаме след последния
                print("  Чакам 30 секунди за нов код...")
                time.sleep(30)

def show_qr_info():
    """Показва информация за QR код"""
    print("\n=== QR код информация ===\n")
    
    with app.app_context():
        test_user = AdminUser.query.filter_by(username="test_2fa").first()
        if not test_user or not test_user.totp_secret:
            print("Грешка: Тестовият потребител не е намерен или няма TOTP secret")
            return
        
        totp = pyotp.TOTP(test_user.totp_secret)
        qr_uri = totp.provisioning_uri(
            name=test_user.email,
            issuer_name="HelpChain.bg Admin"
        )
        
        print("За сканиране с приложение за автентикация:")
        print(f"URI: {qr_uri}")
        print(f"\nРъчно въвеждане:")
        print(f"Secret Key: {test_user.totp_secret}")
        print(f"Account: {test_user.email}")
        print(f"Issuer: HelpChain.bg Admin")
        print(f"Algorithm: SHA1")
        print(f"Digits: 6")
        print(f"Period: 30 seconds")

def cleanup_test_data():
    """Изчиства тестовите данни"""
    print("\n=== Изчистване на тестови данни ===\n")
    
    with app.app_context():
        test_user = AdminUser.query.filter_by(username="test_2fa").first()
        if test_user:
            db.session.delete(test_user)
            db.session.commit()
            print("✓ Тестовият потребител е изтрит")
        else:
            print("Няма тестови данни за изчистване")

def main():
    """Главна функция"""
    print("=== Тест на двустепенна автентикация (2FA) ===\n")
    
    while True:
        print("\nИзберете опция:")
        print("1. Настройка на 2FA (пълен тест)")
        print("2. Тест на TOTP кодове (отнема време)")
        print("3. Показване на QR информация")
        print("4. Изчистване на тестови данни")
        print("5. Изход")
        
        choice = input("\nВъведете номер (1-5): ").strip()
        
        if choice == "1":
            test_2fa_setup()
        elif choice == "2":
            test_totp_codes()
        elif choice == "3":
            show_qr_info()
        elif choice == "4":
            cleanup_test_data()
        elif choice == "5":
            print("Довиждане!")
            break
        else:
            print("Невалиден избор. Моля опитайте отново.")

if __name__ == "__main__":
    main()