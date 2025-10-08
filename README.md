 HelpChain – Social & Health Support Platform

[![Website](https://img.shields.io/badge/Live%20Demo-helpchain.live-green)](https://helpchain-s2l5.onrender.com)

HelpChain is a web application developed with Flask to connect people in need with volunteers who can provide help. The goal is to build a real-world platform to manage requests, assign volunteers, and support multilingual and accessible communication.

---

## 🌐 Live Site

➡️ [https://helpchain-s2l5.onrender.com](https://helpchain-s2l5.onrender.com)

---

## 📁 Project Structure

HelpChain/ ├── backend/ │ └── helpchain-backend/ │ ├── src/ │ │ ├── app.py │ │ ├── models.py │ │ ├── extensions.py │ │ ├── routes/ │ │ │ ├── analytics.py │ │ │ └── api.py │ │ ├── controllers/ │ │ │ └── helpchain_controller.py │ │ └── asgi.py │ ├── templates/ │ │ ├── base.html │ │ ├── index.html │ │ ├── login.html │ │ ├── register.html │ │ ├── dashboard.html │ │ ├── profile.html │ │ ├── admin_dashboard.html │ │ ├── about.html │ │ └── submit_request.html │ ├── static/ │ │ ├── css/ │ │ ├── js/ │ │ └── uploads/ │ └── requirements.txt ├── tests/ ├── .gitignore ├── README.md └── run.py

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
<<<<<<< Updated upstream
```
=======
>>>>>>> Stashed changes

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

<<<<<<< Updated upstream
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
=======
Highlights
>>>>>>> Stashed changes

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

Бърз старт (локално)

Препоръчителна Python: 3.12

Създай и активирай virtualenv:

py -3.12 -m venv .venv[Activate.ps1](http://_vscodecontentref_/4)
py -3.12 -m venv .venv
[Activate.ps1](http://_vscodecontentref_/4)

Инсталирай зависимости:
pip install -r [requirements.txt](http://_vscodecontentref_/5)
pip install Pillow --only-binary=all

Стартирай приложението:
uvicorn backend.helpchain-backend.src.asgi:asgi_app --host 127.0.0.1 --port 8003

Структура
backend/helpchain-backend/src — основен Flask код
backend/helpchain-backend/templates — HTML templates
backend/helpchain-backend/static — CSS, JS, images
tests/ — unit/integration тестове
Важни бележки
Актуализирай Python версията в документацията и в Render (3.12 препоръчвам).
Добави необходимите ENV променливи (.env): MAIL_*, DATABASE_URL.
Ignore: добави node_modules/.cache/prettier/ и node_modules/ в .gitignore.

Тестове
pytest -q
Контакт
Stella Barbarella — contact@helpchain.live

Лиценз
This project is licensed under the MIT License - see the LICENSE file for details.


<<<<<<< Updated upstream
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

=======
```
>>>>>>> Stashed changes
