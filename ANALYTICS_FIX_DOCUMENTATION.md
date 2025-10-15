# Поправка на аналитиката: Документация

## Резюме

Този документ описва поправките, направени за разрешаване на проблеми със SQLAlchemy моделите в аналитичната система на HelpChain.

## Проблеми, които са били разрешени

### 1. SQLAlchemy Instance Conflicts

**Проблем:** Аналитичната услуга използваше статична `db` инстанция, което водеше до конфликти при използване в различни Flask контексти (web requests, background threads, тестове).

**Решение:** Добавена е функция `get_db()` в `analytics_service.py`, която динамично извлича базата данни от текущия Flask app context:

```python
def get_db():
    """Get the database instance from current Flask app context"""
    from flask import current_app

    if current_app and "sqlalchemy" in current_app.extensions:
        return current_app.extensions["sqlalchemy"]
    else:
        # Fallback - try to import from extensions
        try:
            from extensions import db
            return db
        except ImportError:
            try:
                from .extensions import db
                return db
            except ImportError:
                raise RuntimeError("Could not get database instance")
```

**Файл:** `backend/analytics_service.py` (линии 41-59)

### 2. AdminUser Import Issues

**Проблем:** Моделите `TwoFactorAuth` и `AdminSession` в `models_with_analytics.py` имаха relationships с `AdminUser`, но този модел не беше импортиран, което водеше до грешки при инициализация на SQLAlchemy relationships.

**Решение:** Добавен е импорт на `AdminUser` в `models_with_analytics.py` с fallback логика:

```python
# Import AdminUser for relationship resolution
try:
    from .models import AdminUser
except ImportError:
    try:
        from models import AdminUser
    except ImportError:
        # Define a placeholder if models.py is not available
        AdminUser = None
```

**Файл:** `backend/models_with_analytics.py` (линии 14-22)

## Промени в кода

### backend/analytics_service.py

1. **Премахнат директен импорт на db** (линии 14-19):
   - Коментиран е директният импорт на `db` от `extensions`
   - Това предотвратява статично свързване с един Flask app

2. **Добавена функция get_db()** (линии 41-59):
   - Динамично извлича database инстанцията от Flask app context
   - Има fallback механизъм за standalone използване

3. **Използване на get_db() навсякъде** (през целия файл):
   - Всички `db.session` са заменени с `get_db().session`
   - Всички database query операции използват `get_db()`

### backend/models_with_analytics.py

1. **Добавен импорт на AdminUser** (линии 14-22):
   - Импортира `AdminUser` от `models.py`
   - Има fallback логика за различни import пътища
   - Предотвратява грешки при relationships

## Тестване

### Автоматични тестове

Създаден е нов тест файл `tests/test_analytics_service_fixes.py`, който валидира:

1. ✓ `get_db()` функцията съществува и е callable
2. ✓ `get_db()` връща валидна database инстанция
3. ✓ `AdminUser` е правилно импортиран в `models_with_analytics`
4. ✓ Аналитичната услуга работи с Flask app context
5. ✓ TwoFactorAuth -> AdminUser relationship работи
6. ✓ AdminSession -> AdminUser relationship работи
7. ✓ Analytics event tracking работи без конфликти
8. ✓ Няма SQLAlchemy instance conflicts при множество извиквания

### Ръчно тестване

Създаден е скрипт `/tmp/test_analytics_comprehensive.py` за ръчно тестване на всички функционалности.

## Резултати

След прилагането на поправките:

1. ✅ Аналитичната услуга работи правилно в Flask app context
2. ✅ Няма SQLAlchemy instance conflicts
3. ✅ Model relationships (TwoFactorAuth, AdminSession) работят коректно
4. ✅ Analytics service връща правилна структура от данни:
   - `overview` - общи метрики
   - `user_engagement` - потребителска ангажираност
   - `chatbot_analytics` - аналитика на чатбота
   - `performance_metrics` - метрики за производителност
   - `conversion_funnel` - conversion funnel анализ
   - `user_journey` - анализ на потребителски пътища
   - `real_time` - real-time метрики

5. ✅ Няма грешка ключ `error` в резултатите (когато има правилен Flask context)

## Как да се използва

### В Flask приложение

```python
from flask import Flask
from extensions import db
from analytics_service import analytics_service

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///your_database.db'
db.init_app(app)

with app.app_context():
    # Get analytics data
    analytics = analytics_service.get_dashboard_analytics(days=30)
    print(analytics['overview'])
```

### За тестване

```python
# Run the unit tests
python3 tests/test_analytics_service_fixes.py

# Run comprehensive test
python3 /tmp/test_analytics_comprehensive.py
```

## Заключение

Поправките разрешават критични проблеми със SQLAlchemy моделите в аналитичната система:
- Динамично извличане на database инстанцията от Flask context
- Правилни model relationships чрез импорт на AdminUser
- Стабилна работа на аналитичната услуга без конфликти

Всички тестове минават успешно, и аналитичната услуга е готова за production използване.
