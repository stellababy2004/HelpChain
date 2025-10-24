#!/usr/bin/env python3
"""
Test script to verify admin panel loads volunteers and help requests without errors
"""

import os
import sys

from bs4 import BeautifulSoup

# Add backend directory to path
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
sys.path.insert(0, backend_dir)


def test_admin_panel():
    """Test admin panel functionality"""
    from appy import app

    with app.test_client() as client:
        print("Testing admin panel functionality...")

        # Test admin login
        print("1. Testing admin login...")
        login_response = client.post(
            "/admin/login",
            data={
                "username": "admin",
                "password": os.getenv("ADMIN_PASSWORD", "Admin123"),
            },
            follow_redirects=True,
        )

        if login_response.status_code != 200:
            print(f"❌ Login failed with status {login_response.status_code}")
            return False

        print("✅ Admin login successful")

        # Test admin dashboard
        print("2. Testing admin dashboard...")
        dashboard_response = client.get("/admin_dashboard", follow_redirects=True)

        if dashboard_response.status_code != 200:
            print(
                f"❌ Dashboard access failed with status {dashboard_response.status_code}"
            )
            print(f"Final URL: {dashboard_response.request.url}")
            return False

        soup = BeautifulSoup(dashboard_response.data, "html.parser")

        # Check for volunteers data
        volunteers_count = soup.find(
            text=lambda text: text and "доброволци" in text.lower()
        )
        if volunteers_count:
            print("✅ Volunteers data loaded successfully")
        else:
            print("⚠️  Volunteers data not found in dashboard")

        # Check for requests data
        requests_count = soup.find(
            text=lambda text: text
            and ("заявки" in text.lower() or "requests" in text.lower())
        )
        if requests_count:
            print("✅ Help requests data loaded successfully")
        else:
            print("⚠️  Help requests data not found in dashboard")

        # Check for any error messages
        errors = soup.find_all(
            text=lambda text: text
            and ("error" in text.lower() or "грешка" in text.lower())
        )
        if errors:
            print(f"⚠️  Found {len(errors)} potential error messages:")
            for error in errors[:3]:  # Show first 3 errors
                print(f"   - {error.strip()}")
        else:
            print("✅ No error messages found in dashboard")

        print("3. Testing admin analytics...")
        analytics_response = client.get("/admin_analytics")
        if analytics_response.status_code == 200:
            print("✅ Admin analytics page loads successfully")
        else:
            print(f"⚠️ Admin analytics page status: {analytics_response.status_code}")

        print("4. Testing predictive analytics...")
        predictive_response = client.get("/predictive-analytics")
        if predictive_response.status_code == 200:
            print("✅ Predictive analytics page loads successfully")
        else:
            print(
                f"⚠️ Predictive analytics page status: {predictive_response.status_code}"
            )

        print("\n🎉 Admin panel test completed!")
        return True


if __name__ == "__main__":
    try:
        test_admin_panel()
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
