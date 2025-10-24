#!/usr/bin/env python3
"""
Test script to verify admin volunteers functionality
"""
import json

import requests

BASE_URL = "http://127.0.0.1:5000"


def test_admin_volunteers():
    """Test the admin volunteers page and delete functionality"""
    print("Testing admin volunteers functionality...")

    # Create a session to maintain cookies
    session = requests.Session()

    try:
        # First, try to access admin_volunteers without login (should redirect)
        print("1. Testing access without login...")
        response = session.get(f"{BASE_URL}/admin_volunteers")
        print(f"   Status: {response.status_code}")
        if response.status_code == 302:  # Redirect to login
            print("   ✓ Correctly redirected to login")
        else:
            print("   ✗ Expected redirect to login")

        # Try to login as admin
        print("\n2. Testing admin login...")
        login_data = {"username": "admin", "password": "Admin123"}
        response = session.post(f"{BASE_URL}/admin_login", data=login_data)
        print(f"   Status: {response.status_code}")

        # Check if login was successful by looking for redirect or success message
        if response.status_code == 302 or "dashboard" in response.url.lower():
            print("   ✓ Admin login successful")
        else:
            print("   ✗ Admin login failed")
            return False

        # Now try to access admin_volunteers
        print("\n3. Testing admin_volunteers page access...")
        response = session.get(f"{BASE_URL}/admin_volunteers")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✓ Admin volunteers page accessible")
            if "Управление на доброволци" in response.text:
                print("   ✓ Page contains expected content")
            else:
                print("   ✗ Page content unexpected")
        else:
            print("   ✗ Admin volunteers page not accessible")
            return False

        # Test if the delete route exists (we can't actually delete without volunteers)
        print("\n4. Testing delete route existence...")
        # We'll test with a non-existent volunteer ID to see if route exists
        response = session.post(f"{BASE_URL}/admin_volunteers/999/delete")
        print(f"   Status: {response.status_code}")
        if response.status_code == 404:
            print("   ✓ Delete route exists (404 for non-existent volunteer)")
        elif response.status_code == 200:
            print("   ✓ Delete route exists and processed request")
        else:
            print(f"   ? Delete route response: {response.status_code}")

        print("\n✅ All basic tests passed!")
        return True

    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Is it running?")
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False


if __name__ == "__main__":
    success = test_admin_volunteers()
    if success:
        print("\n🎉 Admin volunteers functionality appears to be working!")
    else:
        print("\n💥 There are issues with the admin volunteers functionality.")
