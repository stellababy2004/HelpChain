import sys
import os

# Ensure current project root is on sys.path when running this script directly
sys.path.insert(0, os.getcwd())

from appy import app

app.config["TESTING"] = True
with app.test_client() as c:
    payload = {
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "TestPass123",
    }
    resp = c.post("/auth/signup", json=payload)
    print("status", resp.status_code)
    try:
        print("json =", resp.get_json())
    except Exception as e:
        print("raw =", resp.get_data(as_text=True))
        print("json error =", e)
