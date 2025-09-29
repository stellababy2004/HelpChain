# HelpChain – Social & Health Support Platform

[![Website](https://img.shields.io/badge/Live%20Demo-helpchain.live-green)](https://helpchain-s2l5.onrender.com)

HelpChain is a web application developed with Flask to connect people in need with volunteers who can provide help. The goal is to build a real-world platform to manage requests, assign volunteers, and support multilingual and accessible communication.

---

## 🌐 Live Site

➡️ [https://helpchain-s2l5.onrender.com](https://helpchain-s2l5.onrender.com)

---

## 📁 Project Structure

```
HelpChain/
├── backend/
│   ├── app.py
│   ├── models.py
│   ├── extensions.py
│   ├── templates/
│   │   ├── index.html
│   │   ├── register.html
│   │   ├── submit_request.html
│   │   └── email_templates/
│   │       ├── welcome_email.html
│   │       └── admin_notification.html
├── run.py
├── requirements.txt
```

---

## ⚙️ Features

- 📨 User registration with welcome email
- 🔔 Admin notification email on new signup
- 🌍 Multilingual support with Flask-Babel
- 📥 Form for submitting help requests
- 🛠️ Flask Admin (installed, setup in progress)
- 🔐 Configuration for secure email via Zoho SMTP

---

## 📦 Technologies Used

| Component       | Technology             |
| --------------- | ---------------------- |
| Backend         | Flask (Python)         |
| Email           | Flask-Mail + Zoho SMTP |
| UI Templates    | Jinja2                 |
| i18n            | Flask-Babel            |
| Database        | SQLite + SQLAlchemy    |
| Deployment      | Render                 |
| Admin UI        | Flask-Admin            |
| Version Control | Git + GitHub           |

---

## 🚀 Deployment (Render)

The app is deployed with Gunicorn on Render. Run command:

```bash
gunicorn backend.app:app
```

Python 3.13 is specified by default.

---

## 🧭 Roadmap

- [ ] Setup Flask-Admin interface
- [ ] Add login system (volunteers/admins)
- [ ] Track email logs in database
- [ ] Allow users to choose language
- [ ] Connect to custom domain: `helpchain.live`
- [ ] Make frontend fully mobile-friendly
- [ ] Add volunteer dashboard with task status

---

## Releases

### v0.1.0 — 2025-09-29

Initial test-stable release — 13 passing tests.

Highlights

- Refactored and stabilized unit tests (mocked HTTP for chatbot).
- Welcome email test made safe by mocking SMTP.
- Added conftest.py with fixtures and PYTHONPATH fixes for tests.
- LICENSE (MIT) added and tag v0.1.0 created.
- Pre-commit hooks (black, ruff) configured and passing.

---

## 📬 Contact

Email: [contact@helpchain.live](mailto:contact@helpchain.live)

Developed by **Stella Barbarella** – [stellabarbarella.com](https://stellabarbarella.com)

---

## Бърз старт (локално)

- Препоръчителна Python: 3.12
- Създай и активирай virtualenv:
  ```
  py -3.12 -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```
- Инсталирай зависимости:
  ```
  pip install --upgrade pip
  pip install -r backend/helpchain-backend/requirements.txt
  pip install pytest requests
  ```
- Стартирай приложението (dev):
  ```
  set FLASK_APP=backend.app
  set FLASK_ENV=development
  flask run
  ```
  или за production (gunicorn):
  ```
  gunicorn backend.app:app
  ```

---

## Структура

- backend/ — основен Flask код, templates, статични файлове
- backend/helpchain-backend/src — (модул за deployed package)
- scripts/ — помощни скриптове
- tests/ — unit/integration тестове

---

## Важни бележки

- Актуализирай Python версията в документацията и в Render (3.12 препоръчвам).
- Добави необходимите ENV променливи (.env): MAIL\_\*, DATABASE_URL, OPENAI_API_KEY (ако е нужно).
- Ignore: добави `node_modules/.cache/prettier/` и `node_modules/` в `.gitignore`.

---

## Тестове

```
pytest -q
```

---

## Контакт

Stella Barbarella — contact@helpchain.live

---

## Лиценз

Добави LICENSE (MIT/друга), ако искаш публично споделяне.
