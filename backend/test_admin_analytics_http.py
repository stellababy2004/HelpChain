#!/usr/bin/env python
"""
Test admin analytics functionality with real HTTP requests
"""

import json
import os

import requests
from bs4 import BeautifulSoup


def test_admin_analytics_http():
    """Test admin analytics with real HTTP requests"""

    base_url = "http://127.0.0.1:8000"
    session = requests.Session()

    print("Testing admin login and analytics with HTTP requests...")

    try:
        # 1. Test admin login
        print("\n1. Testing admin login...")
        login_data = {
            "username": "admin",
            "password": os.getenv("ADMIN_PASSWORD", "test-password"),
        }

        response = session.post(
            f"{base_url}/admin/login", data=login_data, allow_redirects=True
        )
        print(f"Login response status: {response.status_code}")
        print(f"Final URL after login: {response.url}")

        if response.status_code == 200 and "admin_dashboard" in response.url:
            print("SUCCESS: Admin login successful!")
        else:
            print("FAILED: Admin login failed")
            print("Response content:", response.text[:500])
            return

        # 2. Test analytics page
        print("\n2. Testing analytics page...")
        response = session.get(f"{base_url}/admin_analytics")
        print(f"Analytics response status: {response.status_code}")

        if response.status_code == 200:
            print("SUCCESS: Analytics page loaded!")

            # Parse HTML to check for Chart.js elements
            soup = BeautifulSoup(response.text, "html.parser")

            # Check for Chart.js script
            chart_js = soup.find(
                "script", string=lambda text: text and "Chart.js" in text
            )
            if chart_js:
                print("SUCCESS: Chart.js library found")
            else:
                print("WARNING: Chart.js library not found")

            # Check for chart canvases
            canvases = soup.find_all(
                "canvas",
                {"id": ["trendsChart", "categoryChart", "geoChart", "predictionChart"]},
            )
            found_canvases = [canvas.get("id") for canvas in canvases]
            print(f"Found chart canvases: {found_canvases}")

            if len(found_canvases) >= 3:
                print("SUCCESS: Most chart canvases found")
            else:
                print("WARNING: Some chart canvases missing")

            # Check for data scripts
            data_scripts = soup.find_all("script", {"type": "application/json"})
            data_ids = []
            for script in data_scripts:
                script_id = script.get("id")
                if script_id:
                    data_ids.append(script_id)

            print(f"Found data scripts: {data_ids}")

            # Check for trendsData specifically
            trends_script = soup.find("script", {"id": "trendsData"})
            if trends_script:
                try:
                    trends_data = json.loads(trends_script.string)
                    print(
                        f"SUCCESS: Trends data loaded with {len(trends_data.get('labels', []))} data points"
                    )
                except json.JSONDecodeError:
                    print("WARNING: Trends data is not valid JSON")
            else:
                print("WARNING: Trends data script not found")

            # Check for categoryStats
            category_script = soup.find("script", {"id": "categoryStats"})
            if category_script:
                try:
                    category_data = json.loads(category_script.string)
                    print(
                        f"SUCCESS: Category stats loaded with {len(category_data)} categories"
                    )
                except json.JSONDecodeError:
                    print("WARNING: Category stats is not valid JSON")
            else:
                print("WARNING: Category stats script not found")

        else:
            print("FAILED: Analytics page failed to load")
            print("Response content:", response.text[:1000])

    except requests.exceptions.ConnectionError:
        print(
            "ERROR: Cannot connect to server. Make sure Flask app is running on port 8000"
        )
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_admin_analytics_http()

