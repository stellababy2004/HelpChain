#!/usr/bin/env python3
"""
Test script to verify volunteer registration validation fixes
"""

import requests
import json


def test_volunteer_registration():
    """Test the volunteer registration endpoint with various inputs"""

    base_url = "http://localhost:5000"  # Adjust if running on different port

    # First test if the app is responding
    print("Testing if app is responding...")
    try:
        response = requests.get(f"{base_url}/")
        print(f"GET / Status: {response.status_code}")
    except Exception as e:
        print(f"App not responding: {e}")
        return

    test_cases = [
        {
            "name": "Test Volunteer",
            "email": "test@example.com",
            "phone": "123456789",
            "location": "Sofia",
        },
        {
            "name": "",  # Empty name - should fail
            "email": "test2@example.com",
            "phone": "123456789",
            "location": "Sofia",
        },
        {
            "name": "Test Volunteer 2",
            "email": "",  # Empty email - should fail
            "phone": "123456789",
            "location": "Sofia",
        },
        {
            "name": "Test Volunteer 3",
            "email": "invalid-email",  # Invalid email - should fail
            "phone": "123456789",
            "location": "Sofia",
        },
    ]

    for i, test_data in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i} ---")
        print(f"Data: {test_data}")

        try:
            response = requests.post(
                f"{base_url}/volunteer_register", data=test_data, allow_redirects=False
            )

            print(f"Status Code: {response.status_code}")

            if response.status_code == 302:  # Redirect on success
                print("✓ SUCCESS: Registration successful (redirect)")
            elif response.status_code == 200:  # Form re-displayed with error
                print("✓ VALIDATION: Form re-displayed (validation error expected)")
            elif response.status_code == 500:
                print("✗ ERROR: 500 Internal Server Error")
            else:
                print(f"? UNKNOWN: Status {response.status_code}")

        except requests.exceptions.ConnectionError:
            print("✗ CONNECTION ERROR: Cannot connect to server")
            print("Make sure the Flask app is running on the correct port")
            break
        except Exception as e:
            print(f"✗ EXCEPTION: {e}")


if __name__ == "__main__":
    test_volunteer_registration()
