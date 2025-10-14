#!/usr/bin/env python3
"""
Test script for email functionality in HelpChain
"""
import os
import sys
from dotenv import load_dotenv

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

from flask import Flask
from flask_mail import Mail, Message
from src.config import Config


def test_email():
    """Test email sending functionality"""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize mail
    mail = Mail(app)

    with app.app_context():
        try:
            # Create a test message
            msg = Message(
                subject="Test Email from HelpChain",
                recipients=["contact@helpchain.live"],
                sender=app.config["MAIL_DEFAULT_SENDER"],
                body="""
                This is a test email from HelpChain application.

                If you receive this email, the email configuration is working correctly.

                Test details:
                - MAIL_SERVER: {server}
                - MAIL_PORT: {port}
                - MAIL_USERNAME: {username}
                - MAIL_USE_TLS: {tls}
                """.format(
                    server=app.config.get("MAIL_SERVER"),
                    port=app.config.get("MAIL_PORT"),
                    username=app.config.get("MAIL_USERNAME"),
                    tls=app.config.get("MAIL_USE_TLS"),
                ),
            )

            # Send the email
            mail.send(msg)
            print("✅ Test email sent successfully!")
            print("📧 Sent to: contact@helpchain.live")
            print(f"📨 From: {app.config['MAIL_DEFAULT_SENDER']}")
            print(f"🖥️  Server: {app.config['MAIL_SERVER']}:{app.config['MAIL_PORT']}")

        except Exception as e:
            print(f"❌ Email sending failed: {e}")
            print("🔧 Please check your email configuration in .env file")
            print("📋 Current config:")
            print(f"   MAIL_SERVER: {app.config.get('MAIL_SERVER')}")
            print(f"   MAIL_PORT: {app.config.get('MAIL_PORT')}")
            print(f"   MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
            print(f"   MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS')}")


if __name__ == "__main__":
    test_email()
