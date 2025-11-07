import requests

# Create a session to maintain cookies
session = requests.Session()

# Test POST request to volunteer_login
url = "http://localhost:8000/volunteer_login"
data = {"email": "ivan@example.com"}

print("Testing POST request to volunteer_login...")
try:
    response = session.post(url, data=data, allow_redirects=False)
    print(f"Status Code: {response.status_code}")
    print(f"Location: {response.headers.get('Location', 'None')}")

    if response.status_code == 302 and "volunteer_dashboard" in response.headers.get(
        "Location", ""
    ):
        print("Login successful!")

        # Check session cookies
        print(f"Session cookies: {dict(session.cookies)}")

        # Now try to access volunteer_dashboard to confirm session works
        print("\nTesting GET request to volunteer_dashboard...")
        dashboard_response = session.get(
            "http://localhost:8000/volunteer_dashboard", allow_redirects=False
        )
        print(f"Dashboard Status Code: {dashboard_response.status_code}")
        print(
            f"Dashboard Location: {dashboard_response.headers.get('Location', 'None')}"
        )

        if dashboard_response.status_code == 200:
            print("Dashboard loaded successfully!")

            # Now try to access achievements page
            print("\nTesting GET request to achievements...")
            achievements_response = session.get(
                "http://localhost:8000/achievements", allow_redirects=False
            )
            print(f"Achievements Status Code: {achievements_response.status_code}")
            print(
                f"Achievements Location: {achievements_response.headers.get('Location', 'None')}"
            )

            if achievements_response.status_code == 200:
                print("Achievements page loaded successfully!")
                # Check if content contains gamification elements
                content = achievements_response.text
                if (
                    "points" in content.lower()
                    or "level" in content.lower()
                    or "achievements" in content.lower()
                ):
                    print("Gamification content found!")
                else:
                    print("No gamification content found")
                print(f"Content preview: {content[:500]}...")
            else:
                print("Achievements page redirect or error")
        else:
            print("Dashboard access failed")

    else:
        print("Login failed")
        print(f"Response content: {response.text[:500]}...")

except Exception as e:
    print(f"Error: {e}")
