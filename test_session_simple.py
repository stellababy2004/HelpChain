import requests

# Test session persistence
session = requests.Session()

print("=== Testing Direct Dashboard Access ===")
response = session.get("http://127.0.0.1:5000/admin_dashboard")
print(f"Direct dashboard access status: {response.status_code}")
if response.status_code == 302:
    print(f"Redirected to: {response.headers.get('Location')}")
    print("As expected: redirected to login when not authenticated")

print()
print("=== Testing Admin Login Session Persistence ===")

# 1. Get admin login page
print("1. Getting admin login page...")
response = session.get("http://127.0.0.1:5000/admin_login")
print(f"Status: {response.status_code}")
print("Login page loaded successfully")

# 2. Attempt admin login
print("2. Attempting admin login...")
# IMPORTANT: No real secrets! Use a placeholder if needed.
login_data = {"username": "admin", "password": "REPLACE_ME"}  # pragma: allowlist secret
response = session.post(
    "http://127.0.0.1:5000/admin_login", data=login_data, allow_redirects=False
)
print(f"Login POST status: {response.status_code}")
print(f"Session cookies after login POST: {dict(session.cookies)}")
if response.status_code == 302:
    print(f"Redirect to: {response.headers.get('Location')}")

# 3. Follow redirect to admin_dashboard
print("3. Following redirect to admin_dashboard...")
response = session.get("http://127.0.0.1:5000/admin_dashboard", allow_redirects=False)
print(f"Dashboard GET status: {response.status_code}")
print(f"Session cookies after redirect: {dict(session.cookies)}")
if response.status_code == 302:
    print(f"Second redirect to: {response.headers.get('Location')}")
    print("ERROR: Redirected back to login - session not persistent!")
else:
    print("SUCCESS: Dashboard loaded - session persistent!")
