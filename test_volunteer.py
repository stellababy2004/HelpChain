import requests

# Login as volunteer
session = requests.Session()
login_data = {"email": "ivan@example.com"}
response = session.post("http://127.0.0.1:3000/volunteer_login", data=login_data)

print(f"Login status: {response.status_code}")
print(f'Redirect location: {response.headers.get("Location", "None")}')

# Check if redirected to dashboard
if response.status_code == 302 and "volunteer_dashboard" in response.headers.get(
    "Location", ""
):
    print("✓ Login successful, redirected to dashboard")

    # Get dashboard page
    dashboard_response = session.get("http://127.0.0.1:3000/volunteer_dashboard")
    print(f"Dashboard status: {dashboard_response.status_code}")
    if "Иван Петров" in dashboard_response.text:
        print("✓ Dashboard shows volunteer name")
    else:
        print("✗ Volunteer name not found in dashboard")

    if "Актуализирайте вашата локация" in dashboard_response.text:
        print("✓ Location update section found")
    else:
        print("✗ Location update section not found")

    if "latitude" in dashboard_response.text and "longitude" in dashboard_response.text:
        print("✓ Location form fields found")
    else:
        print("✗ Location form fields not found")

else:
    print("✗ Login failed")
    print(f"Response: {response.text[:200]}")
