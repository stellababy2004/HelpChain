#!/usr/bin/env python3
"""
Test script to simulate submitting a request and check email notification
"""
import os
import sys

from dotenv import load_dotenv

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

from flask import Flask
from flask_mail import Mail
from src.config import Config
from src.models import Request, db


def test_request_submission():
    """Test request submission with email notification"""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    mail = Mail(app)

    with app.app_context():
        # Create tables if they don't exist
        db.create_all()

        try:
            # Create a test request
            test_request = Request(
                name="Тестов Потребител",
                phone="+359 88 123 4567",
                email="test@example.com",
                location="sofia",
                category="food",
                description="Тестова заявка за храна",
                urgency="medium",
                status="pending",
            )

            db.session.add(test_request)
            db.session.commit()

            print(f"✅ Test request created with ID: {test_request.id}")

            # Test email notification
            def send_email_notification(req):
                # Check if email is in mock mode
                if os.environ.get("MAIL_MOCK", "").lower() in ["true", "1"]:
                    print(f"📧 [MOCK MODE] Email notification for request ID {req.id}:")
                    print("📧 Subject: Нова заявка за помощ в HelpChain")
                    print("📧 To: contact@helpchain.live")
                    print("📧 From: {}".format(app.config["MAIL_DEFAULT_SENDER"]))
                    print("📧 Body:")
                    print("    Нова заявка за помощ:")
                    print(f"    ID: {req.id}")
                    print(f"    Име: {req.name}")
                    print(f"    Имейл: {req.email}")
                    print(f"    Телефон: {req.phone}")
                    print(f"    Локация: {req.location}")
                    print(f"    Категория: {req.category}")
                    print(f"    Описание: {req.description}")
                    print(f"    Спешност: {req.urgency}")
                    print("✅ [MOCK MODE] Email logged successfully!")
                    return

                from flask_mail import Message

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
                    print(f"Email sent for request ID {req.id}")
                except Exception as e:
                    print(f"Email send failed: {e}")

            # Send email notification
            send_email_notification(test_request)

            print("✅ Test completed successfully!")
            print(
                "💡 If you see '[MOCK MODE]' messages above, email notifications are working in mock mode"
            )
            print(
                "💡 To enable real emails, remove MAIL_MOCK=true from .env file and configure proper SMTP settings"
            )

        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    test_request_submission()
