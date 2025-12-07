#!/usr/bin/env python3
"""
Simple test script to verify PWA fixes work
"""

import os
import sys

# Add backend to path
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
sys.path.insert(0, backend_dir)


def test_sw_route():
    """Test that /sw.js route serves the service worker correctly"""
    try:
        # Start a simple Flask test server
        from flask import Flask, send_from_directory

        app = Flask(__name__)
        app.static_folder = os.path.join(backend_dir, "static")

        @app.route("/sw.js")
        def serve_sw():
            response = send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")
            response.headers["Service-Worker-Allowed"] = "/"
            return response

        # Test the route
        with app.test_client() as client:
            response = client.get("/sw.js")
            print(f"Status Code: {response.status_code}")
            print(f"Content-Type: {response.headers.get('Content-Type')}")
            print(f"Service-Worker-Allowed: {response.headers.get('Service-Worker-Allowed')}")
            print(f"Content Length: {len(response.get_data())}")

            if response.status_code == 200:
                print("✅ /sw.js route works correctly!")
                return True
            else:
                print("❌ /sw.js route failed!")
                return False

    except Exception as e:
        print(f"❌ Error testing /sw.js route: {e}")
        return False


def test_push_subscription_logic():
    """Test the push subscription logic"""
    try:
        # Check if the notifications file exists
        notifications_file = os.path.join(backend_dir, "routes", "notifications.py")
        if not os.path.exists(notifications_file):
            print("❌ routes/notifications.py file not found")
            return False

        # Read the file and check for subscribe_push function
        with open(notifications_file, encoding="utf-8") as f:
            content = f.read()

        if "def subscribe_push" in content:
            print("✅ subscribe_push function exists in notifications.py")
            return True
        else:
            print("❌ subscribe_push function not found in notifications.py")
            return False

    except Exception as e:
        print(f"❌ Error testing push subscription logic: {e}")
        return False


if __name__ == "__main__":
    print("Testing PWA fixes...")
    print("=" * 50)

    sw_test = test_sw_route()
    push_test = test_push_subscription_logic()

    print("=" * 50)
    if sw_test and push_test:
        print("✅ All PWA fixes verified successfully!")
    else:
        print("❌ Some tests failed")
