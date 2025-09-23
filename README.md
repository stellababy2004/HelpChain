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
| Component        | Technology       |
|------------------|------------------|
| Backend          | Flask (Python)   |
| Email            | Flask-Mail + Zoho SMTP |
| UI Templates     | Jinja2           |
| i18n             | Flask-Babel      |
| Database         | SQLite + SQLAlchemy |
| Deployment       | Render           |
| Admin UI         | Flask-Admin      |
| Version Control  | Git + GitHub     |

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

## 🌍 Multilingual Support

HelpChain поддържа многоезичност чрез [Flask-Babel](https://python-babel.github.io/flask-babel/).

### Добавяне/Обновяване на преводи

1. **Извлечи и обнови преводите:**
   ```bash
   python babel_update.py
   ```
   Това ще генерира/обнови файловете за всички езици в папка `translations/`.

2. **Редактирай преводите:**
   - Намери `.po` файловете в `translations/<lang>/LC_MESSAGES/messages.po`
   - Добави или редактирай преводите с текстов редактор.

3. **Компилирай преводите:**
   ```bash
   python babel_update.py
   ```
   Скриптът автоматично компилира `.mo` файловете.

4. **Добави нов език:**
   ```bash
   python babel_update.py es
   ```
   Това ще създаде превод за испански (`es`).

### Как работи преводът в шаблоните

Във всички Jinja2 шаблони текстовете са оградени с:
```html
{{ _('Текст за превод') }}
```
Това позволява автоматично превключване на езика според избора на потребителя.

---

## 📬 Contact
Email: [contact@helpchain.live](mailto:contact@helpchain.live)

Developed by **Stella Barbarella** – [stellabarbarella.com](https://stellabarbarella.com)
