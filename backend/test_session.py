import time
import requests

# Create session
session = requests.Session()

# Login
login_data = {"username": "admin", "password": "N!Zdx2!H%X#Icuyp"}
print("Logging in...")
r = session.post(
    "http://127.0.0.1:5000/admin_login", data=login_data, allow_redirects=False
)
print(f"Login status: {r.status_code}")
print(f"Login location: {r.headers.get('Location')}")

# Get dashboard
dashboard_url = r.headers.get("Location")
if dashboard_url:
    print(f"Getting dashboard: {dashboard_url}")
    r2 = session.get("http://127.0.0.1:5000" + dashboard_url)
    print(f"Dashboard status: {r2.status_code}")

# Try analytics
print("Trying analytics...")
r3 = session.get("http://127.0.0.1:5000/analytics", allow_redirects=False)
print(f"Analytics status: {r3.status_code}")
print(f"Analytics location: {r3.headers.get('Location')}")

# Try admin_analytics
print("Trying admin_analytics...")
r4 = session.get("http://127.0.0.1:5000/admin_analytics", allow_redirects=False)
print(f"Admin Analytics status: {r4.status_code}")
print(f"Admin Analytics location: {r4.headers.get('Location')}")

# Check cookies
print("Cookies:")
for cookie in session.cookies:
    print(f"  {cookie.name}: {cookie.value}")
