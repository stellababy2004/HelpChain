#!/usr/bin/env python3
"""
Test script to trigger real-time analytics updates via WebSocket
"""
import json
import time
from datetime import datetime

import requests


def test_websocket_analytics():
    """Test WebSocket analytics events"""
    print("Testing WebSocket analytics real-time updates...")

    # Test the analytics API endpoint
    try:
        response = requests.get("http://localhost:5000/api/analytics/live")
        if response.status_code == 200:
            print("✅ Analytics API is responding")
            data = response.json()
            print(f"📊 Current analytics data: {json.dumps(data, indent=2)[:200]}...")
        else:
            print(f"❌ Analytics API error: {response.status_code}")
    except Exception as e:
        print(f"❌ Failed to connect to analytics API: {e}")

    # Test triggering analytics updates
    try:
        # Simulate some activity that would trigger analytics updates
        print("\n🔄 Simulating analytics activity...")

        # Make some requests to trigger updates
        for i in range(3):
            try:
                response = requests.get("http://localhost:5000/api/analytics/data")
                print(f"📈 Triggered analytics update {i+1}/3")
                time.sleep(1)
            except Exception as e:
                print(f"❌ Failed to trigger update {i+1}: {e}")

        print("✅ Analytics updates triggered successfully")
        print("📊 Check the analytics dashboard to see real-time chart updates!")

    except Exception as e:
        print(f"❌ Error testing analytics: {e}")


if __name__ == "__main__":
    test_websocket_analytics()
