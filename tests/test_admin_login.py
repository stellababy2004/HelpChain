#!/usr/bin/env python3
"""
Test admin login with email 2FA
"""

import os
import re
import time

import requests


def test_admin_login():
    """Test the complete admin login flow with email 2FA"""
    base_url = "http://127.0.0.1:5000"

    # Start a session to maintain cookies
    session = requests.Session()

    print("Testing admin login with email 2FA...")

    # Step 1: Get the login page to establish session
    print("1. Getting login page...")
    response = session.get(f"{base_url}/admin/login")
    assert (
        response.status_code == 200
    ), f"Failed to get login page: {response.status_code}"

    print("2. Attempting login with credentials...")
    # Step 2: Post login credentials
    login_data = {
        "username": "admin",
        "password": os.getenv("ADMIN_PASSWORD", "Admin123"),
    }

    response = session.post(
        f"{base_url}/admin/login", data=login_data, allow_redirects=False
    )

    if response.status_code == 302:  # Redirect to email 2FA
        print("✓ Login successful, redirected to email 2FA")
        redirect_url = response.headers.get("Location")
        if "admin/email_2fa" in redirect_url:
            print("✓ Redirected to email 2FA page as expected")

            # Step 3: Check if email was sent (not saved to fallback file)
            print("3. Checking if email was sent...")
            time.sleep(2)  # Wait a bit for email processing

            try:
                with open("backend/sent_emails.txt", encoding="utf-8") as f:
                    content = f.read()
                    # Get the last email in the file
                    emails = content.split("=" * 50)
                    if emails:
                        last_email = emails[-1].strip()
                        if last_email:
                            # Extract the verification code from the last email
                            code_match = re.search(
                                r"Код за верификация: (\d{6})", last_email
                            )
                            if code_match:
                                code = code_match.group(1)
                                print(
                                    f"✓ Found verification code in fallback file: {code}"
                                )
                                print(
                                    "⚠ Email was saved to fallback - SMTP may have failed"
                                )
                                assert (
                                    False
                                ), f"Verification code found in fallback file ({code}); SMTP may have failed"
                            else:
                                print(
                                    "✓ No verification code found in recent emails - checking if sent via SMTP..."
                                )
                        else:
                            print(
                                "✓ No emails in fallback file - email likely sent via SMTP!"
                            )
                    else:
                        print(
                            "✓ No emails in fallback file - email likely sent via SMTP!"
                        )

            except FileNotFoundError:
                print("✓ sent_emails.txt not found - email likely sent via SMTP!")

            print("✓ Admin login with email 2FA appears to be working!")
            # success - test functions must return None
            return
        else:
            print(f"✗ Unexpected redirect: {redirect_url}")
            assert False, f"Unexpected redirect: {redirect_url}"
    else:
        print(f"✗ Login failed with status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        assert False, f"Login failed with status: {response.status_code}"


if __name__ == "__main__":
    success = test_admin_login()
    print(f"\nTest result: {'SUCCESS' if success else 'FAILED'}")
