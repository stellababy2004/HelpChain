# HelpChain Copilot Instructions

## Архитектура

HelpChain е Flask уеб приложение за свързване на нуждаещи се хора с доброволци. Използва SQLAlchemy за база данни, Flask-Mail за имейли, Flask-Babel за многоезичност (bg/en), и AI интеграция с OpenAI/Gemini за чатбот.

**Ключови компоненти:**

- `backend/helpchain-backend/src/app.py` - Основно Flask приложение с blueprints (routes/, controllers/), create_app() factory pattern
- `backend/appy.py` - По-опростена версия за бързо тестване
- `backend/models_with_analytics.py` - SQLAlchemy модели (User, HelpRequest, Volunteer, AdminUser с 2FA, AnalyticsEvent)
- `backend/models.py` - Основни модели без analytics
- `backend/ai_service.py` - AI чатбот услуга с fallback логика и поддръжка за OpenAI/Gemini
- `backend/analytics_service.py` - Проследяване на потребителско поведение и метрики
- `backend/helpchain-backend/src/routes/` - Blueprint routes (api.py, analytics.py)
- `backend/helpchain-backend/src/controllers/` - Business logic controllers

**Поток на данни:** Потребителски заявки → AI анализ → Доброволци → Админ панел → Изпълнение

## Критични работни процеси

- **Стартиране (production):** `uvicorn backend.helpchain-backend.src.asgi:asgi_app --host 0.0.0.0 --port 10000`
- **Стартиране (dev):** `python run.py` или `python backend/appy.py`
- **База данни:** `flask db migrate && flask db upgrade` за Alembic миграции
- **Тестване:** `pytest` с conftest.py за fixtures и PYTHONPATH setup; тестове използват mocked SMTP
- **Имейли:** Настрой .env с MAIL_SERVER/Zoho SMTP променливи
- **AI:** Задай OPENAI_API_KEY или GEMINI_API_KEY; използвай AI_DEV_MOCK=1 за тестване без API
- **Разработка:** Активирай venv с `venv\Scripts\activate` (Windows) или `source venv/bin/activate` (Linux/Mac)

## Проектни конвенции

- **Език:** Основно български (gettext за i18n); AI отговори винаги на български
- **Модели:** Използвай `db.session.add/commit` за транзакции; проверявай `db.create_all()` в app context
- **Аналитика:** Проследявай събития с `analytics_service.track_event()` за user behavior
- **Грешки:** Safe database операции с `_safe_database_operation`; логвай с `app.logger`
- **Файлове:** Upload в `app.config["UPLOAD_FOLDER"]` с `secure_filename()`
- **Шаблони:** Jinja2 с `{% trans %}...{% endtrans %}` за преводи
- **2FA:** Използвай `AdminUser.verify_totp(token)` за верификация; генерирай QR с `get_totp_uri()`; templates в `backend/helpchain-backend/src/templates/`
- **Конфигурация:** Factory pattern с `create_app(config_object)`; .env за secrets, instance/config.py за локални настройки
- **Тестове:** pytest fixtures в conftest.py; mock SMTP за безопасност

## Интеграции

- **AI чатбот:** `ai_service.generate_response()` връща dict с response/confidence/provider; поддържа OpenAI GPT и Google Gemini с fallback
- **Имейл нотификации:** `mail.send(Message())` за нови заявки; Zoho SMTP конфигурация
- **Аналитика:** `analytics_service.get_dashboard_analytics()` за метрики; проследява user behavior, performance, chatbot conversations
- **Миграции:** Alembic за schema промени
- **2FA:** pyotp за TOTP; AdminUser методи за enable/disable; `flask db migrate && flask db upgrade`
- **Админ панел:** Изисква `session["admin_logged_in"] = True`; поддържа 2FA с TOTP
- **База данни:** SQLite за dev, PostgreSQL за production; SQLAlchemy с relationships

**Примери:**

- Нов blueprint route: регистрирай в `app.register_blueprint(bp, url_prefix="/api")`
- AI отговор: `result = await ai_service.generate_response(user_msg, context); return result["response"]`
- Analytics: `analytics_service.track_event("page_view", page_url=request.path)`
- 2FA: `if admin_user.verify_totp(token): login_user(admin_user)`
- Database операция: `with app.app_context(): db.create_all()`
- Email: `mail.send(Message(subject="...", recipients=[...], body="..."))`

## Забележки

- Провери `current_app` context за database операции в background threads
- Използвай `flash()` за потребителски съобщения
- Admin панел изисква `session["admin_logged_in"] = True` и поддържа 2FA
- Тестове използват mocked SMTP за безопасност
- AI система разпознава език автоматично но отговаря винаги на български
- Аналитика проследява performance metrics, user behavior, и chatbot interactions

# Track feedback event for analytics

try:
from ...analytics_service import analytics_service
analytics_service.track_event(
event_type="user_feedback",
event_category="engagement",
event_action="submit_feedback",
context={
"feedback_length": len(data.get("message", "")),
"has_email": bool(data.get("email")),
"user_agent": request.headers.get("User-Agent"),
"ip_address": request.remote_addr,
"page_url": request.referrer or "/about"
}
)
except Exception as analytics_error:
print(f"Analytics tracking failed: {analytics_error}") # Non-blocking

def test_feedback_route():
"""Test feedback submission with analytics tracking"""
tester = app.test_client()
response = tester.post("/feedback", data={
"name": "Test User",
"email": "test@example.com",
"message": "This is a test feedback message"
})
assert response.status_code == 302 # Should redirect
