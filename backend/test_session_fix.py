#!/usr/bin/env python3
"""
Test script to verify admin login session persistence
"""
import requests
import time

# Base URL
base_url = "http://127.0.0.1:5000"

# Create a session to maintain cookies
session = requests.Session()

print("Testing admin login session persistence...")

# Step 1: Try to access admin dashboard without login (should redirect)
print("\n1. Testing access to admin dashboard without login...")
response = session.get(f"{base_url}/admin_dashboard", allow_redirects=False)
print(f"Status: {response.status_code}")
if response.status_code == 302:
    print("✓ Correctly redirected (not logged in)")
else:
    print("✗ Unexpected response")

# Step 2: Login as admin
print("\n2. Logging in as admin...")
login_data = {
    "username": "admin",
    "password": "Admin123"
}
response = session.post(f"{base_url}/admin_login", data=login_data, allow_redirects=False)
print(f"Status: {response.status_code}")
if response.status_code == 302:
    print("✓ Login successful, redirecting to dashboard")
    # Follow the redirect
    redirect_url = response.headers.get('Location')
    if redirect_url:
        print(f"Redirecting to: {redirect_url}")
        response = session.get(redirect_url, allow_redirects=False)
        print(f"Dashboard response: {response.status_code}")
else:
    print("✗ Login failed")
    print(f"Response: {response.text[:200]}")

# Step 3: Test session persistence - access dashboard again
print("\n3. Testing session persistence...")
time.sleep(1)  # Small delay
response = session.get(f"{base_url}/admin_dashboard", allow_redirects=False)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print("✓ Session persisted! Admin dashboard accessible")
elif response.status_code == 302:
    print("✗ Session lost - redirected back to login")
else:
    print(f"✗ Unexpected response: {response.status_code}")

# Step 4: Check cookies
print("\n4. Checking session cookies...")
cookies = session.cookies.get_dict()
session_cookie = None
for name, value in cookies.items():
    if 'session' in name.lower():
        session_cookie = (name, value)
        break

if session_cookie:
    print(f"✓ Session cookie found: {session_cookie[0]}")
else:
    print("✗ No session cookie found")

print("\nTest completed.")