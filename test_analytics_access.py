import requests

# Test analytics page access
base_url = "http://127.0.0.1:5000"


def test_analytics_access():
    print("Testing analytics page access...")

    # First, try to access analytics page directly (should redirect to login)
    print("\n1. Testing direct access to /analytics (should redirect to login)...")
    response = requests.get(f"{base_url}/analytics", allow_redirects=False)
    print(f"Status: {response.status_code}")
    print(f"Location: {response.headers.get('Location', 'No redirect')}")

    # Try to access admin_analytics directly (should redirect to login)
    print(
        "\n2. Testing direct access to /admin_analytics (should redirect to login)..."
    )
    response = requests.get(f"{base_url}/admin_analytics", allow_redirects=False)
    print(f"Status: {response.status_code}")
    print(f"Location: {response.headers.get('Location', 'No redirect')}")

    # Login as admin
    print("\n3. Logging in as admin...")
    session = requests.Session()

    # For now, assume no CSRF - try direct login
    login_data = {"username": "admin", "password": "Admin123"}

    login_response = session.post(
        f"{base_url}/admin_login", data=login_data, allow_redirects=False
    )
    print(f"Login status: {login_response.status_code}")
    print(f"Login location: {login_response.headers.get('Location', 'No redirect')}")

    # Follow redirects
    if login_response.status_code in [302, 303]:
        redirect_url = login_response.headers.get("Location")
        if redirect_url:
            print(f"Following redirect to: {redirect_url}")
            final_response = session.get(
                f"{base_url}{redirect_url}"
                if redirect_url.startswith("/")
                else redirect_url
            )
            print(f"Final status: {final_response.status_code}")

    # Now try to access analytics
    print("\n4. Testing analytics access after login...")
    analytics_response = session.get(f"{base_url}/analytics", allow_redirects=False)
    print(f"Analytics status: {analytics_response.status_code}")
    print(
        f"Analytics location: {analytics_response.headers.get('Location', 'No redirect')}"
    )

    # Try admin_analytics
    print("\n5. Testing admin_analytics access after login...")
    admin_analytics_response = session.get(
        f"{base_url}/admin_analytics", allow_redirects=False
    )
    print(f"Admin analytics status: {admin_analytics_response.status_code}")

    if admin_analytics_response.status_code == 200:
        print("✓ Admin analytics page loaded successfully!")
        # Check if CSP headers are present
        csp_header = admin_analytics_response.headers.get("Content-Security-Policy", "")
        if "jsdelivr.net" in csp_header:
            print("✓ CSP header contains jsdelivr.net")
        else:
            print("✗ CSP header missing jsdelivr.net")
    else:
        print(
            f"✗ Admin analytics failed with status {admin_analytics_response.status_code}"
        )
        if admin_analytics_response.status_code in [302, 303]:
            print(f"Redirected to: {admin_analytics_response.headers.get('Location')}")


if __name__ == "__main__":
    test_analytics_access()
