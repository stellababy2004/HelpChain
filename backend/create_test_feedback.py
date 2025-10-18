#!/usr/bin/env python3
"""
Create test feedback data for sentiment analysis testing
"""

import os
import sys

# Add backend directory to path
backend_dir = os.path.dirname(__file__)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Import Flask app
import random
from datetime import datetime, timedelta

from appy import app
from extensions import db
from models_with_analytics import Feedback


def create_test_feedback():
    """Create test feedback data"""

    # Create some test feedback data
    test_feedbacks = [
        {
            "name": "Мария Иванова",
            "email": "maria@example.com",
            "message": "Отлично приложение! Много ми помогнахте с намирането на доброволец.",
            "user_type": "user",
        },
        {
            "name": "Георги Петров",
            "email": "georgi@example.com",
            "message": "Благодаря за бързата помощ. Всичко работи перфектно!",
            "user_type": "user",
        },
        {
            "name": "Анна Димитрова",
            "email": "anna@example.com",
            "message": "Имаше малък проблем с регистрацията, но иначе е добро.",
            "user_type": "user",
        },
        {
            "name": "Иван Стоянов",
            "email": "ivan@example.com",
            "message": "Не съм доволен от услугата. Твърде бавно отговарят.",
            "user_type": "user",
        },
        {
            "name": "Петър Василев",
            "email": "petar@example.com",
            "message": "Страхотно! Ще го препоръчам на приятелите си.",
            "user_type": "user",
        },
        {
            "name": "Светлана Николова",
            "email": "svetlana@example.com",
            "message": "Има много грешки в приложението. Трябва да се оправи.",
            "user_type": "user",
        },
        {
            "name": "Димитър Ангелов",
            "email": "dimitar@example.com",
            "message": "Добре свършихте работата. Благодаря!",
            "user_type": "user",
        },
        {
            "name": "Елена Колева",
            "email": "elena@example.com",
            "message": "Нормално приложение, нищо особено.",
            "user_type": "user",
        },
    ]

    with app.app_context():
        with db.session.begin():
            for fb_data in test_feedbacks:
                # Random timestamp within last 30 days
                days_ago = random.randint(0, 30)
                timestamp = datetime.utcnow() - timedelta(days=days_ago)

                feedback = Feedback(
                    name=fb_data["name"],
                    email=fb_data["email"],
                    message=fb_data["message"],
                    user_type=fb_data["user_type"],
                    timestamp=timestamp,
                )
                db.session.add(feedback)

        print("Test feedback data created successfully!")


if __name__ == "__main__":
    create_test_feedback()
