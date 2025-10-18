#!/usr/bin/env python3
"""
Simple test script for push notification endpoints
"""

import json

import requests


def test_vapid_key():
    """Test VAPID public key endpoint"""
    try:
        response = requests.get(
            "http://localhost:8000/api/notification/vapid-public-key"
        )
        print(f"VAPID Key Test - Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Connection error: {e}")
        return False


def test_server_status():
    """Test basic server connectivity"""
    try:
        response = requests.get("http://localhost:8000/")
        print(f"Server Status - Status: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"Server connection error: {e}")
        return False


if __name__ == "__main__":
    print("Testing HelpChain Push Notification System")
    print("=" * 50)

    # Test server connectivity
    server_ok = test_server_status()
    print()

    if server_ok:
        # Test VAPID key endpoint
        vapid_ok = test_vapid_key()
        print()

        if vapid_ok:
            print("✅ Push notification system is working!")
        else:
            print("❌ Push notification endpoints have issues")
    else:
        print("❌ Server is not running")
