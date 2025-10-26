import json

import requests

print("Testing /api/admin/dashboard error response...")
print("=" * 50)

# Test with authentication (should return 500 with generic error)
print("Testing with admin authentication:")
try:
    # Create a session to maintain cookies
    session = requests.Session()

    # First login as admin
    login_data = {"username": "admin", "password": "Admin123"}
    login_response = session.post(
        "http://localhost:5000/admin_login", data=login_data, allow_redirects=False
    )
    print(f"Login status: {login_response.status_code}")

    # Then test the dashboard endpoint
    dashboard_response = session.get("http://localhost:5000/api/admin/dashboard")
    print(f"Dashboard status: {dashboard_response.status_code}")
    print(f'Content-Type: {dashboard_response.headers.get("Content-Type", "None")}')
    print(f"Response length: {len(dashboard_response.text)} characters")
    print()
    print("Raw response:")
    print("=" * 40)
    print(dashboard_response.text)
    print("=" * 40)

    # Check if it's JSON
    try:
        json_data = dashboard_response.json()
        print(f"JSON response: {json.dumps(json_data, indent=2, ensure_ascii=False)}")
    except:
        print("Not JSON response")

    # Check for traceback keywords
    response_lower = dashboard_response.text.lower()
    has_traceback = any(
        keyword in response_lower
        for keyword in ["traceback", "exception", "error in", 'file "', "line "]
    )
    has_generic_error = any(
        keyword in response_lower
        for keyword in ["вътрешна грешка", "internal server error", "server error"]
    )

    print()
    print("SECURITY CHECK:")
    print(f'Contains traceback: {"NO" if not has_traceback else "YES"}')
    print(f'Generic error message: {"YES" if has_generic_error else "NO"}')

    # Check for specific Bulgarian error message
    bulgarian_error = "Възникна неочаквана грешка. Нашият екип е уведомен и работи по проблема. Моля, опитайте отново по-късно."
    has_bulgarian_error = bulgarian_error in dashboard_response.text

    print(f'Bulgarian generic error: {"YES" if has_bulgarian_error else "NO"}')

except Exception as e:
    print(f"Error during test: {e}")
