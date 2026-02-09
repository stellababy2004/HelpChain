#!/usr/bin/env python3
"""
Simple test script for push notification endpoints
"""

import requests


def test_vapid_key():
    """Test VAPID public key endpoint"""
    try:
        print("🧪 Testing VAPID public key endpoint...")

        response = requests.get(
            "http://127.0.0.1:8000/api/notification/vapid-public-key"
        )

        if response.status_code == 200:
            data = response.json()
            print("✅ VAPID key endpoint working!")
            print(f"   Status: {response.status_code}")
            print(f"   Key: {data.get('publicKey', 'N/A')[:20]}...")
            return True
        else:
            print(f"❌ VAPID key endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Error testing VAPID key: {e}")
        return False


def test_server_status():
    """Test basic server connectivity"""
    try:
        print("🧪 Testing server connectivity...")

        response = requests.get("http://127.0.0.1:8000/")

        if response.status_code == 200:
            print("✅ Server is running!")
            print(f"   Status: {response.status_code}")
            return True
        else:
            print(f"❌ Server not responding: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error connecting to server: {e}")
        return False


if __name__ == "__main__":
    print("🚀 Starting push notification endpoint tests...\n")

    # Test server connectivity first
    if not test_server_status():
        print("❌ Server not running, cannot test endpoints")
        exit(1)

    print()

    # Test VAPID key endpoint
    vapid_ok = test_vapid_key()

    print()

    if vapid_ok:
        print("🎉 All tests passed!")
    else:
        print("❌ Some tests failed")
