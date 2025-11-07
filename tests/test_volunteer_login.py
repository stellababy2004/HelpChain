import threading
import time

import requests

from backend.appy import app


# Start Flask app in a separate thread
def run_app():
    app.run(debug=False, host="127.0.0.1", port=5000, use_reloader=False)


thread = threading.Thread(target=run_app, daemon=True)
thread.start()

# Wait for app to start
time.sleep(3)

# Test volunteer login flow
base_url = "http://localhost:5000"

# Start session to maintain cookies
session = requests.Session()

print("Testing volunteer login...")

try:
    # Step 1: Login with email (test mode returns dashboard directly)
    response = session.post(
        f"{base_url}/volunteer_login", data={"email": "ivan@example.com"}
    )
    print(f"Login response status: {response.status_code}")
    print(f"Login redirect URL: {response.url}")

    if response.status_code == 200:
        print("SUCCESS: Volunteer dashboard accessible!")
        if "точки" in response.text.lower() or "ниво" in response.text.lower():
            print("SUCCESS: Gamification features found in dashboard!")
        else:
            print("WARNING: Gamification features not found in dashboard")
            # Print a snippet of the response for debugging
            print(f"Response snippet: {response.text[:500]}...")
    else:
        print(f"FAILED: Dashboard not accessible, got: {response.status_code}")

    # Skip the other steps since test mode returns dashboard directly

except Exception as e:
    print(f"Error during testing: {e}")
