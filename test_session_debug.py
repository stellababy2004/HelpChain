#!/usr/bin/env python3
"""
Test script to debug admin login session persistence issue
"""

import requests


def test_admin_login_session():
    """Test admin login and session persistence"""
    base_url = "http://localhost:5000"

    # Create a session to maintain cookies
    session = requests.Session()

    print("=== Testing Admin Login Session Persistence ===")

    # Step 1: Get login page to check CSRF token if any
    print("\n1. Getting admin login page...")
    try:
        response = session.get(f"{base_url}/admin_login")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("Login page loaded successfully")
            # Check for any session cookies
            cookies = session.cookies.get_dict()
            print(f"Session cookies after GET: {cookies}")
        else:
            print(f"Failed to load login page: {response.text}")
            return
    except Exception as e:
        print(f"Error getting login page: {e}")
        return

    # Step 2: Attempt login
    print("\n2. Attempting admin login...")
    login_data = {"username": "admin", "password": "Admin123"}

    try:
        response = session.post(
            f"{base_url}/admin_login", data=login_data, allow_redirects=False
        )
        print(f"Login POST status: {response.status_code}")
        print(f"Login POST headers: {dict(response.headers)}")

        # Check cookies after login
        cookies_after_login = session.cookies.get_dict()
        print(f"Session cookies after login POST: {cookies_after_login}")

        if response.status_code == 302:
            redirect_url = response.headers.get("Location")
            print(f"Redirect to: {redirect_url}")

            # Step 3: Follow redirect to admin_dashboard
            print("\n3. Following redirect to admin_dashboard...")
            response2 = session.get(f"{base_url}{redirect_url}", allow_redirects=False)
            print(f"Dashboard GET status: {response2.status_code}")
            print(f"Dashboard GET headers: {dict(response2.headers)}")

            cookies_after_redirect = session.cookies.get_dict()
            print(f"Session cookies after redirect: {cookies_after_redirect}")

            if response2.status_code == 302:
                redirect_url2 = response2.headers.get("Location")
                print(f"Second redirect to: {redirect_url2}")

                # Step 4: Check if redirected back to login
                if "/admin_login" in redirect_url2:
                    print("ERROR: Redirected back to login - session not persistent!")
                    return False
                else:
                    print("SUCCESS: Not redirected to login")
                    return True
            elif response2.status_code == 200:
                print("SUCCESS: Dashboard loaded directly")
                return True
            else:
                print(f"Unexpected status: {response2.status_code}")
                return False
        else:
            print(f"Login failed with status: {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print(f"Error during login: {e}")
        return False


def test_direct_dashboard_access():
    """Test direct access to admin dashboard"""
    base_url = "http://localhost:5000"

    # Create a new session
    session = requests.Session()

    print("\n=== Testing Direct Dashboard Access ===")

    try:
        response = session.get(f"{base_url}/admin_dashboard", allow_redirects=False)
        print(f"Direct dashboard access status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")

        if response.status_code == 302:
            redirect_url = response.headers.get("Location")
            print(f"Redirected to: {redirect_url}")
            if "/admin_login" in redirect_url:
                print("As expected: redirected to login when not authenticated")
                return True
            else:
                print("Unexpected redirect")
                return False
        else:
            print("Unexpected: dashboard accessible without login")
            return False

    except Exception as e:
        print(f"Error testing direct access: {e}")
        return False


if __name__ == "__main__":
    print("Testing Flask session persistence...")

    # Test 1: Direct access should redirect to login
    test_direct_dashboard_access()

    # Test 2: Login flow
    success = test_admin_login_session()

    if success:
        print("\n✅ Session persistence test PASSED")
    else:
        print("\n❌ Session persistence test FAILED")
