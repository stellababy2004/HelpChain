# [![CI](https://github.com/stellababy2004/HelpChain.bg/actions/workflows/ci.yml/badge.svg)](https://github.com/stellababy2004/HelpChain.bg/actions/workflows/ci.yml)
# HelpChain – Social & Healthcare Support Platform

🌍 Languages: [English](README.md) | [Български](README.bg.md) | [Français](README.fr.md)

[![Website](https://img.shields.io/badge/Live%20Demo-helpchain.live-green)](https://helpchain.live)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0+-lightgrey.svg)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**HelpChain** is a Flask-based web platform designed to connect people in need with volunteers and professionals who can provide real-world assistance.  
The project focuses on reliability, security, multilingual support, and production-grade operational guarantees.

---

## 🌐 Live Website

➡️ **https://helpchain.live**

---

## 🎯 Project Goals

- Centralized request management for social & healthcare support
- Volunteer coordination and task assignment
- Secure admin operations with role-based access and 2FA
- Multilingual, accessible, and privacy-aware communication
- Production-ready CI, database sanity checks, and schema drift protection

---

## ✨ Key Features

### Users
- Submit help requests via structured forms
- Multilingual UI (BG / EN / FR)
- Mobile-friendly, accessible interface
- Secure CSRF-protected flows

### Volunteers
- Passwordless authentication via email
- Task dashboard and status tracking
- Geolocation-based matching
- Email notifications

### Administrators
- Dedicated admin authentication & 2FA
- Volunteer and request management
- Analytics and audit logs
- Role & permission system

---

## 🛠 Tech Stack

| Layer        | Technology                              |
|-------------|------------------------------------------|
| Backend     | Flask 3.x                                |
| ORM         | SQLAlchemy + Flask-SQLAlchemy            |
| Database    | SQLite (dev/CI), PostgreSQL (production) |
| Auth        | Flask-Login, email-based 2FA             |
| i18n        | Flask-Babel                              |
| Security    | Flask-Limiter, CSRF, Talisman            |
| CI          | GitHub Actions                           |
| Deployment  | Uvicorn + Render                         |

---

## 🏗 Architecture Overview

backend/
├── models.py # ORM models
├── extensions.py # Shared Flask extensions
├── helpchain-backend/src/
│ ├── app.py # App factory (ASGI)
│ ├── routes/ # Blueprints
│ ├── controllers/ # Business logic
│ ├── templates/ # Jinja2 templates
│ └── static/ # Frontend assets
scripts/
├── schema_drift_guard.py # DB schema verification
├── db_crud_smoke.py # CRUD rollback tests

---

## 🧪 Testing & CI Guarantees

The project includes **production-grade database safety checks**:

- Schema Drift Guard (ORM vs real DB)
- CRUD smoke tests with transaction rollback
- CI pipeline halts immediately on drift or DB inconsistency

CI order:
1. Initialize test database
2. Schema drift guard
3. CRUD smoke tests (rollback)
4. Pytest

---

## 🚀 Deployment

**Recommended:** Render  
**ASGI entrypoint:**
```bash
uvicorn backend.helpchain-backend.src.asgi:asgi_app --host 0.0.0.0 --port $PORT
```

📄 License

MIT License – see LICENSE

Author: Stella Barbarella
Website: https://helpchain.live
---

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
- **Password:** стойността на `ADMIN_PASSWORD` от `.env` файла (по подразбиране: ``)

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


## 🚦 Routing & Deployment Policy

> Source of truth: виж vercel.json в корена на репото.

**Routing policy (canonical):**

- explicit-only endpoints
- 404 by default
- контролирано добавяне на нови маршрути
- детерминирано поведение (без ghost bugs)

**Препоръка за употреба:**
- Остави този текст във vercel.json като коментар (source of truth).
- Копирай 1:1 в README.md или docs/deployment.md под секция “Routing & Deployment Policy”.
- Ако имаш PR – сложи го и в PR description (като context, не като шум).

**Checklist за стабилност:**
- /api/_health → 200
- /health → 200
- unknown route → 404

**Твърдо мнение:**
Преместваме “поведение” от имплицитно към договорно. Това е разликата между “работи сега” и “работи след 6 месеца без драма”.

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

## Acceptance Checklist — Vercel Protected Preview Smoke (Production-grade)

- [x] **No browser required**: Smoke runs fully automated via cookie-jar flow in `smoke.ps1` (no SSO/manual steps).
- [x] **Canonical health OK**: `GET /health` returns **200**.
- [x] **Deterministic 404**: A clearly invalid route (e.g. `/__smoke_404__`) returns **404**.
- [x] **Secret hygiene**: Bypass token is stored as a **GitHub Actions secret** (not a workflow input) and is never printed in logs.
- [x] **URL redaction**: Logs do not include bypass query parameters used to set the cookie.
- [x] **Workflow resilience**: The job has a sensible **timeout** and uses **concurrency** to avoid overlapping runs.
- [x] *(Optional policy)* **`/api/_health` behavior**: Treated as optional (**200 or 404**) as long as `/health` is **200**.

Pinning Actions by SHA — next step (what “done” looks like)

Критериите за “supply-chain done”:

- uses: actions/checkout@v4 → pinned full SHA
- setup-python, cache, и всякакви други uses: → pinned full SHA
- (ако имаш composite actions) → pinned versions or SHAs

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

<!-- chore: trigger vercel preview build (no-op) -->
