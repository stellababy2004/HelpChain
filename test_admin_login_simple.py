#!/usr/bin/env python3
import os
import sys

import requests

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))


def test_admin_login():
    """Test admin login functionality"""
    try:
        # Test GET request to admin login page
        response = requests.get("http://127.0.0.1:8000/admin_login")
        print(f"GET /admin_login: {response.status_code}")

        if response.status_code != 200:
            print("Admin login page not accessible")
            return False

        # Test POST request with correct credentials
        data = {"username": "admin", "password": "admin123"}
        response = requests.post("http://127.0.0.1:8000/admin_login", data=data, allow_redirects=False)

        print(f"POST /admin_login: {response.status_code}")
        print(f"Location header: {response.headers.get('location', 'None')}")

        if response.status_code == 302 and "admin_dashboard" in response.headers.get("location", ""):
            print("Admin login successful!")
            return True
        else:
            print("Admin login failed")
            return False

    except Exception as e:
        print(f"Error testing admin login: {e}")
        return False


if __name__ == "__main__":
    success = test_admin_login()
    sys.exit(0 if success else 1)
