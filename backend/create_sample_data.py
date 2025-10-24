#!/usr/bin/env python3
"""
Sample Data Generator for HelpChain Application
Adds realistic sample data for testing and demonstration purposes
"""

import json
import os
import sys
import random
from datetime import datetime, timedelta
from faker import Faker

# Add backend directory to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Import Flask app and models
from appy import app, db
from models import (
    Volunteer, HelpRequest, User, Role, Permission,
    ChatRoom, ChatMessage, ChatParticipant,
    Notification, UserActivity
)
from models_with_analytics import (
    Task, TaskAssignment, TaskPerformance,
    AdminLog, ChatbotConversation, Feedback, SuccessStory, AnalyticsEvent
)

# Initialize Faker for generating realistic data
fake = Faker('bg_BG')  # Bulgarian locale

def create_sample_volunteers(count=20):
    """Create sample volunteers with realistic data"""
    print(f"Creating {count} sample volunteers...")

    volunteers_data = [
        {
            "name": "Мария Иванова",
            "email": "maria.ivanova@email.com",
            "phone": "+359 88 123 4567",
            "location": "София",
            "skills": "Първа помощ, Готовка, Превод",
            "points": 450,
            "level": 3,
            "experience": 180,
            "total_tasks_completed": 12,
            "total_hours_volunteered": 45.5,
            "rating": 4.8,
            "rating_count": 8,
            "streak_days": 15
        },
        {
            "name": "Георги Петров",
            "email": "georgi.petrov@email.com",
            "phone": "+359 87 234 5678",
            "location": "Пловдив",
            "skills": "Транспорт, Ремонт, Електроника",
            "points": 320,
            "level": 2,
            "experience": 120,
            "total_tasks_completed": 8,
            "total_hours_volunteered": 32.0,
            "rating": 4.6,
            "rating_count": 6,
            "streak_days": 8
        },
        {
            "name": "Анна Димитрова",
            "email": "anna.dimitrova@email.com",
            "phone": "+359 89 345 6789",
            "location": "Варна",
            "skills": "Образование, Детска грижа, Психология",
            "points": 680,
            "level": 4,
            "experience": 280,
            "total_tasks_completed": 18,
            "total_hours_volunteered": 72.5,
            "rating": 4.9,
            "rating_count": 12,
            "streak_days": 22
        },
        {
            "name": "Иван Стоянов",
            "email": "ivan.stoyanov@email.com",
            "phone": "+359 88 456 7890",
            "location": "Бургас",
            "skills": "Строителство, Градинарство, Животновъдство",
            "points": 290,
            "level": 2,
            "experience": 90,
            "total_tasks_completed": 6,
            "total_hours_volunteered": 28.0,
            "rating": 4.4,
            "rating_count": 5,
            "streak_days": 5
        },
        {
            "name": "Елена Николова",
            "email": "elena.nikolova@email.com",
            "phone": "+359 87 567 8901",
            "location": "Русе",
            "skills": "Медицинска помощ, Фармация, Здравеопазване",
            "points": 550,
            "level": 3,
            "experience": 200,
            "total_tasks_completed": 15,
            "total_hours_volunteered": 58.5,
            "rating": 4.7,
            "rating_count": 10,
            "streak_days": 18
        }
    ]

    # Add the predefined volunteers
    for volunteer_data in volunteers_data:
        volunteer = Volunteer(**volunteer_data)
        db.session.add(volunteer)

    # Generate additional random volunteers
    locations = ["София", "Пловдив", "Варна", "Бургас", "Русе", "Стара Загора", "Плевен", "Добрич", "Сливен", "Шумен"]
    skills_list = [
        "Първа помощ", "Готовка", "Превод", "Транспорт", "Ремонт", "Електроника",
        "Образование", "Детска грижа", "Психология", "Строителство", "Градинарство",
        "Животновъдство", "Медицинска помощ", "Фармация", "Здравеопазване", "ИТ поддръжка",
        "Социална работа", "Организация на събития", "Фотография", "Видео монтаж"
    ]

    for i in range(len(volunteers_data), count):
        name = fake.name()
        email = fake.email()
        phone = fake.phone_number()
        location = random.choice(locations)
        num_skills = random.randint(1, 4)
        skills = ", ".join(random.sample(skills_list, num_skills))

        # Generate realistic gamification stats
        level = random.randint(1, 5)
        experience = level * 100 + random.randint(0, 99)
        points = experience + random.randint(0, 50)
        total_tasks = random.randint(level * 2, level * 4)
        total_hours = total_tasks * random.uniform(2, 8)
        rating = round(random.uniform(3.5, 5.0), 1)
        rating_count = random.randint(1, total_tasks)
        streak_days = random.randint(0, 30)

        volunteer = Volunteer(
            name=name,
            email=email,
            phone=phone,
            location=location,
            skills=skills,
            points=points,
            level=level,
            experience=experience,
            total_tasks_completed=total_tasks,
            total_hours_volunteered=round(total_hours, 1),
            rating=rating,
            rating_count=rating_count,
            streak_days=streak_days
        )
        db.session.add(volunteer)

    db.session.commit()
    print(f"✅ Created {count} sample volunteers")


