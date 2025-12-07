#!/usr/bin/env python3
"""
Test script for HelpChain email notifications
Tests both file saving and SMTP sending functionality
"""

import os
import sys
from datetime import datetime

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from flask import Flask
from flask_mail import Mail, Message


def test_email_system():
    """Test the email notification system"""
    print("🧪 Testing HelpChain Email System")
    print("=" * 50)

    # Create Flask app
    app = Flask(__name__)

    # Load configuration from .env file
    try:
        from dotenv import load_dotenv

        load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    except ImportError:
        print("⚠️  python-dotenv not installed, using environment variables")

    # Configure Flask-Mail
    app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.mailtrap.io")
    app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", "587"))
    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
    app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
    app.config["MAIL_USE_SSL"] = os.getenv("MAIL_USE_SSL", "False").lower() == "true"
    app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER", "noreply@helpchain.live")

    mail = Mail(app)

    # Mock request object
    class MockRequest:
        def __init__(self):
            self.id = 999
            self.name = "Тестов Потребител"
            self.email = "test@example.com"
            self.phone = "+359 88 123 4567"
            self.location = "София"
            self.category = "Техническа помощ"
            self.description = "Това е тестова заявка за проверка на имейл системата"
            self.urgency = "Средна"

    req = MockRequest()

    with app.app_context():
        # Test file saving
        print("📁 Testing file saving...")
        email_content = f"""
Subject: Нова заявка за помощ в HelpChain
To: contact@helpchain.live
From: {app.config["MAIL_DEFAULT_SENDER"]}
Date: {datetime.now()}

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
                f.write(f"Email sent at: {datetime.now()}\n")
                f.write(email_content)
                f.write(f"{'=' * 50}\n")
            print("✅ Email saved to file successfully")
            print("📂 Check 'sent_emails.txt' for the email content")
        except Exception as e:
            print(f"❌ Failed to save email to file: {e}")

        # Test SMTP sending
        print("\n📧 Testing SMTP sending...")
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
            print("✅ Email sent successfully via SMTP")
            print("📧 Sent to: contact@helpchain.live")
        except Exception as e:
            print(f"⚠️  SMTP send failed, but file saving works: {e}")
            print("🔧 Email configuration details:")
            print(f"   MAIL_SERVER: {app.config.get('MAIL_SERVER')}")
            print(f"   MAIL_PORT: {app.config.get('MAIL_PORT')}")
            print(f"   MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
            print(f"   MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS')}")

    print("\n" + "=" * 50)
    print("🎯 Test completed!")
    print("💡 If SMTP fails, check your .env file and Mailtrap credentials")
    print("📁 Emails are saved to 'sent_emails.txt' as backup")


if __name__ == "__main__":
    test_email_system()
