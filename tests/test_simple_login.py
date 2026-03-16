import os

from backend.appy import app

# Test admin login
with app.test_client() as client:
    response = client.post(
        "/admin/login",
        data={
            "username": "admin",
            "password": os.getenv("ADMIN_USER_PASSWORD", "test-password"),
        },
        follow_redirects=True,
    )

    print(f"Status Code: {response.status_code}")
    print(f"Location: {response.headers.get('Location', 'None')}")
    print(f"Data length: {len(response.get_data(as_text=True))}")
    print(
        "Response contains dashboard:",
        "admin_dashboard" in response.get_data(as_text=True),
    )
    print(
        "Response contains login form:",
        "admin_login" in response.get_data(as_text=True),
    )