def create_sample_help_requests(count=15):
    """Create sample help requests"""
    print(f"Creating {count} sample help requests...")

    categories = ["Здравеопазване", "Образование", "Социална помощ", "Битови нужди", "Транспорт", "Техническа помощ"]
    statuses = ["pending", "approved", "assigned", "completed"]
    priorities = ["low", "normal", "urgent"]

    # Predefined requests for realism
    requests_data = [
        {
            "name": "Петър Димитров",
            "email": "petar.dimitrov@email.com",
            "title": "Здравеопазване",
            "message": "Нуждая се от помощ за придружаване до болница за преглед. Имам затруднения с придвижването.",
            "status": "pending",
            "priority": "urgent"
        },
        {
            "name": "Мария Георгиева",
            "email": "maria.georgieva@email.com",
            "title": "Образование",
            "message": "Търся доброволец, който да помогне на детето ми с домашните по математика.",
            "status": "approved",
            "priority": "normal"
        },
        {
            "name": "Иван Стоев",
            "email": "ivan.stoev@email.com",
            "title": "Битови нужди",
            "message": "Нуждая се от помощ за пазаруване и почистване на дома. Имам ограничена подвижност.",
            "status": "assigned",
            "priority": "normal"
        }
    ]

    # Add predefined requests
    for request_data in requests_data:
        help_request = HelpRequest(**request_data)
        help_request.description = request_data.get("message", "")  # Set description from message
        db.session.add(help_request)

    # Generate additional random requests
    for i in range(len(requests_data), count):
        name = fake.name()
        email = fake.email()
        category = random.choice(categories)
        status = random.choice(statuses)
        priority = random.choices(priorities, weights=[0.3, 0.6, 0.1])[0]  # More normal priority

        # Generate realistic messages based on category
        messages = {
            "Здравеопазване": [
                "Нуждая се от придружител за лекарски преглед.",
                "Търся помощ за рехабилитация у дома.",
                "Нуждая се от доброволец за болнични посещения."
            ],
            "Образование": [
                "Имам нужда от помощ с уроците по български език.",
                "Търся учител по английски за детето ми.",
                "Нуждая се от помощ с компютърни умения."
            ],
            "Социална помощ": [
                "Самотен съм и бих се радвал на компания за разговор.",
                "Нуждая се от емоционална подкрепа след загуба.",
                "Търся приятел за разходки в парка."
            ],
            "Битови нужди": [
                "Нуждая се от помощ с пазаруване и готвене.",
                "Търся помощ за почистване и подреждане на дома.",
                "Имам нужда от ремонт на електроуреди."
            ],
            "Транспорт": [
                "Нуждая се от придружител за пътуване до друг град.",
                "Търся помощ за транспортиране на тежки вещи.",
                "Нуждая се от шофьор за лекарски прегледи."
            ],
            "Техническа помощ": [
                "Нуждая се от помощ с настройка на компютър.",
                "Търся учител по смартфон за възрастни.",
                "Имам проблем с интернет връзката."
            ]
        }

        message = random.choice(messages.get(category, ["Нуждая се от помощ."]))

        help_request = HelpRequest(
            name=name,
            email=email,
            title=category,
            description=message,  # Set description field
            message=message,      # Also set message field
            status=status,
            priority=priority
        )
        db.session.add(help_request)

    db.session.commit()
    print(f"✅ Created {count} sample help requests")


