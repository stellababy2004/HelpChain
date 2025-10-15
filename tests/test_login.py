import requests

# Test admin login
url = "http://127.0.0.1:5000/admin_login"
data = {"username": "admin", "password": "admin123"}

try:
    response = requests.post(url, data=data, allow_redirects=False, timeout=5)
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.text}")
    print(f"Headers: {response.headers}")
except requests.exceptions.RequestException as e:
    print(f"Request failed: {e}")
