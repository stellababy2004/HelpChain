import os
import sys

# Add backend directory to path
backend_dir = os.path.dirname(__file__)
sys.path.insert(0, backend_dir)

from appy import app, db


def test_admin_login():
    with app.test_client() as client:
        # Test admin login
        response = client.post(
            "/admin_login",
            data={"username": "admin", "password": "Admin123"},
            follow_redirects=True,
        )

        print(f"Status code: {response.status_code}")
        print(f"Final URL: {response.request.url}")

        # Check if we got redirected to admin_dashboard
        if b"admin_dashboard" in response.data or "admin_dashboard" in str(
            response.data
        ):
            print("SUCCESS: Admin login worked!")
            return True
        else:
            print("FAILED: Admin login did not redirect to dashboard")
            print(f"Response contains 'error': {'error' in str(response.data).lower()}")
            print(f"Response preview: {str(response.data)[:500]}")
            return False


if __name__ == "__main__":
    with app.app_context():
        success = test_admin_login()
        print(f"Test result: {'PASSED' if success else 'FAILED'}")