def create_sample_tasks(count=10):
    """Create sample tasks for the smart matching system"""
    print(f"Creating {count} sample tasks...")

    categories = ["Здравеопазване", "Образование", "Социална помощ", "Битови нужди", "Техническа помощ"]
    priorities = ["low", "medium", "high", "urgent"]
    statuses = ["open", "assigned", "in_progress", "completed"]

    task_templates = [
        {
            "title": "Придружаване до болница",
            "description": "Придружаване на пациент до болница за преглед и обратно до дома",
            "category": "Здравеопазване",
            "required_skills": ["Първа помощ", "Транспорт"],
            "estimated_hours": 4
        },
        {
            "title": "Помощ с домашни работи",
            "description": "Помощ на ученик с домашни работи по математика и български език",
            "category": "Образование",
            "required_skills": ["Образование", "Математика"],
            "estimated_hours": 2
        },
        {
            "title": "Пазаруване и готвене",
            "description": "Пазаруване на хранителни продукти и приготвяне на топла храна",
            "category": "Битови нужди",
            "required_skills": ["Готовка", "Транспорт"],
            "estimated_hours": 3
        },
        {
            "title": "Техническа поддръжка",
            "description": "Настройка на компютър и обучение по основни компютърни умения",
            "category": "Техническа помощ",
            "required_skills": ["ИТ поддръжка", "Образование"],
            "estimated_hours": 2
        },
        {
            "title": "Социална компания",
            "description": "Посещение и разговор с самотен възрастен човек",
            "category": "Социална помощ",
            "required_skills": ["Социална работа", "Психология"],
            "estimated_hours": 1
        }
    ]

    # Add predefined tasks
    for task_data in task_templates:
        task = Task(**task_data)
        task.priority = random.choice(priorities)
        task.status = random.choice(statuses)
        task.required_skills = json.dumps(task_data.get("required_skills", []))  # Convert list to JSON
        db.session.add(task)

    # Generate additional random tasks
    for i in range(len(task_templates), count):
        category = random.choice(categories)
        priority = random.choices(priorities, weights=[0.4, 0.4, 0.15, 0.05])[0]
        status = random.choices(statuses, weights=[0.3, 0.3, 0.2, 0.2])[0]

        titles = {
            "Здравеопазване": ["Медицинско придружаване", "Рехабилитация у дома", "Здравни консултации"],
            "Образование": ["Помощ с уроци", "Компютърно обучение", "Езикови уроци"],
            "Социална помощ": ["Социални посещения", "Емоционална подкрепа", "Организация на събития"],
            "Битови нужди": ["Домакинска помощ", "Ремонтни работи", "Градинарство"],
            "Техническа помощ": ["ИТ поддръжка", "Технически ремонт", "Онлайн помощ"]
        }

        title = random.choice(titles.get(category, ["Обща помощ"]))
        description = f"Задача в категория {category}: {title}"

        task = Task(
            title=title,
            description=description,
            category=category,
            priority=priority,
            status=status,
            estimated_hours=random.randint(1, 8)
        )
        db.session.add(task)

    db.session.commit()
    print(f"✅ Created {count} sample tasks")


