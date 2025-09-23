#!/usr/bin/env python3
"""
Скрипт за инициализация на новата система за сигурност
Създава таблиците и първия super admin потребител
"""

import sys
import os
from pathlib import Path

# Добавяме backend директорията в Python path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from appy import app, db
from models import AdminUser, AdminRole
from werkzeug.security import generate_password_hash
from datetime import datetime


def init_security_tables():
    """Създава новите таблици за сигурност"""
    with app.app_context():
        print("Създаване на нови таблици за сигурност...")
        try:
            # Създаваме всички таблици
            db.create_all()
            print("✅ Таблиците са създадени успешно!")
            return True
        except Exception as e:
            print(f"❌ Грешка при създаване на таблици: {e}")
            return False


def create_super_admin():
    """Създава първия super admin потребител"""
    with app.app_context():
        print("\nСъздаване на super admin потребител...")
        
        # Проверяваме дали вече има super admin
        existing_admin = AdminUser.query.filter_by(role=AdminRole.SUPER_ADMIN).first()
        if existing_admin:
            print(f"✅ Super admin потребителят '{existing_admin.username}' вече съществува.")
            return True
        
        # Вземаме данните от .env файла или въвеждаме ръчно
        from dotenv import load_dotenv
        load_dotenv()
        
        username = os.getenv('ADMIN_USERNAME', 'admin')
        password = os.getenv('ADMIN_PASSWORD')
        
        if not password:
            print("❌ Няма парола в .env файла. Моля въведете парола:")
            password = input("Парола за super admin: ")
        
        email = input(f"Email за admin потребител '{username}' (default: admin@helpchain.bg): ").strip()
        if not email:
            email = "admin@helpchain.bg"
        
        try:
            super_admin = AdminUser(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                role=AdminRole.SUPER_ADMIN,
                is_active=True,
                created_at=datetime.utcnow()
            )
            
            db.session.add(super_admin)
            db.session.commit()
            
            print(f"✅ Super admin потребителят '{username}' е създаден успешно!")
            print(f"   Email: {email}")
            print(f"   Роля: {AdminRole.SUPER_ADMIN.value}")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Грешка при създаване на super admin: {e}")
            return False


def main():
    """Главна функция"""
    print("🔐 Инициализация на система за сигурност HelpChain.bg")
    print("=" * 50)
    
    # Създаваме таблиците
    if not init_security_tables():
        print("❌ Неуспешна инициализация.")
        return False
    
    # Създаваме super admin
    if not create_super_admin():
        print("❌ Неуспешно създаване на super admin.")
        return False
    
    print("\n🎉 Системата за сигурност е инициализирана успешно!")
    print("\nТова, което можете да правите сега:")
    print("1. Логнете се с новия admin акаунт")
    print("2. Активирайте 2FA за допълнителна сигурност")
    print("3. Създайте други admin потребители с различни роли")
    print("4. Прегледайте логовете на административни действия")
    
    return True


if __name__ == "__main__":
    if main():
        sys.exit(0)
    else:
        sys.exit(1)