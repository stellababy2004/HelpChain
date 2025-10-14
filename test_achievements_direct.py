from backend.appy import app
from backend.models import Volunteer

# Start the app in test mode
with app.test_client() as client:
    # Get Ivan's ID
    with app.app_context():
        volunteer = Volunteer.query.filter_by(email="ivan@example.com").first()
        volunteer_id = volunteer.id
        print(f"Ivan ID: {volunteer_id}")

    # Simulate login by setting session
    with client.session_transaction() as sess:
        sess["volunteer_logged_in"] = True
        sess["volunteer_id"] = volunteer_id

    # Try to access achievements
    response = client.get("/achievements")
    print(f"Achievements status: {response.status_code}")

    if response.status_code == 200:
        print("Achievements page loaded successfully!")
        # Check if achievements are in the response
        response_text = response.data.decode("utf-8")
        if "achievement-card" in response_text:
            print("Achievement cards found in response")
        else:
            print("No achievement cards found")
            # Print first 1000 chars to see what's there
            print("Response preview:", response_text[:1000])
    else:
        error_text = response.data.decode("utf-8")
        print(f"Error: {error_text[:500]}")
