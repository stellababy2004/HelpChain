from textwrap import shorten

import requests

BASE_URL = "http://127.0.0.1:5000"
ENDPOINTS = [
    "/analytics/api/analytics/data",
    "/analytics/api/advanced/anomalies",
    "/api/admin/dashboard",
]

session = requests.Session()
login_response = session.post(
    f"{BASE_URL}/admin_login",
    data={"username": "admin", "password": "Admin123"},
    allow_redirects=True,
)
print("Login status:", login_response.status_code)
print("Login final URL:", login_response.url)
print("Cookies:", session.cookies.get_dict())

for endpoint in ENDPOINTS:
    response = session.get(f"{BASE_URL}{endpoint}")
    body = response.text.strip()
    preview = shorten(body, width=400, placeholder="...")
    print("\nEndpoint:", endpoint)
    print("Status:", response.status_code)
    print("Content-Type:", response.headers.get("content-type"))
    print("Body preview:", preview)
    print("Traceback present:", "Traceback" in body)
