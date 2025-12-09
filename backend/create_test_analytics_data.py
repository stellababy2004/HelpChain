"""
ðíÐèðÀð┤ð░ð▓ð░ð¢ðÁ ð¢ð░ ÐéðÁÐüÐéð¥ð▓ð░ ð▒ð░ðÀð░ ð┤ð░ð¢ð¢ð© Ðü ÐÇð░ðÀð¢ð¥ð¥ð▒ÐÇð░ðÀð¢ð© ð┐ð¥ÐéÐÇðÁð▒ð©ÐéðÁð╗ð© ð© ðÀð░ÐÅð▓ð║ð© ðÀð░ analytics ÐéðÁÐüÐéð▓ð░ð¢ðÁ
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
    ðíÐèðÀð┤ð░ð▓ð░ ÐéðÁÐüÐéð¥ð▓ð░ ð▒ð░ðÀð░ ð┤ð░ð¢ð¢ð© Ðü ÐÇð░ðÀð¢ð¥ð¥ð▒ÐÇð░ðÀð¢ð© ð┤ð░ð¢ð¢ð©
    """
    # ðÿðÀÐéÐÇð©ð╣ ð▓Ðüð©Ðçð║ð© ÐéðÁÐüÐéð¥ð▓ð© ð┤ð░ð¢ð¢ð© ðÀð░ Ðçð©ÐüÐéð¥ seed-ð▓ð░ð¢ðÁ
    print("­ƒº╣ ðÿðÀÐçð©ÐüÐéð▓ð░ð¢ðÁ ð¢ð░ ÐéðÁÐüÐéð¥ð▓ð© ð┤ð░ð¢ð¢ð©...")
    from backend.models_with_analytics import AnalyticsEvent, Feedback

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
        print("Ô£à ðÆÐüð©Ðçð║ð© ÐéðÁÐüÐéð¥ð▓ð© ð┤ð░ð¢ð¢ð© Ðüð░ ð©ðÀÐéÐÇð©Ðéð©.")
        print("­ƒôØ ðíÐèðÀð┤ð░ð▓ð░ð¢ðÁ ð¢ð░ ÐéðÁÐüÐéð¥ð▓ð© Feedback ðÀð░ð┐ð©Ðüð©...")
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
                email=f"test.feedback{i + 1}@helpchain-test.bg",
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
        print(
            f"Ô£à ðíÐèðÀð┤ð░ð┤ðÁð¢ð© {len(feedback_samples)} ÐéðÁÐüÐéð¥ð▓ð© Feedback ðÀð░ð┐ð©Ðüð░"
        )
    """ðíÐèðÀð┤ð░ð▓ð░ ÐéðÁÐüÐéð¥ð▓ð░ ð▒ð░ðÀð░ ð┤ð░ð¢ð¢ð© Ðü ÐÇð░ðÀð¢ð¥ð¥ð▒ÐÇð░ðÀð¢ð© ð┤ð░ð¢ð¢ð©"""

    with app.app_context():
        # ðíÐèðÀð┤ð░ð▓ð░ð╝ðÁ ð¢ð¥ð▓ð© ÐéðÁÐüÐéð¥ð▓ð© ð┤ð░ð¢ð¢ð© ð▒ðÁðÀ ð©ðÀÐéÐÇð©ð▓ð░ð¢ðÁ ð¢ð░ ÐüÐéð░ÐÇð©
        print("­ƒôØ ðíÐèðÀð┤ð░ð▓ð░ð¢ðÁ ð¢ð░ ð¢ð¥ð▓ð© ÐéðÁÐüÐéð¥ð▓ð© ð┤ð░ð¢ð¢ð©...")

        # Cat├®gories d'aide
        help_categories = [
            "Transport",
            "Soins ├á domicile",
            "Aide m├®dicale",
            "Courses",
            "Assistance technique",
            "Traductions",
            "Formation",
            "Soutien psychologique",
            "Conseil juridique",
            "Soins aux personnes ├óg├®es",
            "Garde d'enfants",
            "Activit├®s sociales",
        ]

        # Villes fran├ºaises
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

        # ðíÐéð░ÐéÐâÐüð© ð¢ð░ ðÀð░ÐÅð▓ð║ð©
        request_statuses = [
            "ðÉð║Ðéð©ð▓ðÁð¢",
            "ðùð░ð▓ÐèÐÇÐêðÁð¢ð░",
            "ðÆ ð┐ÐÇð¥ÐåðÁÐü",
            "ð×Ðéð║ð░ðÀð░ð¢ð░",
            "ðºð░ð║ð░ ð┐ð¥Ðéð▓ÐèÐÇðÂð┤ðÁð¢ð©ðÁ",
        ]

        # ðúð╝ðÁð¢ð©ÐÅ ð© Ðüð┐ðÁÐåð©ð░ð╗ð©ðÀð░Ðåð©ð©
        skills_list = [
            "ð¿ð¥Ðäð©ÐÇð░ð¢ðÁ",
            "ðôð¥Ðéð▓ðÁð¢ðÁ",
            "ðƒð¥Ðçð©ÐüÐéð▓ð░ð¢ðÁ",
            "ðôÐÇð░ð┤ð©ð¢ð░ÐÇÐüÐéð▓ð¥",
            "ðáðÁð╝ð¥ð¢Ðéð©",
            "ðƒÐÇðÁð▓ð¥ð┤ð©",
            "ðÜð¥ð╝ð┐ÐÄÐéÐèÐÇð¢ð© ÐâÐüð╗Ðâð│ð©",
            "ð£ðÁð┤ð©Ðåð©ð¢Ðüð║ð© ð│ÐÇð©ðÂð©",
            "ðƒÐüð©Ðàð¥ð╗ð¥ð│ð©ÐÅ",
            "ð«ÐÇð©ð┤ð©ÐçðÁÐüð║ð© ð▓Ðèð┐ÐÇð¥Ðüð©",
            "ð×ð▒ÐâÐçðÁð¢ð©ðÁ",
            "ð£ÐâðÀð©ð║ð░",
            "ðÿðÀð║ÐâÐüÐéð▓ð¥",
            "ðíð┐ð¥ÐÇÐé",
            "ðæð©ðÀð¢ðÁÐü ð║ð¥ð¢ÐüÐâð╗Ðéð©ÐÇð░ð¢ðÁ",
            "ðíÐçðÁÐéð¥ð▓ð¥ð┤ÐüÐéð▓ð¥",
            "ðÿð¢ðÂðÁð¢ðÁÐÇÐüÐéð▓ð¥",
            "ðÉÐÇÐàð©ÐéðÁð║ÐéÐâÐÇð░",
        ]

        print("­ƒæÑ ðíÐèðÀð┤ð░ð▓ð░ð¢ðÁ ð¢ð░ ÐéðÁÐüÐéð¥ð▓ð© ð┤ð¥ð▒ÐÇð¥ð▓ð¥ð╗Ðåð©...")

        # ðíÐèðÀð┤ð░ð▓ð░ð¢ðÁ ð¢ð░ ÐéðÁÐüÐéð¥ð▓ð© ð┤ð¥ð▒ÐÇð¥ð▓ð¥ð╗Ðåð©
        volunteers = []
        for i in range(50):
            volunteer = Volunteer(
                name=f"[TEST] {fake.first_name()} {fake.last_name()}",
                email=f"test.volunteer{i + 1}@helpchain-test.fr",
            )
            volunteers.append(volunteer)
            db.session.add(volunteer)

        db.session.commit()
        print(
            f"Ô£à ðíÐèðÀð┤ð░ð┤ðÁð¢ð© {len(volunteers)} ÐéðÁÐüÐéð¥ð▓ð© ð┤ð¥ð▒ÐÇð¥ð▓ð¥ð╗Ðåð©"
        )

        print(
            "­ƒôØ ðíÐèðÀð┤ð░ð▓ð░ð¢ðÁ ð¢ð░ ÐéðÁÐüÐéð¥ð▓ð© ðÀð░ÐÅð▓ð║ð© ðÀð░ ð┐ð¥ð╝ð¥Ðë..."
        )

        # ðíÐèðÀð┤ð░ð▓ð░ð¢ðÁ ð¢ð░ ÐéðÁÐüÐéð¥ð▓ð© ðÀð░ÐÅð▓ð║ð© ðÀð░ ð┐ð¥ð╝ð¥Ðë
        help_requests = []
        for i in range(120):
            created_at = fake.date_time_between(start_date="-3M", end_date="now")

            # ðƒÐÇð©ð╝ðÁÐÇð¢ð© ðÀð░ð│ð╗ð░ð▓ð©ÐÅ ð© ð¥ð┐ð©Ðüð░ð¢ð©ÐÅ ð▒ð░ðÀð©ÐÇð░ð¢ð© ð¢ð░ ð║ð░ÐéðÁð│ð¥ÐÇð©ÐÅÐéð░
            category = random.choice(help_categories)

            titles_by_category = {
                "ðóÐÇð░ð¢Ðüð┐ð¥ÐÇÐé": [
                    "ðØÐâðÂð┤ð░ÐÅ ÐüðÁ ð¥Ðé ð┐ÐÇðÁð▓ð¥ðÀ ð┤ð¥ ð▒ð¥ð╗ð¢ð©Ðåð░",
                    "ðƒð¥ð╝ð¥Ðë ðÀð░ Ðéð¥ð▓ð░ÐÇðÁð¢ðÁ ð¢ð░ ð╝ðÁð▒ðÁð╗ð©",
                    "ðƒÐÇðÁð▓ð¥ðÀ ð┤ð¥ ð╗ðÁÐéð©ÐëðÁ",
                ],
                "ðöð¥ð╝ð░ð║ð©ð¢Ðüð║ð© ð│ÐÇð©ðÂð©": [
                    "ðƒð¥Ðçð©ÐüÐéð▓ð░ð¢ðÁ ð¢ð░ ð░ð┐ð░ÐÇÐéð░ð╝ðÁð¢Ðé",
                    "ðƒð¥ð╝ð¥Ðë Ðü ð┐ÐÇð░ð¢ðÁ",
                    "ð×ÐÇð│ð░ð¢ð©ðÀð©ÐÇð░ð¢ðÁ ð¢ð░ ð┤ð¥ð╝",
                ],
                "ð£ðÁð┤ð©Ðåð©ð¢Ðüð║ð░ ð┐ð¥ð╝ð¥Ðë": [
                    "ðƒÐÇð©ð┤ÐÇÐâðÂð░ð▓ð░ð¢ðÁ ð┤ð¥ ð╗ðÁð║ð░ÐÇ",
                    "ðƒð¥ð╝ð¥Ðë Ðü ð╗ðÁð║ð░ÐÇÐüÐéð▓ð░",
                    "ðáðÁÐàð░ð▒ð©ð╗ð©Ðéð░Ðåð©ÐÅ",
                ],
                "ðƒð░ðÀð░ÐÇÐâð▓ð░ð¢ðÁ": [
                    "ðƒð░ðÀð░ÐÇÐâð▓ð░ð¢ðÁ ð¢ð░ ÐàÐÇð░ð¢ð©ÐéðÁð╗ð¢ð© ÐüÐéð¥ð║ð©",
                    "ðƒð¥ð║Ðâð┐ð║ð░ ð¢ð░ ð╗ðÁð║ð░ÐÇÐüÐéð▓ð░",
                    "ðÿðÀð▒ð¥ÐÇ ð¢ð░ ð┐ð¥ð┤ð░ÐÇÐèð║",
                ],
                "ðóðÁÐàð¢ð©ÐçðÁÐüð║ð░ ð┐ð¥ð┤ð┤ÐÇÐèðÂð║ð░": [
                    "ðáðÁð╝ð¥ð¢Ðé ð¢ð░ ð║ð¥ð╝ð┐ÐÄÐéÐèÐÇ",
                    "ðÿð¢ÐüÐéð░ð╗ð©ÐÇð░ð¢ðÁ ð¢ð░ Ðüð¥ÐäÐéÐâðÁÐÇ",
                    "ðØð░ÐüÐéÐÇð¥ð╣ð║ð░ ð¢ð░ WiFi",
                ],
                "ðƒÐÇðÁð▓ð¥ð┤ð©": [
                    "ðƒÐÇðÁð▓ð¥ð┤ ð¢ð░ ð┤ð¥ð║Ðâð╝ðÁð¢Ðéð©",
                    "ðúÐüÐéðÁð¢ ð┐ÐÇðÁð▓ð¥ð┤",
                    "ðƒð¥ð╝ð¥Ðë Ðü ð║ð¥ÐÇðÁÐüð┐ð¥ð¢ð┤ðÁð¢Ðåð©ÐÅ",
                ],
                "ð×ð▒ÐâÐçðÁð¢ð©ðÁ": [
                    "ðúÐÇð¥ð║ ð┐ð¥ ð╝ð░ÐéðÁð╝ð░Ðéð©ð║ð░",
                    "ðƒð¥ð╝ð¥Ðë Ðü ð░ð¢ð│ð╗ð©ð╣Ðüð║ð© ðÁðÀð©ð║",
                    "ðÜð¥ð╝ð┐ÐÄÐéÐèÐÇð¢ð░ ð│ÐÇð░ð╝ð¥Ðéð¢ð¥ÐüÐé",
                ],
                "ðƒÐüð©Ðàð¥ð╗ð¥ð│ð©ÐçðÁÐüð║ð░ ð┐ð¥ð┤ð║ÐÇðÁð┐ð░": [
                    "ðáð░ðÀð│ð¥ð▓ð¥ÐÇ ð┐ÐÇð© ÐéÐÇÐâð┤ð¢ð¥ÐüÐéð©",
                    "ðòð╝ð¥Ðåð©ð¥ð¢ð░ð╗ð¢ð░ ð┐ð¥ð┤ð║ÐÇðÁð┐ð░",
                    "ðÜð¥ð¢ÐüÐâð╗Ðéð░Ðåð©ÐÅ",
                ],
                "ð«ÐÇð©ð┤ð©ÐçðÁÐüð║ð░ ð║ð¥ð¢ÐüÐâð╗Ðéð░Ðåð©ÐÅ": [
                    "ðƒð¥ð╝ð¥Ðë Ðü ð┤ð¥ð║Ðâð╝ðÁð¢Ðéð©",
                    "ðƒÐÇð░ð▓ð¢ð© ÐüÐèð▓ðÁÐéð©",
                    "ðíÐèð┤ðÁð╣ÐüÐéð▓ð©ðÁ Ðü ð┐ÐÇð¥ÐåðÁð┤ÐâÐÇð©",
                ],
                "ðôÐÇð©ðÂð░ ðÀð░ ð▓ÐèðÀÐÇð░ÐüÐéð¢ð©": [
                    "ðƒÐÇð©ð┤ÐÇÐâðÂð░ð▓ð░ð¢ðÁ ð¢ð░ ð▓ÐèðÀÐÇð░ÐüÐéðÁð¢ Ðçð¥ð▓ðÁð║",
                    "ðƒð¥ð╝ð¥Ðë ð▓ ðÁðÂðÁð┤ð¢ðÁð▓ð©ðÁÐéð¥",
                    "ðíð¥Ðåð©ð░ð╗ð©ðÀð░Ðåð©ÐÅ",
                ],
                "ðôÐÇð©ðÂð░ ðÀð░ ð┤ðÁÐåð░": [
                    "ðöðÁÐéðÁð│ð╗ðÁð┤ð░ð¢ðÁ",
                    "ðƒð¥ð╝ð¥Ðë Ðü ð┤ð¥ð╝ð░Ðêð¢ð©",
                    "ðáð░ðÀð▓ð╗ðÁÐçðÁð¢ð©ÐÅ ðÀð░ ð┤ðÁÐåð░",
                ],
                "ðíð¥Ðåð©ð░ð╗ð¢ð© ð┤ðÁð╣ð¢ð¥ÐüÐéð©": [
                    "ð×ÐÇð│ð░ð¢ð©ðÀð©ÐÇð░ð¢ðÁ ð¢ð░ ÐüÐèð▒ð©ÐÇð░ð¢ðÁ",
                    "ðÜÐâð╗ÐéÐâÐÇð¢ð© ð░ð║Ðéð©ð▓ð¢ð¥ÐüÐéð©",
                    "ðöð¥ð▒ÐÇð¥ð▓ð¥ð╗ÐçðÁÐüð║ð© ð┐ÐÇð¥ðÁð║Ðé",
                ],
            }

            title = random.choice(
                titles_by_category.get(category, ["ð×ð▒Ðëð░ ð┐ð¥ð╝ð¥Ðë"])
            )

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
        print(
            f"Ô£à ðíÐèðÀð┤ð░ð┤ðÁð¢ð© {len(help_requests)} ÐéðÁÐüÐéð¥ð▓ð© ðÀð░ÐÅð▓ð║ð© ðÀð░ ð┐ð¥ð╝ð¥Ðë"
        )

        print("­ƒôè ðíÐèðÀð┤ð░ð▓ð░ð¢ðÁ ð¢ð░ ÐéðÁÐüÐéð¥ð▓ð© analytics ÐüÐèð▒ð©Ðéð©ÐÅ...")

        # ðóð©ð┐ð¥ð▓ðÁ ÐüÐèð▒ð©Ðéð©ÐÅ ðÀð░ analytics
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

        # ðƒð¥ð┐Ðâð╗ÐÅÐÇð¢ð© ÐüÐéÐÇð░ð¢ð©Ðåð©
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

        # ðíÐèðÀð┤ð░ð▓ð░ð¢ðÁ ð¢ð░ analytics ÐüÐèð▒ð©Ðéð©ÐÅ
        analytics_events = []
        for i in range(800):
            event_time = fake.date_time_between(start_date="-30d", end_date="now")

            event_type = random.choice(event_types)
            category = random.choice(event_categories)

            # ðáð░ðÀð╗ð©Ðçð¢ð© ð┤ðÁð╣ÐüÐéð▓ð©ÐÅ ð▒ð░ðÀð©ÐÇð░ð¢ð© ð¢ð░ Ðéð©ð┐ð░
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

            # ð£ðÁÐéð░ð┤ð░ð¢ð¢ð© ð▒ð░ðÀð©ÐÇð░ð¢ð© ð¢ð░ Ðéð©ð┐ð░ ÐüÐèð▒ð©Ðéð©ðÁ
            if event_type == "page_view":
                page = random.choice(popular_pages)
                _metadata = f'{{"page": "{page}", "test": true, "referrer": "direct", "load_time": {random.randint(200, 2000)}}}'
            elif event_type == "search":
                search_terms = [
                    "ð┐ð¥ð╝ð¥Ðë ðíð¥Ðäð©ÐÅ",
                    "ð┤ð¥ð▒ÐÇð¥ð▓ð¥ð╗ðÁÐå ðƒð╗ð¥ð▓ð┤ð©ð▓",
                    "ÐéÐÇð░ð¢Ðüð┐ð¥ÐÇÐé",
                    "ð╝ðÁð┤ð©Ðåð©ð¢Ðüð║ð░ ð┐ð¥ð╝ð¥Ðë",
                    "ð┐ÐÇðÁð▓ð¥ð┤ð©",
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
        print(
            f"Ô£à ðíÐèðÀð┤ð░ð┤ðÁð¢ð© {len(analytics_events)} ÐéðÁÐüÐéð¥ð▓ð© analytics ÐüÐèð▒ð©Ðéð©ÐÅ"
        )

        # ðíÐéð░Ðéð©ÐüÐéð©ð║ð░ ðÀð░ ÐüÐèðÀð┤ð░ð┤ðÁð¢ð©ÐéðÁ ð┤ð░ð¢ð¢ð©
        print(
            "\n­ƒôê ð×ð▒ð¥ð▒ÐëðÁð¢ð©ðÁ ð¢ð░ ÐüÐèðÀð┤ð░ð┤ðÁð¢ð©ÐéðÁ ÐéðÁÐüÐéð¥ð▓ð© ð┤ð░ð¢ð¢ð©:"
        )
        print(f"  ­ƒæÑ ðöð¥ð▒ÐÇð¥ð▓ð¥ð╗Ðåð©: {len(volunteers)}")
        print(f"  ­ƒôØ ðùð░ÐÅð▓ð║ð© ðÀð░ ð┐ð¥ð╝ð¥Ðë: {len(help_requests)}")
        print(f"  ­ƒôè Analytics ÐüÐèð▒ð©Ðéð©ÐÅ: {len(analytics_events)}")

        # ðáð░ðÀð┐ÐÇðÁð┤ðÁð╗ðÁð¢ð©ðÁ ð┐ð¥ ð┐ÐÇð©ð¥ÐÇð©ÐéðÁÐéð© (ÐéÐèð╣ ð║ð░Ðéð¥ ð¢ÐÅð╝ð░ category ð┐ð¥ð╗ðÁ)
        priority_count = {}
        for req in help_requests:
            priority_count[req.priority] = priority_count.get(req.priority, 0) + 1

        print("\n´┐¢´©Å ðáð░ðÀð┐ÐÇðÁð┤ðÁð╗ðÁð¢ð©ðÁ ð┐ð¥ ð┐ÐÇð©ð¥ÐÇð©ÐéðÁÐéð©:")
        for priority, count in sorted(priority_count.items()):
            print(f"  ÔÇó {priority}: {count} ðÀð░ÐÅð▓ð║ð©")

        # ðáð░ðÀð┐ÐÇðÁð┤ðÁð╗ðÁð¢ð©ðÁ ð┐ð¥ ÐüÐéð░ÐéÐâÐüð©
        status_count = {}
        for req in help_requests:
            status_count[req.status] = status_count.get(req.status, 0) + 1

        print("\n­ƒôè ðáð░ðÀð┐ÐÇðÁð┤ðÁð╗ðÁð¢ð©ðÁ ð┐ð¥ ÐüÐéð░ÐéÐâÐüð©:")
        for status, count in sorted(status_count.items()):
            print(f"  ÔÇó {status}: {count} ðÀð░ÐÅð▓ð║ð©")

        print("\n­ƒÄ» ðóðÁÐüÐéð¥ð▓ð░Ðéð░ ð▒ð░ðÀð░ ð┤ð░ð¢ð¢ð© ðÁ ð│ð¥Ðéð¥ð▓ð░!")
        print(
            "­ƒÆí ðÆÐüð©Ðçð║ð© ÐéðÁÐüÐéð¥ð▓ð© ðÀð░ð┐ð©Ðüð© Ðüð░ ð╝ð░ÐÇð║ð©ÐÇð░ð¢ð© Ðü '[TEST]' ð▓ ð©ð╝ðÁÐéð¥/ð¥ð┐ð©Ðüð░ð¢ð©ðÁÐéð¥"
        )
        print(
            "­ƒöì ðíðÁð│ð░ ð╝ð¥ðÂðÁÐéðÁ ð┤ð░ ÐéðÁÐüÐéð▓ð░ÐéðÁ Ðäð©ð╗ÐéÐÇð©ÐéðÁ ð▓ Analytics Dashboard!"
        )


if __name__ == "__main__":
    print(
        "­ƒÜÇ ðíÐèðÀð┤ð░ð▓ð░ð¢ðÁ ð¢ð░ ÐéðÁÐüÐéð¥ð▓ð░ ð▒ð░ðÀð░ ð┤ð░ð¢ð¢ð© ðÀð░ HelpChain Analytics..."
    )
    create_test_database()
    print("Ô£à ðùð░ð▓ÐèÐÇÐêðÁð¢ð¥ ÐâÐüð┐ðÁÐêð¢ð¥!")
