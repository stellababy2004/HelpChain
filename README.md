# HelpChain – Платформа за социална и здравна подкрепа

[![Website](https://img.shields.io/badge/Live%20Demo-helpchain.live-green)](https://helpchain-s2l5.onrender.com)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0+-lightgrey.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

HelpChain е уеб приложение, разработено с Flask, което свързва нуждаещи се хора с доброволци, които могат да предоставят помощ. Целта е да се създаде реална платформа за управление на заявки, разпределяне на доброволци и поддържане на многоезична и достъпна комуникация.

## 🌐 Жив сайт

➡️ **[https://helpchain.live](https://helpchain.live)**

## 📋 Съдържание

- [Бърз старт](#-бърз-старт)
- [Функционалности](#-функционалности)
- [Технологии](#-технологии)
- [Архитектура](#-архитектура)
- [API документация](#-api-документация)
- [Разработка](#-разработка)
- [Тестване](#-тестване)
- [Деплоймънт](#-деплоймънт)
- [Принос](#-принос)
- [Лиценз](#-лиценз)

## � Бърз старт

### Предварителни изисквания

- Python 3.12+
- pip
- Git

### Инсталация

1. **Клонирайте репозитория:**

   ```bash
   git clone https://github.com/stellababy2004/HelpChain.bg.git
   cd HelpChain.bg
   ```

2. **Създайте виртуална среда:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # или
   venv\Scripts\activate     # Windows
   ```

3. **Инсталирайте зависимостите:**

   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # за разработка
   ```

4. **Настройте environment променливите:**

   ```bash
   cp .env.example .env
   # Редактирайте .env файла с вашите настройки
   ```

5. **Стартирайте приложението:**

   ```bash
   # За разработка
   python backend/appy.py

   # Или с uvicorn
   uvicorn backend.helpchain-backend.src.asgi:asgi_app --host 127.0.0.1 --port 8000
   ```

6. **Отворете в браузър:**
   - Главна страница: http://127.0.0.1:3000
   - Админ панел: http://127.0.0.1:3000/admin_login

## 🌟 Функционалности

### За потребители

- � **Подаване на заявки за помощ** - Лесна форма за изпращане на заявки
- 🌍 **Многоезична поддръжка** - Български и английски език
- 📱 **Responsive дизайн** - Работи на всички устройства
- � **Сигурна комуникация** - Защитени форми и валидация

### За доброволци

- � **Регистрация и профил** - Лесна регистрация с валидация
- � **Табло за управление** - Преглед на задачи и статус
- � **Геолокация** - Автоматично намиране на близки заявки
- � **Известия** - Имейл нотификации за нови задачи

### За администратори

- 🔐 **2FA защита** - Двуфакторна автентикация по имейл
- � **Управление на доброволци** - Добавяне, редактиране, изтриване
- 📈 **Аналитика** - Статистики и отчети
- � **Имейл система** - Проследяване на изпратени съобщения
- 🛠️ **Ролева система** - Управление на права и роли

## 🛠 Технологии

| Компонент  | Технология                     | Версия |
| ---------- | ------------------------------ | ------ |
| Backend    | Flask                          | 3.0+   |
| Database   | SQLAlchemy + SQLite/PostgreSQL | -      |
| Email      | Flask-Mail + Zoho SMTP         | -      |
| Auth       | Flask-Login + 2FA              | -      |
| i18n       | Flask-Babel                    | -      |
| Security   | Flask-Talisman + Flask-Limiter | -      |
| Real-time  | Flask-SocketIO                 | -      |
| AI         | OpenAI/Gemini API              | -      |
| Deployment | Uvicorn + Render               | -      |

## 🏗 Архитектура

```
HelpChain/
├── backend/
│   ├── appy.py                 # Основно Flask приложение
│   ├── models.py               # SQLAlchemy модели
│   ├── models_with_analytics.py # Модели с аналитика
│   ├── ai_service.py           # AI чатбот услуга
│   ├── analytics_service.py    # Аналитика и метрики
│   ├── permissions.py          # Система за права
│   └── helpchain-backend/
│       └── src/
│           ├── app.py          # Основно приложение (ASGI)
│           ├── routes/         # Blueprint routes
│           ├── controllers/    # Business logic
│           ├── templates/      # Jinja2 шаблони
│           └── static/         # CSS, JS, images
├── tests/                      # Unit и integration тестове
├── instance/                   # Database и конфигурация
├── translations/               # i18n файлове
└── docs/                       # Документация
```

## 📡 API документация

### Основни endpoints

| Метод | Endpoint                 | Описание                       |
| ----- | ------------------------ | ------------------------------ |
| GET   | `/`                      | Главна страница                |
| GET   | `/all_categories`        | Всички категории помощ         |
| POST  | `/volunteer_register`    | Регистрация на доброволец      |
| POST  | `/submit_request`        | Подаване на заявка             |
| GET   | `/admin_login`           | Админ вход                     |
| GET   | `/api/volunteers/nearby` | Намиране на доброволци наблизо |

### Геолокационни API

```bash
# Намиране на доброволци в радиус
GET /api/volunteers/nearby?lat=42.6977&lng=23.3219&radius=50

# Обновяване на локацията на доброволец
PUT /api/volunteers/{id}/location
Content-Type: application/json
{
  "latitude": 42.6977,
  "longitude": 23.3219,
  "location": "София"
}
```

## 💻 Разработка

### Настройка за разработка

1. **Инсталирайте development зависимости:**

   ```bash
   pip install -r requirements-dev.txt
   ```

2. **Настройте pre-commit hooks:**

   ```bash
   pre-commit install
   ```

3. **Стартирайте с debug режим:**
   ```bash
   FLASK_ENV=development python backend/appy.py
   ```

### Логиране и debugging

Приложението използва структурирано логиране с различни нива:

- **DEBUG**: Детайлна информация за debugging
- **INFO**: Обща информация за операции
- **WARNING**: Предупреждения за потенциални проблеми
- **ERROR**: Грешки, които изискват внимание

Логовете се записват в конзолата и могат да се конфигурират за файл.

### Environment променливи

```bash
# Database
DATABASE_URL=sqlite:///instance/volunteers.db

# Email (Zoho SMTP)
MAIL_SERVER=smtp.zoho.eu
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=contact@helpchain.live
MAIL_PASSWORD=your_password

# Security
SECRET_KEY=your_secret_key
FLASK_ENV=development

# AI Services
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key

# Admin
ADMIN_EMAIL=admin@helpchain.live
```

## 🧪 Тестване

### Testing database notes (workaround)

During development and tests the project historically used a module-level
SQLAlchemy engine which caused duplicate engine/session issues with
Flask-SQLAlchemy (different in-memory SQLite connections). To avoid
test flakiness two runtime flags are supported:

- `HELPCHAIN_TEST_DEBUG=1` — when set, `backend.extensions` will print
   diagnostic messages useful for CI debugging. Defaults to off.
- `HELPCHAIN_MODULE_DB_URL` — if set to a DB URL (for example
   `sqlite:///./hc_test.db`), the models module will create and bind a
   local engine at import time. This is provided as a temporary
   compatibility mode for scripts/tests that require a module-level
   database. Prefer configuring the Flask app and letting
   `backend.extensions` bind the session in normal runs.

We plan a long-term refactor to remove module-level engines entirely
(see `backend/models.py` and `backend/extensions.py`) so tests and the
application share a single SQLAlchemy registry. For now, the above
flags provide a safe migration path and reproducible test runs.

### Unit тестове

```bash
# Стартирайте всички тестове
pytest

# С покритие
pytest --cov=backend --cov-report=html

# Конкретен тест
pytest tests/test_app.py::test_home_page
```

### Integration тестове

```bash
# Тестове с база данни
pytest tests/test_database.py

# Email тестове (mocked)
pytest tests/test_email.py
```

### Admin credentials за тестване

За тестване на admin панела използвайте следните credentials:

- **Username:** `admin`
- **Password:** стойността на `ADMIN_PASSWORD` от `.env` файла (по подразбиране: `Admin123`)

**Пример за тестване на login:**

```bash
# Стартирайте приложението
python backend/appy.py

# В друг терминал тествайте login
python -c "
import requests
response = requests.post('http://127.0.0.1:5000/admin/login',
                        data={'username': 'admin', 'password': 'YOUR_ADMIN_PASSWORD'},
                        allow_redirects=False)
print('Status:', response.status_code)
"
```

### Performance тестване

```bash
# Load testing с locust
pip install locust
locust -f tests/locustfile.py
```

## 🚀 Деплоймънт

### Render (препоръчително)

1. **Свържете GitHub репозитория**
2. **Настройте environment променливи**
3. **Изберете Python версия 3.12+**
4. **Build command:**
   ```bash
   pip install -r requirements.txt
   ```
5. **Start command:**
   ```bash
   uvicorn backend.helpchain-backend.src.asgi:asgi_app --host 0.0.0.0 --port $PORT
   ```

### Локален production

```bash
# С Gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 backend.helpchain-backend.src.asgi:app

# С Uvicorn
uvicorn backend.helpchain-backend.src.asgi:asgi_app --host 0.0.0.0 --port 8000 --workers 4
```

### Preview здравни проверки (Vercel)

- Каноничен health endpoint за прегледи: `/health`.
- `/api/_health` може да бъде 404, ако Project-level Routes в Vercel засенчват repo `vercel.json`.
- Smoke скриптът (`scripts/smoke.ps1`) третира `/api/_health = 404` като soft warning, когато `/health = 200`.
- Ако желаете и `/api/_health` да е 200, добавете в Project Settings → Routing (Vercel): правило най-отгоре `^/api/_health$ → api/_health.js`.


## 🤝 Принос

1. Fork-нете проекта
2. Създайте feature branch: `git checkout -b feature/amazing-feature`
3. Commit-нете промените: `git commit -m 'Add amazing feature'`
4. Push-нете към branch-a: `git push origin feature/amazing-feature`
5. Отворете Pull Request

### Code style

- Използвайте Black за форматиране
- Ruff за linting
- Pre-commit hooks за автоматична проверка
- Пишете тестове за нов функционал

## 📞 Контакт

- **Email:** contact@helpchain.live
- **Website:** https://helpchain.live
- **GitHub:** [@stellababy2004](https://github.com/stellababy2004)

**Разработено от:** Stella Barbarella

## 🔐 Удостоверяване на доброволци (Volunteer authentication)

Доброволците в HelpChain използват passwordless вход с еднократен код, изпратен по имейл. Основни бележки:

- Паролният вход (`/api/login`) не е предназначен за ролята `volunteer` и опит за стандартен паролен вход може да върне 401 при грешни данни.
- Администраторските акаунти (`AdminUser`) имат отделна политика за пароли и 2FA и не са обект на passwordless потока.
- За локално тестване или миграции има помощни скриптове в `backend/scripts/` — например `set_user_password.py` (за задаване на парола в dev среда) и `list_users.py` (за преглед на потребители).

Ако е нужно да промениш политиката за удостоверяване (например да позволиш паролен вход за доброволци), промени логиката в `backend/app.py` (рут `/api/login`).

## 📄 Лиценз

Този проект е лицензиран под MIT License - вижте [LICENSE](LICENSE) файла за детайли.

---

⭐ Ако харесвате проекта, не забравяйте да го звездайте!
