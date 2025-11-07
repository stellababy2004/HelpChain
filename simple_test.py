#!/usr/bin/env python3
"""
Simple test to check if the server is responding
"""

import time

import requests

BASE_URL = "http://127.0.0.1:5000"


def test_server():
    print("Testing server response...")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code == 200:
            print("✅ Homepage accessible")
            return True
        else:
            print(f"❌ Homepage returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


if __name__ == "__main__":
    # Wait for server to start
    time.sleep(3)
    success = test_server()
    print("Test completed.")
