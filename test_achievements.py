import requests
from bs4 import BeautifulSoup

# Start a session to maintain cookies
s = requests.Session()

# Login as volunteer
login_data = {"email": "ivan@example.com"}
response = s.post("http://localhost:8000/volunteer_login", data=login_data)
print(f"Login status: {response.status_code}")
print(f"Login redirect: {response.url}")

# Check if we got redirected to dashboard
if "volunteer_dashboard" in response.url:
    print("Login successful!")

    # Now try to access achievements
    achievements_response = s.get("http://localhost:8000/achievements")
    print(f"Achievements status: {achievements_response.status_code}")

    if achievements_response.status_code == 200:
        soup = BeautifulSoup(achievements_response.text, "html.parser")
        title = soup.find("title")
        print(f"Achievements page title: {title.text if title else 'No title'}")

        # Check if achievements are loaded
        achievements = soup.find_all("div", class_="achievement-card")
        print(f"Found {len(achievements)} achievement cards")

        # Check for error messages
        error_div = soup.find("div", class_="alert-danger")
        if error_div:
            print(f"Error message: {error_div.text.strip()}")
    else:
        print(f"Achievements page failed: {achievements_response.text[:200]}")
else:
    print("Login failed")
