#!/usr/bin/env python3
"""
Simple test for admin login using urllib
"""

import http.cookiejar
import urllib.parse
import urllib.request


def test_admin_login():
    # Create cookie jar
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    # Prepare login data
    login_data = urllib.parse.urlencode(
        {"username": "admin", "password": "test-password"}  # pragma: allowlist secret
    ).encode("utf-8")

    try:
        # Try to login
        print("Attempting admin login...")
        req = urllib.request.Request(
            "http://127.0.0.1:5000/admin/login", data=login_data
        )
        response = opener.open(req)

        print(f"Login response status: {response.status}")
        print(f"Login response URL: {response.url}")

        # Check if redirected to dashboard
        if response.url.endswith("/admin_dashboard"):
            print("SUCCESS: Login worked and redirected to dashboard!")
        else:
            print(
                f"Login response content: {response.read().decode('utf-8', errors='ignore')[:500]}"
            )

        # Try to access dashboard
        print("\nAttempting to access dashboard...")
        req2 = urllib.request.Request("http://127.0.0.1:5000/admin_dashboard")
        response2 = opener.open(req2)

        print(f"Dashboard response status: {response2.status}")
        if response2.status == 200:
            print("SUCCESS: Dashboard accessible!")
        else:
            print("FAILED: Dashboard not accessible")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test_admin_login()

