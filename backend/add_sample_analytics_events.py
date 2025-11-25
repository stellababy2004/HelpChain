# Скрипт за добавяне на примерни AnalyticsEvent записи
from datetime import datetime, timedelta

from app import app
from extensions import db
from models_with_analytics import AnalyticsEvent

with app.app_context():
    now = datetime.now()
    events = [
        # Медицина
        AnalyticsEvent(
            event_type="AI",
            event_category="Медицина",
            event_label="BG",
            user_session="A123",
            load_time=0.32,
            device_type="web",
            created_at=now.replace(hour=18, minute=0),
        ),
        AnalyticsEvent(
            event_type="AI",
            event_category="Медицина",
            event_label="BG",
            user_session="D012",
            load_time=0.31,
            device_type="web",
            created_at=now.replace(hour=19, minute=0),
        ),
        AnalyticsEvent(
            event_type="AI",
            event_category="Медицина",
            event_label="EN",
            user_session="M001",
            load_time=0.29,
            device_type="mobile",
            created_at=now.replace(hour=17, minute=0),
        ),
        # Психолог
        AnalyticsEvent(
            event_type="FAQ",
            event_category="Психолог",
            event_label="EN",
            user_session="B456",
            load_time=0.21,
            device_type="mobile",
            created_at=now.replace(hour=16, minute=0),
        ),
        AnalyticsEvent(
            event_type="FAQ",
            event_category="Психолог",
            event_label="BG",
            user_session="P002",
            load_time=0.25,
            device_type="web",
            created_at=now.replace(hour=15, minute=0),
        ),
        AnalyticsEvent(
            event_type="FAQ",
            event_category="Психолог",
            event_label="FR",
            user_session="P003",
            load_time=0.22,
            device_type="web",
            created_at=now.replace(hour=14, minute=0),
        ),
        # Транспорт
        AnalyticsEvent(
            event_type="Human",
            event_category="Транспорт",
            event_label="FR",
            user_session="C789",
            load_time=0.45,
            device_type="web",
            created_at=now.replace(hour=13, minute=0),
        ),
        AnalyticsEvent(
            event_type="Human",
            event_category="Транспорт",
            event_label="BG",
            user_session="T004",
            load_time=0.41,
            device_type="mobile",
            created_at=now.replace(hour=12, minute=0),
        ),
        AnalyticsEvent(
            event_type="Human",
            event_category="Транспорт",
            event_label="EN",
            user_session="T005",
            load_time=0.39,
            device_type="web",
            created_at=now.replace(hour=11, minute=0),
        ),
    ]
    db.session.bulk_save_objects(events)
    db.session.commit()
    print("Добавени са примерни AnalyticsEvent записи!")
