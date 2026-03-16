#!/usr/bin/env python3
"""Test admin login and dashboard access with real server"""

import time

import requests


def test_real_server():
    time.sleep(3)  # Wait for server to start

    try:
        # Create a session to maintain cookies
        session = requests.Session()

        # Test login
        print("Testing login...")
        login_data = {"username": "admin", "password": "test-password"}
        response = session.post(
            "http://localhost:8000/admin/login", data=login_data, allow_redirects=False
        )
        print(f"Login status: {response.status_code}")
        print(f"Login redirect: {response.headers.get('Location')}")

        # Check cookies
        cookies = session.cookies.get_dict()
        print(f"Cookies after login: {cookies}")

        # Test dashboard access
        print("\nTesting dashboard access...")
        dashboard_response = session.get(
            "http://localhost:8000/admin/dashboard", allow_redirects=False
        )
        print(f"Dashboard status: {dashboard_response.status_code}")
        print(f"Dashboard redirect: {dashboard_response.headers.get('Location')}")

        if dashboard_response.status_code == 200:
            print("✓ SUCCESS: Dashboard accessible after login!")
        elif dashboard_response.status_code == 302 and "login" in str(
            dashboard_response.headers.get("Location", "")
        ):
            print("✗ FAILED: Dashboard redirects to login (session not working)")
        else:
            print(
                f"? UNKNOWN: Dashboard returned status {dashboard_response.status_code}"
            )

    except requests.exceptions.ConnectionError:
        print("❌ Server not running or connection failed")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    test_real_server()

