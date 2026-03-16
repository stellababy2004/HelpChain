#!/usr/bin/env python3
"""Test admin login and dashboard access with session persistence"""

import os

from backend.appy import app


def test_admin_session_persistence():
    """Test that session persists between login and dashboard access"""
    with app.test_client() as client:
        # Test login with correct credentials
        expected_password = os.getenv("ADMIN_PASSWORD", "test-password")
        print(f"Using password: {expected_password}")

        # First ensure admin exists
        from backend.appy import initialize_default_admin

        with app.app_context():
            admin_user = initialize_default_admin()
            print(f"Admin user exists: {admin_user is not None}")
            if admin_user:
                print(f"Admin username: {admin_user.username}")
                print(f"Password check: {admin_user.check_password(expected_password)}")

        # Step 1: Login
        print("\n--- Step 1: Login ---")
        login_response = client.post(
            "/admin/login",
            data={"username": "admin", "password": expected_password},
            follow_redirects=False,
        )  # Don't follow redirects to check status

        print(f"Login response status: {login_response.status_code}")
        print(
            f"Login response location: {login_response.headers.get('Location', 'No redirect')}"
        )

        # Check cookies - Flask test client stores cookies differently
        print("Cookies after login: Checking session data...")

        # Step 2: Access dashboard (should work if session persisted)
        print("\n--- Step 2: Access Dashboard ---")
        dashboard_response = client.get("/admin/dashboard", follow_redirects=False)

        print(f"Dashboard response status: {dashboard_response.status_code}")
        print(
            f"Dashboard response location: {dashboard_response.headers.get('Location', 'No redirect')}"
        )

        # Check if dashboard access succeeded
        if dashboard_response.status_code == 200:
            print("✓ Dashboard access test PASSED - Session persisted!")
            return True
        elif (
            dashboard_response.status_code == 302
            and "login" in dashboard_response.headers.get("Location", "")
        ):
            print(
                "✗ Dashboard access test FAILED - Redirected to login (session not persisted)"
            )
            return False
        else:
            print(
                f"? Dashboard access test UNKNOWN - Status {dashboard_response.status_code}"
            )
            return False


if __name__ == "__main__":
    print("Testing admin session persistence...")
    success = test_admin_session_persistence()
    if success:
        print("\n🎉 Session persistence is working correctly!")
    else:
        print("\n❌ Session persistence test failed")

