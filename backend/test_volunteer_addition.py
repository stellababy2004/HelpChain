#!/usr/bin/env python3
"""
Test script to verify volunteer addition functionality works after permission fixes.
"""
import json

import requests
from flask import Flask


def test_volunteer_addition():
    """Test the volunteer addition functionality"""
    base_url = "http://127.0.0.1:5000"

    # Create a session to maintain cookies
    session = requests.Session()

    print("Testing volunteer addition functionality...")

    # First, login as admin
    print("1. Logging in as admin...")
    login_data = {"username": "admin", "password": "Admin123"}

    try:
        response = session.post(f"{base_url}/admin_login", data=login_data)
        print(f"Login response status: {response.status_code}")

        # Check if login was successful by looking for dashboard content or redirect
        if (
            response.status_code == 302
            or "Админ панел" in response.text
            or "admin_dashboard" in response.text
        ):
            print("✓ Admin login successful")
        else:
            print("Login failed - checking response content...")
            print(response.text[:500])
            return False

        # Now try to access the add volunteer page
        print("2. Accessing add volunteer page...")
        response = session.get(f"{base_url}/admin_volunteers/add")
        print(f"Add volunteer page response status: {response.status_code}")

        if response.status_code != 200:
            print("Failed to access add volunteer page")
            print(response.text[:500])
            return False

        print("✓ Add volunteer page accessible")

        # Check if we're still logged in by looking at the response
        if "Вход за админ" in response.text or "admin_login" in response.text:
            print("Session lost - redirected to login page")
            return False

        print("✓ Session maintained")

        # Now try to add a volunteer
        print("3. Adding a test volunteer...")
        volunteer_data = {
            "name": "Test Volunteer",
            "email": "test@example.com",
            "phone": "+359123456789",
            "location": "Sofia",
        }

        response = session.post(f"{base_url}/admin_volunteers/add", data=volunteer_data)
        print(f"Add volunteer response status: {response.status_code}")

        if response.status_code == 302:  # Should redirect after successful addition
            print("✓ Volunteer addition successful (redirected)")
            return True
        else:
            print("Volunteer addition failed")
            print(response.text[:500])
            return False

    except Exception as e:
        print(f"Error during testing: {e}")
        return False


if __name__ == "__main__":
    success = test_volunteer_addition()
    if success:
        print(
            "\n🎉 All tests passed! Volunteer addition functionality is working correctly."
        )
    else:
        print("\n❌ Tests failed. There may still be issues with volunteer addition.")