def create_sample_analytics_data():
    """Create sample analytics events and user activities"""
    print("Creating sample analytics data...")

    # Create some analytics events
    event_types = ["page_view", "button_click", "form_submit", "help_request_created", "volunteer_registered"]
    categories = ["navigation", "engagement", "conversion", "user_action"]

    for i in range(50):
        event = AnalyticsEvent(
            event_type=random.choice(event_types),
            event_category=random.choice(categories),
            event_action=f"action_{i}",
            user_session=f"session_{random.randint(1, 20)}",
            user_type=random.choice(["guest", "volunteer", "admin"]),
            page_url=random.choice(["/", "/volunteer_register", "/submit_request", "/analytics/admin_analytics"]),
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        db.session.add(event)

    # Create some chatbot conversations
    for i in range(20):
        conversation = ChatbotConversation(
            session_id=f"chat_session_{i}",
            user_message=random.choice([
                "Как да се регистрирам като доброволец?",
                "Как да поискам помощ?",
                "Какви услуги предлагате?",
                "Къде се намирате?"
            ]),
            bot_response="Благодаря за въпроса! Ще ви помогнем с информацията, от която се нуждаете.",
            response_type="ai",
            ai_provider="mock",
            ai_confidence=round(random.uniform(0.7, 0.95), 2),
            user_type=random.choice(["guest", "volunteer"])
        )
        db.session.add(conversation)

    db.session.commit()
    print("✅ Created sample analytics data")


def create_sample_feedback(count=8):
    """Create sample feedback entries"""
    print(f"Creating {count} sample feedback entries...")

    feedback_messages = [
        "Отлична платформа! Много съм благодарен за помощта.",
        "Доброволците са много отзивчиви и професионални.",
        "Интерфейсът е лесен за използване, дори за възрастни хора.",
        "Бързо намерих помощта, от която се нуждаех.",
        "Платформата свързва нуждаещите се с доброволци по чудесен начин.",
        "Имам някои технически проблеми, но услугата е страхотна.",
        "Благодаря на всички доброволци за тяхната всеотдайност!",
        "Предлагам да добавите още категории помощ."
    ]

    for i in range(count):
        feedback = Feedback(
            name=fake.name(),
            email=fake.email(),
            message=random.choice(feedback_messages),
            sentiment_score=round(random.uniform(-0.3, 0.8), 2),
            sentiment_label=random.choice(["positive", "neutral", "negative"]),
            sentiment_confidence=round(random.uniform(0.6, 0.95), 2),
            user_type=random.choice(["guest", "volunteer", "admin"])
        )
        db.session.add(feedback)

    db.session.commit()
    print(f"✅ Created {count} sample feedback entries")


def create_sample_success_stories(count=5):
    """Create sample success stories"""
    print(f"Creating {count} sample success stories...")

    stories = [
        {
            "title": "Спасена благодарение на доброволци",
            "content": "Бях в тежко положение след операция и нямах кой да ми помогне с ежедневните задачи. Платформата HelpChain ме свърза с прекрасни доброволци, които ми помагаха с пазаруване, готвене и придружаване до лекар. Благодаря на всички!"
        },
        {
            "title": "От самотен към общуване",
            "content": "Бях много самотен след пенсионирането си. Чрез HelpChain се запознах с доброволци, които ме посещават редовно и ми правят компания. Животът ми се промени към по-добро!"
        },
        {
            "title": "Образователна помощ за детето ми",
            "content": "Синът ми имаше затруднения с математиката в училище. Намерих чудесен доброволец-учител чрез платформата, който му помага два пъти седмично. Оценките му се подобриха значително!"
        },
        {
            "title": "Техническа помощ за възрастни",
            "content": "Не можех да се справя с компютъра и смартфона си. Доброволец от HelpChain ми отдели време и ме научи на основните неща. Сега мога да общувам с внуците си онлайн!"
        },
        {
            "title": "Здравна подкрепа в труден момент",
            "content": "След инсулт имах нужда от рехабилитация у дома. Доброволците от HelpChain ми помагаха с упражненията и ме придружаваха до болница. Възстановяването ми беше много по-успешно благодарение на тяхната подкрепа."
        }
    ]

    for story in stories:
        success_story = SuccessStory(**story)
        db.session.add(success_story)

    db.session.commit()
    print(f"✅ Created {count} sample success stories")


def main():
    """Main function to create all sample data"""
    print("🚀 Starting HelpChain Sample Data Generator")
    print("=" * 50)

    with app.app_context():
        try:
            # Create sample data in order
            create_sample_volunteers(20)
            create_sample_help_requests(15)
            create_sample_tasks(10)
            create_sample_analytics_data()
            create_sample_feedback(8)
            create_sample_success_stories(5)

            print("\n" + "=" * 50)
            print("🎉 Sample data generation completed successfully!")
            print("\n📊 Summary:")
            print("   • 20 Volunteers with gamification stats")
            print("   • 15 Help requests across different categories")
            print("   • 10 Tasks for smart matching system")
            print("   • Analytics events and chatbot conversations")
            print("   • 8 Feedback entries with sentiment analysis")
            print("   • 5 Success stories")
            print("\n🔗 You can now:")
            print("   • Browse volunteers at /admin_volunteers")
            print("   • View help requests in admin dashboard")
            print("   • Check analytics at /analytics/admin_analytics")
            print("   • Test chatbot at /api/chatbot/message")

        except Exception as e:
            print(f"❌ Error creating sample data: {e}")
            db.session.rollback()
            return False

    return True


if __name__ == "__main__":
    main()