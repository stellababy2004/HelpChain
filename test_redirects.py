import time

import requests

time.sleep(2)  # Wait for server to be ready

try:
    # Test admin login page
    response = requests.get("http://127.0.0.1:5000/admin/login", timeout=5)
    print(f"Admin login page: {response.status_code}")

    # Test analytics redirect
    response = requests.get(
        "http://127.0.0.1:5000/analytics", allow_redirects=False, timeout=5
    )
    print(f"Analytics redirect: {response.status_code}")
    if "Location" in response.headers:
        location = response.headers["Location"]
        print(f"Redirects to: {location}")
        if "/admin/login" in location:
            print("✓ Analytics correctly redirects to admin login")
        else:
            print("✗ Analytics redirect incorrect")

    # Test admin analytics (should show real data now)
    response = requests.get("http://127.0.0.1:5000/admin_analytics", timeout=5)
    print(f"Admin analytics: {response.status_code}")
    if "Dashboard stats:" in response.text:
        print("✓ Admin analytics page loads with data")
    else:
        print("? Admin analytics page loads but data format unclear")

    # Test admin dashboard access without login (should redirect)
    response = requests.get(
        "http://127.0.0.1:5000/admin/dashboard", allow_redirects=False, timeout=5
    )
    print(f"Admin dashboard without login: {response.status_code}")
    if response.status_code == 302 and "Location" in response.headers:
        location = response.headers["Location"]
        print(f"Redirects to: {location}")
        if "/admin/login" in location:
            print(
                "✓ Admin dashboard correctly redirects to login when not authenticated"
            )
        else:
            print("✗ Admin dashboard redirect incorrect")

    print("All redirect tests completed!")

except Exception as e:
    print(f"Test failed: {e}")
