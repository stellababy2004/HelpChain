#!/usr/bin/env python3
"""
Comprehensive test script for admin dashboard functionality
"""
import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000"

def test_admin_dashboard():
    """Test the admin dashboard and related functionality"""
    print("🔍 Testing admin dashboard functionality...")
    print("=" * 60)

    # Create a session to maintain cookies
    session = requests.Session()

    try:
        # 1. Test basic access without login
        print("1. Testing admin dashboard access without login...")
        response = session.get(f"{BASE_URL}/admin_dashboard")
        print(f"   Status: {response.status_code}")
        if response.status_code == 302:  # Should redirect to login
            print("   ✓ Correctly redirected to login")
        else:
            print("   ✗ Expected redirect to login")

        # 2. Test admin login
        print("\n2. Testing admin login...")
        login_data = {
            'username': 'admin',
            'password': 'Admin123'
        }
        response = session.post(f"{BASE_URL}/admin_login", data=login_data, allow_redirects=False)
        print(f"   Status: {response.status_code}")

        # Check for successful login
        if response.status_code in [302, 200]:
            print("   ✓ Admin login successful")
        else:
            print("   ✗ Admin login failed")
            return False

        # 3. Test admin dashboard access after login
        print("\n3. Testing admin dashboard access after login...")
        response = session.get(f"{BASE_URL}/admin_dashboard")
        print(f"   Status: {response.status_code}")

        if response.status_code == 200:
            print("   ✓ Admin dashboard accessible")

            # Check for key content
            content_checks = [
                ("Dashboard title", "Админ панел" in response.text),
                ("Navigation", "admin_volunteers" in response.text),
                ("Statistics", "Общо заявки" in response.text or "статистика" in response.text.lower()),
                ("Charts/graphs", "chart" in response.text.lower() or "графика" in response.text.lower()),
            ]

            for check_name, check_result in content_checks:
                status = "✓" if check_result else "✗"
                print(f"   {status} {check_name}: {'Found' if check_result else 'Missing'}")

        else:
            print("   ✗ Admin dashboard not accessible")
            print(f"   Response: {response.text[:200]}...")
            return False

        # 4. Test admin API endpoints
        print("\n4. Testing admin API endpoints...")

        api_endpoints = [
            ("/api/admin/dashboard", "Admin dashboard API"),
            ("/analytics/api/analytics/data", "Analytics data API"),
            ("/analytics/admin_analytics", "Analytics dashboard"),
        ]

        for endpoint, description in api_endpoints:
            try:
                response = session.get(f"{BASE_URL}{endpoint}")
                status = "✓" if response.status_code == 200 else "✗"
                print(f"   {status} {description}: {response.status_code}")

                if response.status_code != 200:
                    print(f"      Error: {response.text[:100]}...")

            except Exception as e:
                print(f"   ✗ {description}: Error - {e}")

        # 5. Test key admin pages
        print("\n5. Testing key admin pages...")

        admin_pages = [
            ("/admin_volunteers", "Volunteers management"),
            ("/admin_tasks", "Tasks management"),
            ("/analytics/", "Analytics main page"),
        ]

        for page, description in admin_pages:
            try:
                response = session.get(f"{BASE_URL}{page}")
                status = "✓" if response.status_code == 200 else "✗"
                print(f"   {status} {description}: {response.status_code}")

                if response.status_code != 200:
                    print(f"      Error: {response.text[:100]}...")

            except Exception as e:
                print(f"   ✗ {description}: Error - {e}")

        # 6. Check for JavaScript errors or missing assets
        print("\n6. Checking for common issues...")

        # Check if analytics data loads
        try:
            response = session.get(f"{BASE_URL}/analytics/api/analytics/data?simple=true")
            if response.status_code == 200:
                data = response.json()
                print("   ✓ Analytics data API working")

                # Check data structure
                expected_keys = ['total_requests', 'total_volunteers', 'active_tasks']
                missing_keys = [key for key in expected_keys if key not in data]
                if missing_keys:
                    print(f"   ⚠️  Missing analytics keys: {missing_keys}")
                else:
                    print("   ✓ Analytics data structure looks good")
                    print(f"      - Total requests: {data.get('total_requests', 'N/A')}")
                    print(f"      - Total volunteers: {data.get('total_volunteers', 'N/A')}")
                    print(f"      - Active tasks: {data.get('active_tasks', 'N/A')}")
            else:
                print(f"   ✗ Analytics data API failed: {response.status_code}")
        except Exception as e:
            print(f"   ✗ Analytics data check failed: {e}")

        print("\n" + "=" * 60)
        print("✅ Admin dashboard testing completed!")
        return True

    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Is it running?")
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = test_admin_dashboard()
    if not success:
        print("\n💥 There are issues with the admin dashboard functionality.")
    else:
        print("\n🎉 Admin dashboard appears to be working!")