#!/usr/bin/env python3
"""
Test script for email functionality
"""
import os

from backend.appy import app, send_email_2fa_code


def test_email():
    """Test email sending functionality"""
    print("Testing email functionality...")

    with app.app_context():
        print("App context established")
        print(f"Mail server: {app.config.get('MAIL_SERVER')}")
        print(f"Mail port: {app.config.get('MAIL_PORT')}")
        print(f"Mail username: {app.config.get('MAIL_USERNAME')}")
        print(f"Mail TLS: {app.config.get('MAIL_USE_TLS')}")

        # Test sending email
        print("Attempting to send email...")
        result = send_email_2fa_code("123456", "127.0.0.1", "Test User Agent")
        print(f"Email send result: {result}")

        # Check if email was saved to file (fallback)
        if os.path.exists("backend/sent_emails.txt"):
            with open("backend/sent_emails.txt", encoding="utf-8") as f:
                content = f.read()
                if "123456" in content:
                    print("Email was saved to fallback file - SMTP failed")
                else:
                    print(
                        "Email was NOT saved to fallback file - might have been sent successfully"
                    )

        # Convert script-like boolean return into an assertion for pytest
        assert result, f"send_email_2fa_code returned falsy result: {result}"


if __name__ == "__main__":
    test_email()
