 HelpChain – Social & Health Support Platform

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
- 🛠️ Admin panel for managing requests and volunteers
- 🔐 Login system for volunteers and admins
- 📊 Volunteer dashboard with task status
- 📷 Profile management with photo upload
- 🎨 Responsive UI with Font Awesome icons
- 🔒 Secure configuration for email via Zoho SMTP

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
| Admin UI        | Custom admin panel     |
| Version Control | Git + GitHub           |
| ASGI            | Uvicorn                |

---

## 🚀 Deployment (Render)

The app is deployed with Uvicorn on Render. Run command:

```bash
uvicorn backend.helpchain-backend.src.asgi:asgi_app --host 0.0.0.0 --port 10000
```

Python 3.13 is specified by default.

---

## 🧭 Roadmap

- [ ] Setup Flask-Admin interface
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
Python 3.12 is specified.

🧭 Roadmap
 Setup admin panel for managing requests/volunteers
 Add login system (volunteers/admins)
 Add volunteer dashboard with task status
 Implement profile management with photo upload
 Improve UI/UX with Font Awesome and responsive design
 Track email logs in database
 Allow users to choose language
 Connect to custom domain: helpchain.live
 Make frontend fully mobile-friendly
 Add API documentation
📡 API Endpoints
GET / - Home page
GET /login - Login page
POST /login - Authenticate user
GET /register - Registration page
POST /register - Register new user
GET /dashboard - Volunteer dashboard
GET /profile - User profile
POST /profile - Update profile
GET /admin - Admin panel (admin only)
GET /about - About page
POST /submit_request - Submit help request
Releases
v0.2.0 — 2025-10-02
Updated release with new features.

Highlights

Implemented admin panel for managing requests and volunteers.
Added login system for volunteers and admins.
Created volunteer dashboard with task status.
Added profile management with photo upload.
Improved UI/UX with Font Awesome icons and responsive design.
Published project on GitHub.
Fixed pre-commit hooks and code formatting.
v0.1.0 — 2025-09-29
Initial test-stable release — 13 passing tests.

Highlights

Refactored and stabilized unit tests (mocked HTTP for chatbot).
Welcome email test made safe by mocking SMTP.
Added conftest.py with fixtures and PYTHONPATH fixes for tests.
LICENSE (MIT) added and tag v0.1.0 created.
Pre-commit hooks (black, ruff) configured and passing.
🤝 Contributing
Fork the repository.
Create a feature branch: git checkout -b feature-name.
Commit changes: git commit -m "Add feature".
Push to branch: git push origin feature-name.
Open a Pull Request.
📬 Contact
Email: contact@helpchain.live

Developed by Stella Barbarella – stellabarbarella.com

py -3.12 -m venv .venv
[Activate.ps1](http://_vscodecontentref_/3)

