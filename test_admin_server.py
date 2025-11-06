#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

import threading
import time

import requests
from appy import app


def run_server():
    app.run(host="127.0.0.1", port=8000, debug=False, use_reloader=False)


# Start server in background thread
server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

# Wait for server to start
time.sleep(3)

try:
    # Test admin login
    response = requests.post(
        "http://127.0.0.1:8000/admin_login",
        data={"username": "admin", "password": "admin123"},
        allow_redirects=False,
    )

    print(f"Status code: {response.status_code}")
    print(f"Response: {response.text[:500]}")

    if response.status_code == 302:  # Redirect means success
        print("Admin login successful!")
    else:
        print("Admin login failed")

except Exception as e:
    print(f"Error testing admin login: {e}")
