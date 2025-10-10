import requests

try:
    response = requests.get("http://localhost:3000/profile")
    print(f"Status: {response.status_code}")
    if response.status_code == 302:
        print(f'Redirect to: {response.headers.get("Location")}')
except Exception as e:
    print(f"Error: {e}")
