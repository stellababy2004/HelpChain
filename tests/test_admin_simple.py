import os

import requests

# Test admin login on port 8000
url = "http://localhost:8000/admin_login"
data = {"username": "admin", "password": os.getenv("ADMIN_USER_PASSWORD", "Admin123")}

print("Testing admin login...")
try:
    response = requests.post(url, data=data, allow_redirects=False)
    print(f"Status: {response.status_code}")
    print(f"Location: {response.headers.get('Location', 'None')}")

    if response.status_code == 302 and "admin_dashboard" in response.headers.get(
        "Location", ""
    ):
        print("SUCCESS: Login redirect working!")

        # Extract session cookie
        cookies = response.cookies
        session_cookie = None
        for cookie in cookies:
            if "session" in cookie.name.lower():
                session_cookie = cookie
                break

        if session_cookie:
            print(f"Session cookie found: {session_cookie.name}")

            # Test accessing admin_dashboard
            dashboard_url = "http://localhost:8000/admin_dashboard"
            dashboard_response = requests.get(dashboard_url, cookies=cookies)
            print(f"Dashboard status: {dashboard_response.status_code}")
            if dashboard_response.status_code == 200:
                print("SUCCESS: Admin dashboard accessible!")
            else:
                print("FAILED: Admin dashboard not accessible")
                print(f"Content: {dashboard_response.text[:200]}...")
        else:
            print("FAILED: No session cookie found")
    else:
        print("FAILED: Login did not redirect properly")
        print(f"Content: {response.text[:200]}...")
except Exception as e:
    print(f"Error: {e}")
