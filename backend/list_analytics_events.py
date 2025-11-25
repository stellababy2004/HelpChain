# Скрипт за проверка на всички AnalyticsEvent записи
from app import app
from extensions import db
from models_with_analytics import AnalyticsEvent

with app.app_context():
    events = AnalyticsEvent.query.all()
    print(f"Намерени записи: {len(events)}")
    for e in events:
        print(
            f"session_id={e.user_session}, type={e.event_type}, category={e.event_category}, lang={e.event_label}, created_at={e.created_at}"
        )
