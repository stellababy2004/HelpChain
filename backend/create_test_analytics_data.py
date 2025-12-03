"""
Създаване на тестова база данни с разнообразни потребители и заявки за analytics тестване
"""

import os
import random
import sys
from datetime import timedelta

from faker import Faker

# Add backend directory to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Import Flask app and models
from appy import app, db

from backend.models import HelpRequest, Volunteer
from backend.models_with_analytics import AnalyticsEvent

fake = Faker("fr_FR")  # French locale


def create_test_database():
    """
    Създава тестова база данни с разнообразни данни
    """
    # Изтрий всички тестови данни за чисто seed-ване
    print("🧹 Изчистване на тестови данни...")
    from models_with_analytics import AnalyticsEvent, Feedback

    with app.app_context():
        Volunteer.query.filter(Volunteer.email.like("%@helpchain-test.%")).delete(
            synchronize_session=False
        )
        Feedback.query.filter(Feedback.email.like("%@helpchain-test.%")).delete(
            synchronize_session=False
        )
        HelpRequest.query.filter(HelpRequest.email.like("%@helpchain-test.%")).delete(
            synchronize_session=False
        )
        AnalyticsEvent.query.filter(
            AnalyticsEvent.user_session.like("test_session_%")
        ).delete(synchronize_session=False)
        db.session.commit()
        print("✅ Всички тестови данни са изтрити.")
        print("📝 Създаване на тестови Feedback записи...")
        feedback_samples = []
        feedback_languages = ["bg", "en", "ru"]
        feedback_categories = [
            "faq/general",
            "ai/medical",
            "ai/legal",
            "ai/transport",
            "human/support",
        ]
        feedback_models = ["openai", "gemini", "custom", "gpt-3.5", "gpt-4"]
        feedback_labels = ["positive", "neutral", "negative"]
        for i in range(60):
            lang = random.choice(feedback_languages)
            cat = random.choice(feedback_categories)
            model = random.choice(feedback_models)
            label = random.choices(feedback_labels, weights=[0.5, 0.2, 0.3])[0]
            score = {
                "positive": random.uniform(4.0, 5.0),
                "neutral": random.uniform(2.5, 3.5),
                "negative": random.uniform(1.0, 2.4),
            }[label]
            fb = Feedback(
                name=f"[TEST] {fake.first_name()} {fake.last_name()}",
                email=f"test.feedback{i+1}@helpchain-test.bg",
                message=f"[TEST] {fake.sentence(nb_words=10)} {label} feedback for {cat} ({model})",
                timestamp=fake.date_time_between(start_date="-30d", end_date="now"),
                sentiment_score=score,
                sentiment_label=label,
                sentiment_confidence=round(random.uniform(0.7, 1.0), 2),
                ai_processed=True,
                ai_processing_time=random.uniform(0.1, 1.5),
                ai_provider=model,
                user_type=lang,
                user_id=None,
                page_url=cat,
                user_agent="TestUserAgent/1.0",
                ip_address=fake.ipv4(),
            )
            feedback_samples.append(fb)
            db.session.add(fb)
        db.session.commit()
        print(f"✅ Създадени {len(feedback_samples)} тестови Feedback записа")
    """Създава тестова база данни с разнообразни данни"""

    with app.app_context():
        # Създаваме нови тестови данни без изтриване на стари
        print("📝 Създаване на нови тестови данни...")

        # Catégories d'aide
        help_categories = [
            "Transport",
            "Soins à domicile",
            "Aide médicale",
            "Courses",
            "Assistance technique",
            "Traductions",
            "Formation",
            "Soutien psychologique",
            "Conseil juridique",
            "Soins aux personnes âgées",
            "Garde d'enfants",
            "Activités sociales",
        ]

        # Villes françaises
        french_cities = [
            "Paris",
            "Marseille",
            "Lyon",
            "Toulouse",
            "Nice",
            "Nantes",
            "Strasbourg",
            "Montpellier",
            "Bordeaux",
            "Lille",
            "Rennes",
            "Reims",
        ]

        # Статуси на заявки
        request_statuses = [
            "Активен",
            "Завършена",
            "В процес",
            "Отказана",
            "Чака потвърждение",
        ]

        # Умения и специализации
        skills_list = [
            "Шофиране",
            "Готвене",
            "Почистване",
            "Градинарство",
            "Ремонти",
            "Преводи",
            "Компютърни услуги",
            "Медицински грижи",
            "Психология",
            "Юридически въпроси",
            "Обучение",
            "Музика",
            "Изкуство",
            "Спорт",
            "Бизнес консултиране",
            "Счетоводство",
            "Инженерство",
            "Архитектура",
        ]

        print("👥 Създаване на тестови доброволци...")

        # Създаване на тестови доброволци
        volunteers = []
        for i in range(50):
            volunteer = Volunteer(
                name=f"[TEST] {fake.first_name()} {fake.last_name()}",
                email=f"test.volunteer{i + 1}@helpchain-test.fr",
            )
            volunteers.append(volunteer)
            db.session.add(volunteer)

        db.session.commit()
        print(f"✅ Създадени {len(volunteers)} тестови доброволци")

        print("📝 Създаване на тестови заявки за помощ...")

        # Създаване на тестови заявки за помощ
        help_requests = []
        for i in range(120):
            created_at = fake.date_time_between(start_date="-3M", end_date="now")

            # Примерни заглавия и описания базирани на категорията
            category = random.choice(help_categories)

            titles_by_category = {
                "Транспорт": [
                    "Нуждая се от превоз до болница",
                    "Помощ за товарене на мебели",
                    "Превоз до летище",
                ],
                "Домакински грижи": [
                    "Почистване на апартамент",
                    "Помощ с пране",
                    "Организиране на дом",
                ],
                "Медицинска помощ": [
                    "Придружаване до лекар",
                    "Помощ с лекарства",
                    "Рехабилитация",
                ],
                "Пазаруване": [
                    "Пазаруване на хранителни стоки",
                    "Покупка на лекарства",
                    "Избор на подарък",
                ],
                "Техническа поддръжка": [
                    "Ремонт на компютър",
                    "Инсталиране на софтуер",
                    "Настройка на WiFi",
                ],
                "Преводи": [
                    "Превод на документи",
                    "Устен превод",
                    "Помощ с кореспонденция",
                ],
                "Обучение": [
                    "Урок по математика",
                    "Помощ с английски език",
                    "Компютърна грамотност",
                ],
                "Психологическа подкрепа": [
                    "Разговор при трудности",
                    "Емоционална подкрепа",
                    "Консултация",
                ],
                "Юридическа консултация": [
                    "Помощ с документи",
                    "Правни съвети",
                    "Съдействие с процедури",
                ],
                "Грижа за възрастни": [
                    "Придружаване на възрастен човек",
                    "Помощ в ежедневието",
                    "Социализация",
                ],
                "Грижа за деца": [
                    "Детегледане",
                    "Помощ с домашни",
                    "Развлечения за деца",
                ],
                "Социални дейности": [
                    "Организиране на събиране",
                    "Културни активности",
                    "Доброволчески проект",
                ],
            }

            title = random.choice(titles_by_category.get(category, ["Обща помощ"]))

            help_request = HelpRequest(
                name=f"[TEST] {fake.first_name()} {fake.last_name()}",
                email=f"test.requester{i + 1}@helpchain-test.bg",
                title=title,
                description=f"[TEST] {fake.text(max_nb_chars=200)}",
                priority=random.choice(["low", "normal", "urgent"]),
                status=random.choice(request_statuses),
            )

            help_requests.append(help_request)
            db.session.add(help_request)

        db.session.commit()
        print(f"✅ Създадени {len(help_requests)} тестови заявки за помощ")

        print("📊 Създаване на тестови analytics събития...")

        # Типове събития за analytics
        event_types = [
            "page_view",
            "user_action",
            "form_interaction",
            "feature_usage",
            "search",
            "registration",
            "login",
        ]

        event_categories = [
            "navigation",
            "volunteer",
            "admin",
            "ui",
            "search",
            "registration",
            "authentication",
            "help_request",
        ]

        # User types
        user_types = ["guest", "volunteer", "admin", "requester"]

        # Популярни страници
        popular_pages = [
            "/dashboard",
            "/volunteers",
            "/admin",
            "/register",
            "/login",
            "/help-requests",
            "/profile",
            "/analytics",
            "/search",
            "/about",
        ]

        # Създаване на analytics събития
        analytics_events = []
        for i in range(800):
            event_time = fake.date_time_between(start_date="-30d", end_date="now")

            event_type = random.choice(event_types)
            category = random.choice(event_categories)

            # Различни действия базирани на типа
            actions_by_type = {
                "page_view": ["visit", "load", "refresh"],
                "user_action": ["click", "submit", "download", "share"],
                "form_interaction": ["form_start", "form_submit", "form_error"],
                "feature_usage": ["search", "filter", "export", "sort"],
                "search": ["search_query", "search_results", "search_filter"],
                "registration": ["registration_start", "registration_complete"],
                "login": ["login_attempt", "login_success", "logout"],
            }

            action = random.choice(actions_by_type.get(event_type, ["generic_action"]))

            # Метаданни базирани на типа събитие
            if event_type == "page_view":
                page = random.choice(popular_pages)
                _metadata = f'{{"page": "{page}", "test": true, "referrer": "direct", "load_time": {random.randint(200, 2000)}}}'
            elif event_type == "search":
                search_terms = [
                    "помощ София",
                    "доброволец Пловдив",
                    "транспорт",
                    "медицинска помощ",
                    "преводи",
                ]
                term = random.choice(search_terms)
                _metadata = f'{{"search_term": "{term}", "test": true, "results_count": {random.randint(0, 50)}}}'
            else:
                _metadata = f'{{"test": true, "session_id": "test_session_{random.randint(1000, 9999)}", "user_agent": "TestAgent"}}'

            analytics_event = AnalyticsEvent(
                event_type=event_type,
                event_category=category,
                event_action=action,
                event_label=f"test_{random.choice(user_types)}",
                event_value=random.randint(1, 100),
                user_session=f"test_session_{random.randint(1000, 9999)}",
                user_type=random.choice(user_types),
                user_ip=fake.ipv4(),
                user_agent="TestUserAgent/1.0",
                referrer=random.choice(
                    [None, "https://google.com", "https://facebook.com", "direct"]
                ),
                page_url=random.choice(popular_pages),
                page_title=f"Test Page - {random.choice(popular_pages).replace('/', '')}",
                load_time=random.uniform(0.2, 3.0),
                screen_resolution=random.choice(
                    ["1920x1080", "1366x768", "1440x900", "1536x864"]
                ),
                device_type=random.choice(["desktop", "mobile", "tablet"]),
                created_at=event_time,
            )

            analytics_events.append(analytics_event)
            db.session.add(analytics_event)

        db.session.commit()
        print(f"✅ Създадени {len(analytics_events)} тестови analytics събития")

        # Статистика за създадените данни
        print("\n📈 Обобщение на създадените тестови данни:")
        print(f"  👥 Доброволци: {len(volunteers)}")
        print(f"  📝 Заявки за помощ: {len(help_requests)}")
        print(f"  📊 Analytics събития: {len(analytics_events)}")

        # Разпределение по приоритети (тъй като няма category поле)
        priority_count = {}
        for req in help_requests:
            priority_count[req.priority] = priority_count.get(req.priority, 0) + 1

        print("\n�️ Разпределение по приоритети:")
        for priority, count in sorted(priority_count.items()):
            print(f"  • {priority}: {count} заявки")

        # Разпределение по статуси
        status_count = {}
        for req in help_requests:
            status_count[req.status] = status_count.get(req.status, 0) + 1

        print("\n📊 Разпределение по статуси:")
        for status, count in sorted(status_count.items()):
            print(f"  • {status}: {count} заявки")

        print("\n🎯 Тестовата база данни е готова!")
        print("💡 Всички тестови записи са маркирани с '[TEST]' в името/описанието")
        print("🔍 Сега можете да тествате филтрите в Analytics Dashboard!")


if __name__ == "__main__":
    print("🚀 Създаване на тестова база данни за HelpChain Analytics...")
    create_test_database()
    print("✅ Завършено успешно!")
