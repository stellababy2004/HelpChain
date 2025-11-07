"""
Test push notification endpoints
"""

import requests

BASE_URL = "http://127.0.0.1:8000"


def test_vapid_key():
    """Test VAPID public key endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/notification/vapid-public-key")
        print(f"🔑 VAPID Key Endpoint: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Public Key: {data.get('public_key', 'N/A')[:20]}...")
            return True
        else:
            print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"   Connection Error: {e}")
        return False


def test_push_subscription():
    """Test push subscription endpoint with mock data"""
    try:
        # Mock push subscription data
        subscription_data = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/mock_endpoint",
            "keys": {
                "p256dh": "mock_p256dh_key_1234567890123456789012345678901234567890",
                "auth": "mock_auth_key_12345678",
            },
            "volunteer_id": 1,
        }

        response = requests.post(
            f"{BASE_URL}/api/notification/subscribe",
            json=subscription_data,
            headers={"Content-Type": "application/json"},
        )

        print(f"📱 Push Subscription: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data.get('message', 'OK')}")
            return True
        else:
            print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"   Connection Error: {e}")
        return False


def test_server_status():
    """Test if server is running"""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"🌐 Server Status: {response.status_code}")
        if response.status_code == 200:
            print("   Server is running!")
            return True
        else:
            print(f"   Unexpected status: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("   ❌ Server not responding")
        return False
    except Exception as e:
        print(f"   Error: {e}")
        return False


def main():
    print("🧪 Testing HelpChain Push Notification System")
    print("=" * 50)

    # Test server status
    if not test_server_status():
        print("\n❌ Server is not running. Please start the server first.")
        return

    print()

    # Test VAPID key endpoint
    vapid_ok = test_vapid_key()
    print()

    # Test push subscription
    subscription_ok = test_push_subscription()
    print()

    # Summary
    print("=" * 50)
    if vapid_ok and subscription_ok:
        print("✅ All push notification tests passed!")
        print("\n🎉 Push notification system is working correctly!")
        print("\nNext steps:")
        print("1. Open http://127.0.0.1:8000 in your browser")
        print("2. Click the 'Enable Push Notifications' button")
        print("3. Grant permission when prompted")
        print("4. Test receiving push notifications")
    else:
        print("❌ Some tests failed. Check server logs for details.")


if __name__ == "__main__":
    main()
