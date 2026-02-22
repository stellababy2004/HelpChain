#!/usr/bin/env python3
"""
Test API endpoints
"""

import json

import requests


def test_api_endpoints():
    """Test HelpChain API endpoints"""
    base_url = "http://localhost:5000"

    print("🔍 Тестване на API endpoints")
    print("=" * 50)

    # Test endpoints
    endpoints = [
        ("/", "Основна страница"),
        ("/api/analytics-data", "Analytics Data API"),
        ("/api/cache-stats", "Cache Stats API"),
        ("/admin", "Admin страница"),
        ("/api/notifications/queue/status", "Notification Queue Status"),
    ]

    for endpoint, name in endpoints:
        try:
            print(f"📡 Тестване на {name}...")
            response = requests.get(f"{base_url}{endpoint}", timeout=10)

            if response.status_code == 200:
                print(f"  ✅ {name}: HTTP {response.status_code}")

                # Show first 100 chars of response for data endpoints
                if endpoint.startswith("/api/"):
                    try:
                        json_data = response.json()
                        print(
                            f"  📊 Data: {json.dumps(json_data, ensure_ascii=False)[:100]}..."
                        )
                    except Exception:
                        print(f"  📄 Text: {response.text[:100]}...")
            else:
                print(f"  ⚠️  {name}: HTTP {response.status_code}")

        except requests.exceptions.ConnectionError:
            print(f"  ❌ {name}: Connection refused - сървърът не работи")
        except requests.exceptions.Timeout:
            print(f"  ⏰ {name}: Timeout")
        except Exception as e:
            print(f"  ❌ {name}: Error - {e}")

    print("\n" + "=" * 50)


if __name__ == "__main__":
    test_api_endpoints()
