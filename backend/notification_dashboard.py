#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HelpChain Notification Dashboard
Web interface to view email notifications and requests
"""

import os
import sqlite3
from datetime import datetime
from flask import (
    Flask,
    render_template_string,
    redirect,
    url_for,
    flash,
)
from flask_mail import Mail, Message
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = "helpchain-notification-secret-key"

# Configure Flask-Mail
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.mailtrap.io")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", "587"))
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
app.config["MAIL_USE_SSL"] = os.getenv("MAIL_USE_SSL", "False").lower() == "true"
app.config["MAIL_DEFAULT_SENDER"] = os.getenv(
    "MAIL_DEFAULT_SENDER", "noreply@helpchain.live"
)

mail = Mail(app)

# Database setup
DB_PATH = "notifications.db"


def init_db():
    """Initialize the notifications database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS notifications
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT,
                  recipient TEXT,
                  subject TEXT,
                  content TEXT,
                  status TEXT,
                  smtp_error TEXT)"""
    )
    conn.commit()
    conn.close()


def save_notification_to_db(
    recipient, subject, content, status="saved", smtp_error=None
):
    """Save notification to database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """INSERT INTO notifications (timestamp, recipient, subject, content, status, smtp_error)
                 VALUES (?, ?, ?, ?, ?, ?)""",
        (datetime.now().isoformat(), recipient, subject, content, status, smtp_error),
    )
    conn.commit()
    conn.close()


def get_notifications(limit=50):
    """Get recent notifications from database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM notifications ORDER BY timestamp DESC LIMIT ?", (limit,))
    notifications = c.fetchall()
    conn.close()
    return notifications


# Initialize database
init_db()

# HTML Templates
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="bg">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HelpChain - Админ Панел Нотификации</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #2c3e50; text-align: center; margin-bottom: 30px; }
        .stats { display: flex; justify-content: space-around; margin-bottom: 30px; }
        .stat-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); text-align: center; }
        .stat-number { font-size: 2em; font-weight: bold; color: #3498db; }
        .stat-label { color: #7f8c8d; margin-top: 5px; }
        .notifications { background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden; }
        .notification-item { padding: 20px; border-bottom: 1px solid #ecf0f1; }
        .notification-item:last-child { border-bottom: none; }
        .notification-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .notification-time { color: #7f8c8d; font-size: 0.9em; }
        .notification-status { padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; }
        .status-saved { background: #f39c12; color: white; }
        .status-sent { background: #27ae60; color: white; }
        .status-failed { background: #e74c3c; color: white; }
        .notification-subject { font-weight: bold; color: #2c3e50; margin-bottom: 10px; }
        .notification-content { color: #34495e; line-height: 1.5; white-space: pre-wrap; background: #f8f9fa; padding: 15px; border-radius: 5px; font-family: monospace; }
        .refresh-btn { background: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-bottom: 20px; }
        .refresh-btn:hover { background: #2980b9; }
        .empty-state { text-align: center; color: #7f8c8d; padding: 40px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📧 HelpChain - Админ Панел Нотификации</h1>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{{ total_notifications }}</div>
                <div class="stat-label">Общо нотификации</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ sent_notifications }}</div>
                <div class="stat-label">Изпратени</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ saved_notifications }}</div>
                <div class="stat-label">Запазени</div>
            </div>
        </div>

        <button class="refresh-btn" onclick="location.reload()">🔄 Обнови</button>

        <div class="notifications">
            {% if notifications %}
                {% for notification in notifications %}
                <div class="notification-item">
                    <div class="notification-header">
                        <div class="notification-time">{{ notification[1] }}</div>
                        <div class="notification-status status-{{ notification[5] }}">{{ notification[5].upper() }}</div>
                    </div>
                    <div class="notification-subject">{{ notification[3] }}</div>
                    <div class="notification-content">{{ notification[4] }}</div>
                    {% if notification[6] %}
                    <div style="color: #e74c3c; margin-top: 10px; font-size: 0.9em;">
                        <strong>SMTP грешка:</strong> {{ notification[6] }}
                    </div>
                    {% endif %}
                </div>
                {% endfor %}
            {% else %}
                <div class="empty-state">
                    <h3>Няма нотификации</h3>
                    <p>Нотификациите ще се появят тук когато потребители подават заявки.</p>
                </div>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""


def send_email_notification(req):
    """Send email notification with database backup"""
    content = f"""Нова заявка за помощ:
ID: {req.id}
Име: {req.name}
Имейл: {req.email}
Телефон: {req.phone}
Локация: {req.location}
Категория: {req.category}
Описание: {req.description}
Спешност: {req.urgency}"""

    subject = "Нова заявка за помощ в HelpChain"

    # Try to send email
    msg = Message(
        subject=subject,
        recipients=["contact@helpchain.live"],
        sender=app.config["MAIL_DEFAULT_SENDER"],
        body=content,
    )

    smtp_error = None
    status = "saved"

    try:
        mail.send(msg)
        status = "sent"
        print(f"✅ Email sent successfully for request ID {req.id}")
    except Exception as e:
        smtp_error = str(e)
        print(f"⚠️  Email send failed, saving to database: {e}")

    # Save to database regardless
    save_notification_to_db(
        "contact@helpchain.live", subject, content, status, smtp_error
    )

    return status == "sent"


@app.route("/")
def dashboard():
    notifications = get_notifications()
    total = len(notifications)
    sent = len([n for n in notifications if n[5] == "sent"])
    saved = len([n for n in notifications if n[5] == "saved"])

    return render_template_string(
        DASHBOARD_TEMPLATE,
        notifications=notifications,
        total_notifications=total,
        sent_notifications=sent,
        saved_notifications=saved,
    )


@app.route("/test-notification")
def test_notification():
    """Add a test notification"""

    class MockRequest:
        def __init__(self):
            self.id = int(datetime.now().timestamp())
            self.name = "Тестов Администратор"
            self.email = "admin@helpchain.live"
            self.phone = "+359 88 123 4567"
            self.location = "София"
            self.category = "Системна проверка"
            self.description = "Тестова нотификация за проверка на системата"
            self.urgency = "Ниска"

    req = MockRequest()
    send_email_notification(req)

    flash("✅ Тестова нотификация е добавена!", "success")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    print("🚀 Starting HelpChain Notification Dashboard...")
    print("📧 Email configuration:")
    print(f"   MAIL_SERVER: {app.config['MAIL_SERVER']}")
    print(f"   MAIL_PORT: {app.config['MAIL_PORT']}")
    print(f"   MAIL_USERNAME: {app.config['MAIL_USERNAME']}")
    print(f"   MAIL_DEFAULT_SENDER: {app.config['MAIL_DEFAULT_SENDER']}")
    print("\n🌐 Dashboard: http://127.0.0.1:5001")
    print("🧪 Test notification: http://127.0.0.1:5001/test-notification")
    print("📊 Database: notifications.db")
    app.run(debug=True, host="127.0.0.1", port=5001)
