#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script for admin analytics functionality
"""

import requests
import os


def test_admin_analytics():
    """Test admin analytics page access"""
    base_url = "http://localhost:8000"

    # Start session
    session = requests.Session()

    # First login as admin
    login_data = {
        "username": "admin",
        "password": os.getenv("ADMIN_USER_PASSWORD", "Admin123"),
    }

    print("Logging in as admin...")
    login_response = session.post(
        f"{base_url}/admin_login", data=login_data, allow_redirects=False
    )

    print(f"Login status: {login_response.status_code}")
    print(f"Login headers: {dict(login_response.headers)}")

    if login_response.status_code == 302:
        print("Login successful, redirecting to dashboard")

        # Follow redirect to dashboard
        dashboard_url = login_response.headers.get("Location")
        if dashboard_url:
            dashboard_response = session.get(f"{base_url}{dashboard_url}")
            print(f"Dashboard status: {dashboard_response.status_code}")

        # Now try to access analytics
        print("\nAccessing admin analytics...")
        analytics_response = session.get(f"{base_url}/admin_analytics")

        print(f"Analytics status: {analytics_response.status_code}")
        print(f"Analytics URL: {analytics_response.url}")

        if analytics_response.status_code == 200:
            print("✓ Admin analytics page loaded successfully!")

            # Check if charts are present
            content = analytics_response.text
            if "chart-container" in content:
                print("✓ Chart containers found in HTML")
            else:
                print("✗ Chart containers not found")

            if "Chart.js" in content:
                print("✓ Chart.js library found")
            else:
                print("✗ Chart.js library not found")

            # Check for data scripts
            if "trendsData" in content:
                print("✓ Trends data script found")
            else:
                print("✗ Trends data script not found")

        else:
            print(
                f"✗ Admin analytics failed with status {analytics_response.status_code}"
            )
            print(f"Response: {analytics_response.text[:500]}")

    else:
        print(f"✗ Login failed with status {login_response.status_code}")
        print(f"Response: {login_response.text[:500]}")


if __name__ == "__main__":
    test_admin_analytics()
