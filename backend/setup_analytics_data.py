#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт за добавяне на тестови данни за analytics dashboard
"""

import sys
import os
from datetime import datetime, timedelta
import random

# Добавяме backend директорията към path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.appy import app, db
    from backend.models import HelpRequest, Volunteer, AdminLog
except ImportError as e:
    from appy import app, db
    from models import HelpRequest, Volunteer, AdminLog

def add_sample_data():
    """Добавя примерни данни за тестване"""
    print("🔄 Добавяне на тестови данни...")
    
    with app.app_context():
        # Изчистваме съществуващите данни
        HelpRequest.query.delete()
        Volunteer.query.delete()
        
        # Категории и статуси
        categories = ['здраве', 'документи', 'социална помощ', 'транспорт', 'образование', 'друго']
        statuses = ['Pending', 'Активен', 'Завършена', 'Отхвърлена']
        bulgarian_cities = [
            'София', 'Пловдив', 'Варна', 'Бургас', 'Русе', 
            'Стара Загора', 'Плевен', 'Сливен', 'Добрич', 'Шумен'
        ]
        
        # Добавяме заявки за помощ
        help_requests_data = [
            {
                'name': 'Мария Иванова',
                'email': 'maria@example.com',
                'phone': '0888123456',
                'title': 'Нужда от медицинска помощ',
                'description': 'Необходима е помощ за придружаване до болница за лечение',
                'message': 'Възрастна жена се нуждае от помощ за транспорт до болница',
                'status': 'Активен'
            },
            {
                'name': 'Георги Петров',
                'email': 'georgi@example.com',
                'phone': '0887654321',
                'title': 'Документи за пенсия',
                'description': 'Помощ за попълване на документи за пенсиониране',
                'message': 'Нужна е помощ с документи за НОИ',
                'status': 'Pending'
            },
            {
                'name': 'Елена Стоянова',
                'email': 'elena@example.com',
                'phone': '0889987654',
                'title': 'Хранителни продукти',
                'description': 'Семейство се нуждае от хранителни продукти',
                'message': 'Молим за помощ с хранителни продукти за семейство с деца',
                'status': 'Завършена'
            },
            {
                'name': 'Иван Димитров',
                'email': 'ivan@example.com',
                'phone': '0886112233',
                'title': 'Ремонт на покрив',
                'description': 'Нужна е помощ за ремонт на покрив',
                'message': 'Стар човек се нуждае от помощ за ремонт',
                'status': 'Активен'
            },
            {
                'name': 'Анна Георгиева',
                'email': 'anna@example.com',
                'phone': '0885445566',
                'title': 'Превоз до училище',
                'description': 'Дете се нуждае от превоз до училище',
                'message': 'Родител търси помощ за превоз на дете',
                'status': 'Отхвърлена'
            }
        ]
        
        # Добавяме основните заявки
        for req_data in help_requests_data:
            req = HelpRequest(
                name=req_data['name'],
                email=req_data['email'],
                phone=req_data['phone'],
                title=req_data['title'],
                description=req_data['description'],
                message=req_data['message'],
                status=req_data['status'],
                created_at=datetime.now() - timedelta(days=random.randint(0, 30))
            )
            db.session.add(req)
        
        # Добавяме още 20 произволни заявки
        names = ['Петър', 'Мария', 'Иван', 'Елена', 'Георги', 'Стефан', 'Анна', 'Димитър', 'Надежда', 'Васил']
        surnames = ['Иванов', 'Петров', 'Стоянов', 'Димитров', 'Георгиев', 'Николов', 'Христов', 'Тодоров']
        
        for i in range(20):
            name = random.choice(names) + ' ' + random.choice(surnames)
            req = HelpRequest(
                name=name,
                email=f"test{i}@example.com",
                phone=f"088{random.randint(1000000, 9999999)}",
                title=f"Заявка за помощ #{i+6}",
                description=f"Описание на заявка {i+6} от категория {random.choice(categories)}",
                message=f"Съобщение за заявка {i+6}",
                status=random.choice(statuses),
                created_at=datetime.now() - timedelta(days=random.randint(0, 60))
            )
            db.session.add(req)
        
        # Добавяме доброволци
        volunteers_data = [
            {
                'name': 'Александър Александров',
                'email': 'alex@volunteer.bg',
                'phone': '0888111222',
                'location': 'София'
            },
            {
                'name': 'Мария Маринова',
                'email': 'maria@volunteer.bg',
                'phone': '0887333444',
                'location': 'Пловдив'
            },
            {
                'name': 'Стефан Стефанов',
                'email': 'stefan@volunteer.bg',
                'phone': '0886555666',
                'location': 'Варна'
            },
            {
                'name': 'Елена Енева',
                'email': 'elena@volunteer.bg',
                'phone': '0885777888',
                'location': 'Бургас'
            },
            {
                'name': 'Иван Иванов',
                'email': 'ivan@volunteer.bg',
                'phone': '0884999000',
                'location': 'София'
            }
        ]
        
        for vol_data in volunteers_data:
            vol = Volunteer(
                name=vol_data['name'],
                email=vol_data['email'],
                phone=vol_data['phone'],
                location=vol_data['location']
            )
            db.session.add(vol)
        
        # Добавяме още 15 произволни доброволци
        for i in range(15):
            vol = Volunteer(
                name=f"{random.choice(names)} {random.choice(surnames)}",
                email=f"volunteer{i}@example.com",
                phone=f"088{random.randint(1000000, 9999999)}",
                location=random.choice(bulgarian_cities)
            )
            db.session.add(vol)
        
        # Запазваме промените
        db.session.commit()
        
        # Статистики
        total_requests = HelpRequest.query.count()
        total_volunteers = Volunteer.query.count()
        
        print(f"✅ Добавени данни:")
        print(f"   📋 Заявки: {total_requests}")
        print(f"   👥 Доброволци: {total_volunteers}")
        print(f"   📍 Градове: {len(set(vol.location for vol in Volunteer.query.all() if vol.location))}")
        
        # Статистики по статуси
        status_counts = {}
        for status in statuses:
            count = HelpRequest.query.filter_by(status=status).count()
            if count > 0:
                status_counts[status] = count
        
        print(f"   📊 Статуси: {status_counts}")
        
        return True

def add_demo_analytics_data():
    """Добавя данни специално за демонстрация на analytics"""
    print("📊 Добавяне на данни за analytics демонстрация...")
    
    with app.app_context():
        # Добавяме заявки за последните 30 дни с различна интензивност
        today = datetime.now().date()
        
        for day_offset in range(30):
            date = today - timedelta(days=day_offset)
            
            # Различна интензивност по дни
            if day_offset < 7:  # Последната седмица - много активност
                requests_count = random.randint(2, 5)
            elif day_offset < 14:  # Преди 2 седмици - средна активност
                requests_count = random.randint(1, 3)
            else:  # По-стари - малка активност
                requests_count = random.randint(0, 2)
            
            for _ in range(requests_count):
                req = HelpRequest(
                    name=f"Потребител {day_offset}-{_}",
                    email=f"user{day_offset}{_}@example.com",
                    phone=f"088{random.randint(1000000, 9999999)}",
                    title=f"Заявка от {date.strftime('%d.%m.%Y')}",
                    description=f"Описание на заявка от {date}",
                    message=f"Съобщение от {date}",
                    status=random.choice(['Pending', 'Активен', 'Завършена', 'Отхвърлена']),
                    created_at=datetime.combine(date, datetime.min.time()) + timedelta(
                        hours=random.randint(8, 18),
                        minutes=random.randint(0, 59)
                    )
                )
                db.session.add(req)
        
        db.session.commit()
        print("✅ Analytics данни добавени успешно!")

if __name__ == "__main__":
    print("🚀 Инициализация на тестови данни за HelpChain Analytics Dashboard")
    print("=" * 70)
    
    try:
        # Добавяме основни данни
        if add_sample_data():
            # Добавяме analytics данни
            add_demo_analytics_data()
            
            print("\n🎉 Всички тестови данни са добавени успешно!")
            print("\n📋 Може да отворите analytics dashboard на:")
            print("   🔗 http://127.0.0.1:5000/admin/analytics")
            print("\n🔐 Логин данни:")
            print("   👤 Username: admin")
            print("   🔑 Password: help2025!")
            
    except Exception as e:
        print(f"❌ Грешка при добавяне на данни: {e}")
        import traceback
        traceback.print_exc()