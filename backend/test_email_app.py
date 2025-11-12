#!/usr/bin/env python3
"""
Simple Flask app for testing HelpChain email notifications
"""

import datetime
import os

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template_string, request, url_for
from flask_mail import Mail, Message

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = "test-secret-key"

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

# Simple HTML template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="bg">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HelpChain - Тест на имейл нотификации</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; text-align: center; }
        form { margin-top: 20px; }
        label { display: block; margin: 10px 0 5px; font-weight: bold; }
        input, select, textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 16px; }
        textarea { height: 100px; resize: vertical; }
        button { background: #3498db; color: white; padding: 12px 30px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; margin-top: 20px; width: 100%; }
        button:hover { background: #2980b9; }
        .success { color: #27ae60; text-align: center; margin: 20px 0; }
        .error { color: #e74c3c; text-align: center; margin: 20px 0; }
        .info { background: #ecf0f1; padding: 15px; border-radius: 5px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 HelpChain - Тест на имейл нотификации</h1>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="{{ 'success' if category == 'success' else 'error' }}">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="info">
            <strong>ℹ️ Информация:</strong><br>
            Тази форма тества имейл нотификациите. Когато изпратите заявка, тя ще бъде записана във файл <code>sent_emails.txt</code> и ще се опита да изпрати имейл до <code>contact@helpchain.live</code>.
        </div>

        <form method="POST" action="/submit">
            <label for="name">Име:</label>
            <input type="text" id="name" name="name" required>

            <label for="email">Имейл:</label>
            <input type="email" id="email" name="email" required>

            <label for="phone">Телефон:</label>
            <input type="tel" id="phone" name="phone" required>

            <label for="location">Локация:</label>
            <input type="text" id="location" name="location" required>

            <label for="category">Категория:</label>
            <select id="category" name="category" required>
                <option value="Техническа помощ">Техническа помощ</option>
                <option value="Медицинска помощ">Медицинска помощ</option>
                <option value="Правна помощ">Правна помощ</option>
                <option value="Социална помощ">Социална помощ</option>
                <option value="Друга">Друга</option>
            </select>

            <label for="description">Описание:</label>
            <textarea id="description" name="description" required></textarea>

            <label for="urgency">Спешност:</label>
            <select id="urgency" name="urgency" required>
                <option value="Ниска">Ниска</option>
                <option value="Средна">Средна</option>
                <option value="Висока">Висока</option>
                <option value="Критична">Критична</option>
            </select>

            <button type="submit">🚀 Изпрати заявка</button>
        </form>
    </div>
</body>
</html>
"""


def send_email_notification(req):
    """Send email notification for new request"""
    # Save to file first
    email_content = f"""
Subject: Нова заявка за помощ в HelpChain
To: contact@helpchain.live
From: {app.config["MAIL_DEFAULT_SENDER"]}
Date: {datetime.datetime.now()}

Нова заявка за помощ:
ID: {req.id}
Име: {req.name}
Имейл: {req.email}
Телефон: {req.phone}
Локация: {req.location}
Категория: {req.category}
Описание: {req.description}
Спешност: {req.urgency}
"""

    try:
        with open("sent_emails.txt", "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 50}\n")
            f.write(f"Email sent at: {datetime.datetime.now()}\n")
            f.write(email_content)
            f.write(f"{'=' * 50}\n")
        print(f"✅ Email saved to file for request ID {req.id}")
    except Exception as e:
        print(f"❌ Failed to save email to file: {e}")

    # Try to send real email
    msg = Message(
        subject="Нова заявка за помощ в HelpChain",
        recipients=["contact@helpchain.live"],
        sender=app.config["MAIL_DEFAULT_SENDER"],
        body=f"""
        Нова заявка за помощ:
        ID: {req.id}
        Име: {req.name}
        Имейл: {req.email}
        Телефон: {req.phone}
        Локация: {req.location}
        Категория: {req.category}
        Описание: {req.description}
        Спешност: {req.urgency}
        """,
    )

    try:
        mail.send(msg)
        print(f"✅ Email sent successfully for request ID {req.id}")
        return True
    except Exception as e:
        print(f"⚠️  Email send failed, but saved to file: {e}")
        return False


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/submit", methods=["POST"])
def submit():
    # Mock request object
    class MockRequest:
        def __init__(self, form_data):
            self.id = 1000 + int(
                datetime.datetime.now().timestamp() % 1000
            )  # Simple ID generation
            self.name = form_data.get("name")
            self.email = form_data.get("email")
            self.phone = form_data.get("phone")
            self.location = form_data.get("location")
            self.category = form_data.get("category")
            self.description = form_data.get("description")
            self.urgency = form_data.get("urgency")

    req = MockRequest(request.form)

    # Send email notification
    email_sent = send_email_notification(req)

    if email_sent:
        flash(
            "✅ Заявката е изпратена успешно! Имейл нотификацията е доставена.",
            "success",
        )
    else:
        flash(
            "✅ Заявката е записана! Имейлът е запазен във файл (SMTP има проблеми, но системата работи).",
            "success",
        )

    return redirect(url_for("index"))


if __name__ == "__main__":
    print("🚀 Starting HelpChain Email Test Server...")
    print("📧 Email configuration:")
    print(f"   MAIL_SERVER: {app.config['MAIL_SERVER']}")
    print(f"   MAIL_PORT: {app.config['MAIL_PORT']}")
    print(f"   MAIL_USERNAME: {app.config['MAIL_USERNAME']}")
    print(f"   MAIL_DEFAULT_SENDER: {app.config['MAIL_DEFAULT_SENDER']}")
    print("\n🌐 Open http://127.0.0.1:5000 in your browser")
    print("📁 Emails will be saved to 'sent_emails.txt'")
    app.run(debug=True, host="127.0.0.1", port=5000)
