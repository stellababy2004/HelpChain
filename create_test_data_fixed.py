#!/usr/bin/env python3
"""
Script to add test data to the HelpChain database for admin panel testing.
"""

import os
import random
import sys
from datetime import datetime, timedelta

# Add the backend directory to Python path
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Set up Flask app context
os.environ["FLASK_APP"] = "backend.appy"
os.environ["FLASK_ENV"] = "development"

from appy import app, db
from models import AdminUser, HelpRequest, Volunteer


def create_test_volunteers():
    """Create test volunteers"""
    volunteers_data = [
        {
            "name": "Иван Петров",
            "email": "ivan@example.com",
            "phone": "+359 88 123 4567",
            "skills": "Програмиране, IT поддръжка, английски език",
            "location": "София",
            "latitude": 42.6977,
            "longitude": 23.3219,
        },
        {
            "name": "Мария Димитрова",
            "email": "maria@example.com",
            "phone": "+359 87 234 5678",
            "skills": "Преподаване, детска психология, рисуване",
            "location": "Пловдив",
            "latitude": 42.1354,
            "longitude": 24.7453,
        },
        {
            "name": "Георги Иванов",
            "email": "georgi@example.com",
            "phone": "+359 89 345 6789",
            "skills": "Медицинска помощ, първа помощ, шофиране",
            "location": "Варна",
            "latitude": 43.2141,
            "longitude": 27.9147,
        },
        {
            "name": "Анна Стоянова",
            "email": "anna@example.com",
            "phone": "+359 88 456 7890",
            "skills": "Организация на събития, доброволческа координация",
            "location": "Бургас",
            "latitude": 42.5048,
            "longitude": 27.4626,
        },
        {
            "name": "Димитър Колев",
            "email": "dimitar@example.com",
            "phone": "+359 87 567 8901",
            "skills": "Строителство, ремонтни работи, електротехника",
            "location": "Русе",
            "latitude": 43.8486,
            "longitude": 25.9543,
        },
    ]

    volunteers = []
    for data in volunteers_data:
        volunteer = Volunteer(**data)
        db.session.add(volunteer)
        volunteers.append(volunteer)

    db.session.commit()
    print(f"Created {len(volunteers)} test volunteers")
    return volunteers


def create_test_help_requests():
    """Create test help requests"""
    requests_data = [
        {
            "title": "Помощ с пазаруване",
            "description": "Възрастна жена има нужда от помощ с пазаруване на хранителни продукти. Не може да излиза сама.",
            "status": "pending",
            "name": "Елена Петрова",
            "email": "elena@example.com",
            "phone": "+359 88 111 2222",
            "message": "Здравейте, аз съм 75 годишна жена и имам проблеми с придвижването. Имам нужда от доброволец който да ми помогне с пазаруването веднъж седмично.",
            "latitude": 42.6977,
            "longitude": 23.3219,
        },
        {
            "title": "Онлайн обучение",
            "description": "Студент има нужда от помощ с онлайн обучение и домашни.",
            "status": "approved",
            "name": "Александър Димов",
            "email": "alex@example.com",
            "phone": "+359 87 333 4444",
            "message": "Здравейте, аз съм ученик в 10 клас и имам затруднения с математиката и английския език. Търся доброволец който да ми помага с уроците.",
            "latitude": 42.1354,
            "longitude": 24.7453,
        },
        {
            "title": "Медицинска консултация",
            "description": "Човек има нужда от придружител до лекар.",
            "status": "completed",
            "name": "Борис Николов",
            "email": "boris@example.com",
            "phone": "+359 89 555 6666",
            "message": "Имам нужда от доброволец който да ме придружи до болница за преглед. Не мога да шофирам.",
            "latitude": 43.2141,
            "longitude": 27.9147,
        },
        {
            "title": "Помощ с домакинство",
            "description": "Семейство има нужда от помощ с почистване и подреждане.",
            "status": "pending",
            "name": "Семейство Иванови",
            "email": "family@example.com",
            "phone": "+359 88 777 8888",
            "message": "Здравейте, ние сме многодетно семейство и имаме нужда от помощ с почистването на дома. Особено през уикендите.",
            "latitude": 42.5048,
            "longitude": 27.4626,
        },
        {
            "title": "Компютърна помощ",
            "description": "Възрастен човек има нужда от помощ с компютър.",
            "status": "approved",
            "name": "Васил Георгиев",
            "email": "vasil@example.com",
            "phone": "+359 87 999 0000",
            "message": "Не мога да се справя с интернет банкирането и електронната поща. Търся доброволец който да ми покаже как да използвам компютъра.",
            "latitude": 43.8486,
            "longitude": 25.9543,
        },
    ]

    requests = []
    for data in requests_data:
        # Add some random created_at dates
        days_ago = random.randint(0, 30)
        data["created_at"] = datetime.utcnow() - timedelta(days=days_ago)

        request = HelpRequest(**data)
        db.session.add(request)
        requests.append(request)

    db.session.commit()
    print(f"Created {len(requests)} test help requests")
    return requests


def main():
    """Main function to create test data"""
    print("Starting test data creation...")

    with app.app_context():
        try:
            # Create tables if they don't exist
            db.create_all()
            print("Database tables created/verified")

            # Create test volunteers
            volunteers = create_test_volunteers()

            # Create test help requests
            requests = create_test_help_requests()

            print("\nTest data created successfully!")
            print(f"- {len(volunteers)} volunteers")
            print(f"- {len(requests)} help requests")

            # Print summary
            print("\nData Summary:")
            print("Volunteers:")
            for v in volunteers:
                print(f"  - {v.name} ({v.email}) - {v.location}")

            print("\nHelp Requests:")
            for r in requests:
                print(f"  - {r.title} - {r.status} - {r.name}")

        except Exception as e:
            print(f"Error creating test data: {e}")
            db.session.rollback()
            raise


if __name__ == "__main__":
    main()
