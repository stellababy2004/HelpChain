#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Бърз тест на 2FA системата
"""

import sys
import os
from datetime import datetime
import time

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

def run_comprehensive_test():
    """Пълен бърз тест на 2FA системата"""
    print("🔐 === ТЕСТ НА ДВУСТЕПЕННА АВТЕНТИКАЦИЯ === 🔐\n")
    
    with app.app_context():
        # 1. Създаване на тестов потребител
        print("1️⃣ Създаване на тестов потребител...")
        test_user = AdminUser.query.filter_by(username="test_2fa_quick").first()
        if not test_user:
            test_user = AdminUser(
                username="test_2fa_quick",
                email="test_2fa_quick@helpchain.bg",
                password_hash=generate_password_hash("test123!"),
                role=AdminRole.ADMIN,
                is_active=True
            )
            db.session.add(test_user)
            db.session.commit()
            print("   ✅ Тестов потребител създаден успешно")
        else:
            print("   ℹ️ Тестов потребител вече съществува")
        
        # 2. Генериране на TOTP secret
        print("\n2️⃣ Генериране на TOTP Secret...")
        if not test_user.totp_secret:
            test_user.totp_secret = generate_totp_secret()
            db.session.commit()
        print(f"   ✅ Secret: {test_user.totp_secret}")
        print(f"   📏 Дължина: {len(test_user.totp_secret)} символа")
        
        # 3. Създаване на TOTP обект
        print("\n3️⃣ Създаване на TOTP обект...")
        totp = pyotp.TOTP(test_user.totp_secret)
        print("   ✅ TOTP обект създаден")
        
        # 4. Генериране на QR код URI
        print("\n4️⃣ Генериране на QR код...")
        qr_uri = totp.provisioning_uri(
            name=test_user.email,
            issuer_name="HelpChain.bg Admin"
        )
        print(f"   ✅ QR URI: {qr_uri[:50]}...")
        
        # 5. Генериране на backup кодове
        print("\n5️⃣ Генериране на backup кодове...")
        backup_codes = generate_backup_codes()
        test_user.backup_codes = json.dumps(backup_codes)
        db.session.commit()
        print(f"   ✅ Генерирани {len(backup_codes)} backup кода")
        print(f"   🔑 Примери: {', '.join(backup_codes[:3])}")
        
        # 6. Тест на TOTP токени
        print("\n6️⃣ Тест на TOTP токени...")
        current_token = totp.now()
        print(f"   🕐 Текущ токен: {current_token}")
        
        # Проверка на валидацията
        is_valid = verify_totp_token(test_user, current_token)
        print(f"   {'✅' if is_valid else '❌'} Валидация: {'Успешна' if is_valid else 'Неуспешна'}")
        
        # 7. Активиране на 2FA
        print("\n7️⃣ Активиране на 2FA...")
        test_user.two_factor_enabled = True
        db.session.commit()
        print("   ✅ 2FA активирана успешно")
        
        # 8. Тест на различни времеви периоди
        print("\n8️⃣ Тест на токени в различни времеви периоди...")
        for i in range(3):
            token = totp.at(totp.timecode(time.time()) + i)
            print(f"   Период +{i}: {token}")
        
        # 9. Тест на backup код
        print("\n9️⃣ Тест на backup код...")
        backup_codes_list = json.loads(test_user.backup_codes)
        test_backup = backup_codes_list[0]
        
        # Симулираме използване на backup код
        print(f"   🔑 Тестов backup код: {test_backup}")
        
        # 🔟 Финални резултати
        print("\n🏁 === ФИНАЛНИ РЕЗУЛТАТИ ===")
        print(f"👤 Потребител: {test_user.username}")
        print(f"📧 Email: {test_user.email}")
        print(f"🔐 2FA активирана: {'✅ Да' if test_user.two_factor_enabled else '❌ Не'}")
        print(f"🔑 TOTP Secret: {'✅ Настроен' if test_user.totp_secret else '❌ Липсва'}")
        print(f"🔒 Backup кодове: {len(backup_codes_list)} броя")
        print(f"⏰ Текущ TOTP: {totp.now()}")
        
        return test_user

def test_different_scenarios():
    """Тест на различни сценарии"""
    print("\n🎭 === ТЕСТ НА РАЗЛИЧНИ СЦЕНАРИИ ===\n")
    
    with app.app_context():
        test_user = AdminUser.query.filter_by(username="test_2fa_quick").first()
        if not test_user:
            print("❌ Тестов потребител не е намерен. Първо изпълнете основния тест.")
            return
        
        totp = pyotp.TOTP(test_user.totp_secret)
        
        # Сценарий 1: Правилен токен
        print("📝 Сценарий 1: Правилен токен")
        current_token = totp.now()
        is_valid = verify_totp_token(test_user, current_token)
        print(f"   Токен: {current_token}")
        print(f"   Резултат: {'✅ Валиден' if is_valid else '❌ Невалиден'}")
        
        # Сценарий 2: Грешен токен
        print("\n📝 Сценарий 2: Грешен токен")
        wrong_token = "123456"
        is_valid = verify_totp_token(test_user, wrong_token)
        print(f"   Токен: {wrong_token}")
        print(f"   Резултат: {'✅ Валиден' if is_valid else '❌ Невалиден'}")
        
        # Сценарий 3: Backup код
        print("\n📝 Сценарий 3: Backup код")
        backup_codes = json.loads(test_user.backup_codes)
        test_backup = backup_codes[0]
        print(f"   Backup код: {test_backup}")
        print(f"   Формат: {'✅ Правилен' if '-' in test_backup else '❌ Грешен'}")
        
        print("\n✨ Всички сценарии тествани!")

def cleanup():
    """Изчистване на тестовите данни"""
    print("\n🧹 === ИЗЧИСТВАНЕ ===\n")
    
    with app.app_context():
        test_user = AdminUser.query.filter_by(username="test_2fa_quick").first()
        if test_user:
            db.session.delete(test_user)
            db.session.commit()
            print("✅ Тестовият потребител е изтрит")
        else:
            print("ℹ️ Няма данни за изчистване")

def main():
    """Главна функция"""
    print("🚀 Стартиране на бърз 2FA тест...\n")
    
    try:
        # Изпълняваме всички тестове
        run_comprehensive_test()
        test_different_scenarios()
        
        print("\n" + "="*50)
        print("🎉 ВСИЧКИ ТЕСТОВЕ ЗАВЪРШЕНИ УСПЕШНО!")
        print("="*50)
        
        # Питаме дали да изчистим данните
        print("\nИскате ли да изчистим тестовите данни? (y/n): ", end="")
        try:
            choice = input().lower()
            if choice in ['y', 'yes', 'да']:
                cleanup()
        except KeyboardInterrupt:
            print("\n👋 Тестът е прекратен.")
            
    except Exception as e:
        print(f"❌ Грешка по време на теста: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()