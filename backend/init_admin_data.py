#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт за инициализиране на админ потребители и тестови логове
"""

import sys
import os
from datetime import datetime, timedelta

# Добавяме backend директорията към path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.appy import app, db
    from backend.models import AdminUser, AdminRole, AdminLog, HelpRequest
    from werkzeug.security import generate_password_hash
except ImportError as e:
    from appy import app, db
    from models import AdminUser, AdminRole, AdminLog, HelpRequest
    from werkzeug.security import generate_password_hash

def create_admin_users():
    """Създава основни админ потребители"""
    print("Създаване на админ потребители...")
    
    # Super Admin
    super_admin = AdminUser.query.filter_by(username="admin").first()
    if not super_admin:
        super_admin = AdminUser(
            username="admin",
            email="admin@helpchain.bg",
            password_hash=generate_password_hash(os.getenv("ADMIN_PASSWORD", "defaultAdminPass123")),
            role=AdminRole.SUPER_ADMIN,
            is_active=True
        )
        db.session.add(super_admin)
        print("✓ Създаден Super Admin: admin")
    else:
        print("Super Admin 'admin' вече съществува")
    
    # Regular Admin
    admin = AdminUser.query.filter_by(username="moderator").first()
    if not admin:
        admin = AdminUser(
            username="moderator",
            email="moderator@helpchain.bg", 
            password_hash=generate_password_hash("mod2025!"),
            role=AdminRole.ADMIN,
            is_active=True
        )
        db.session.add(admin)
        print("✓ Създаден Admin: moderator")
    else:
        print("Admin 'moderator' вече съществува")
    
    # Moderator
    moderator = AdminUser.query.filter_by(username="helper").first()
    if not moderator:
        moderator = AdminUser(
            username="helper",
            email="helper@helpchain.bg",
            password_hash=generate_password_hash("helper2025!"),
            role=AdminRole.MODERATOR,
            is_active=True
        )
        db.session.add(moderator)
        print("✓ Създаден Moderator: helper")
    else:
        print("Moderator 'helper' вече съществува")
    
    db.session.commit()
    print("Всички админ потребители са готови!\n")

def create_test_logs():
    """Създава тестови логове за демонстрация"""
    print("Създаване на тестови логове...")
    
    # Вземаме админ потребителите
    super_admin = AdminUser.query.filter_by(username="admin").first()
    admin = AdminUser.query.filter_by(username="moderator").first()
    moderator = AdminUser.query.filter_by(username="helper").first()
    
    if not super_admin or not admin or not moderator:
        print("Грешка: Не са намерени админ потребители!")
        return
    
    # Създаваме тестова заявка за помощ
    test_request = HelpRequest.query.first()
    if not test_request:
        test_request = HelpRequest(
            title="Тестова заявка за демо",
            name="Иван Иванов",
            email="ivan@example.com",
            phone="0888123456",
            message="Нуждая се от помощ за демонстрация на системата",
            description="Тестово описание",
            status="Pending"
        )
        db.session.add(test_request)
        db.session.commit()
    
    # Създаваме различни типове логове с различни времена
    base_time = datetime.utcnow() - timedelta(days=7)
    
    test_logs = [
        {
            "admin_user": super_admin,
            "action": "login",
            "details": {"username": "admin"},
            "timestamp": base_time
        },
        {
            "admin_user": super_admin,
            "action": "approved_request",
            "details": {
                "request_id": test_request.id,
                "request_title": test_request.title,
                "old_status": "Pending",
                "new_status": "Активен",
                "requester_name": test_request.name,
                "requester_email": test_request.email
            },
            "entity_type": "help_request",
            "entity_id": test_request.id,
            "timestamp": base_time + timedelta(hours=1)
        },
        {
            "admin_user": admin,
            "action": "login",
            "details": {"username": "moderator"},
            "timestamp": base_time + timedelta(days=1)
        },
        {
            "admin_user": admin,
            "action": "added_volunteer",
            "details": {
                "volunteer_name": "Мария Петрова",
                "volunteer_email": "maria@example.com",
                "volunteer_phone": "0887654321",
                "volunteer_location": "София"
            },
            "entity_type": "volunteer",
            "entity_id": 1,
            "timestamp": base_time + timedelta(days=1, hours=2)
        },
        {
            "admin_user": moderator,
            "action": "login",
            "details": {"username": "helper"},
            "timestamp": base_time + timedelta(days=2)
        },
        {
            "admin_user": moderator,
            "action": "rejected_request",
            "details": {
                "request_id": test_request.id,
                "request_title": "Друга тестова заявка",
                "old_status": "Pending",
                "new_status": "Отхвърлена",
                "requester_name": "Георги Георгиев",
                "requester_email": "georgi@example.com"
            },
            "entity_type": "help_request",
            "entity_id": test_request.id,
            "timestamp": base_time + timedelta(days=2, hours=3)
        },
        {
            "admin_user": super_admin,
            "action": "added_news",
            "details": {
                "news_title": "Нова успешна история",
                "news_content": "Благодарение на HelpChain успяхме да помогнем на много хора..."
            },
            "entity_type": "success_story",
            "entity_id": 1,
            "timestamp": base_time + timedelta(days=3)
        },
        {
            "admin_user": admin,
            "action": "edited_volunteer",
            "details": {
                "volunteer_id": 1,
                "old_data": {"name": "Мария Петрова", "location": "София"},
                "new_data": {"name": "Мария Петрова-Стоянова", "location": "Пловдив"}
            },
            "entity_type": "volunteer",
            "entity_id": 1,
            "timestamp": base_time + timedelta(days=4)
        },
        {
            "admin_user": super_admin,
            "action": "deleted_volunteer",
            "details": {
                "volunteer_id": 2,
                "volunteer_data": {
                    "name": "Петър Петров",
                    "email": "peter@example.com",
                    "phone": "0889123456",
                    "location": "Варна"
                }
            },
            "entity_type": "volunteer",
            "entity_id": 2,
            "timestamp": base_time + timedelta(days=5)
        }
    ]
    
    # Добавяме логовете в базата данни
    for log_data in test_logs:
        existing_log = AdminLog.query.filter_by(
            admin_user_id=log_data["admin_user"].id,
            action=log_data["action"],
            timestamp=log_data["timestamp"]
        ).first()
        
        if not existing_log:
            import json
            log_entry = AdminLog(
                admin_user_id=log_data["admin_user"].id,
                action=log_data["action"],
                details=json.dumps(log_data["details"]) if log_data.get("details") else None,
                entity_type=log_data.get("entity_type"),
                entity_id=log_data.get("entity_id"),
                ip_address="127.0.0.1",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                timestamp=log_data["timestamp"]
            )
            db.session.add(log_entry)
    
    db.session.commit()
    print("✓ Тестови логове са създадени успешно!\n")

def main():
    """Главна функция"""
    print("=== Инициализиране на админ потребители и логове ===\n")
    
    with app.app_context():
        # Създаваме таблиците ако не съществуват
        db.create_all()
        
        # Създаваме админ потребители
        create_admin_users()
        
        # Създаваме тестови логове
        create_test_logs()
        
        # Показваме статистика
        admin_count = AdminUser.query.count()
        log_count = AdminLog.query.count()
        
        print("=== Резултат ===")
        print(f"Админ потребители в системата: {admin_count}")
        print(f"Логове в системата: {log_count}")
        print("\n✅ Инициализацията завърши успешно!")
        print("\nМожете да влезете в админ панела с:")
        print("- Super Admin: admin / [вашата парола]")
        print("- Admin: moderator / mod2025!")
        print("- Moderator: helper / helper2025!")

if __name__ == "__main__":
    main()