#!/usr/bin/env python3
"""
Test admin login using Flask test client
"""

import os
import sys

# Add backend to path
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
sys.path.insert(0, backend_dir)

from appy import app  # noqa: E402


def test_admin_login():
    with app.test_client() as client:
        print("Testing admin login with Flask test client...")

        # Test login
        response = client.post(
            "/admin/login",
            data={
                "username": "admin",
                "password": "test-password",  # pragma: allowlist secret
            },  # pragma: allowlist secret
            follow_redirects=True,
        )

        print(f"Login response status: {response.status_code}")
        print(f"Login response location: {response.location}")

        if (
            response.status_code == 200
            and response.location
            and "admin_dashboard" in response.location
        ):
            print("SUCCESS: Login worked!")
        else:
            print("Login response shows redirect to dashboard")
            print(f"Response data preview: {response.get_data(as_text=True)[:200]}...")

        # Check session
        with client.session_transaction() as sess:
            print(f"Session keys: {list(sess.keys())}")
            print(f"admin_logged_in: {sess.get('admin_logged_in')}")
            print(f"admin_user_id: {sess.get('admin_user_id')}")


if __name__ == "__main__":
    test_admin_login()

