import json

import requests

# Test a known endpoint first
try:
    response = requests.get("http://localhost:5000/test_analytics", timeout=10)
    print(f"Test endpoint status: {response.status_code}")
    print(f"Test endpoint response: {response.text}")
except Exception as e:
    print(f"Test endpoint error: {e}")

# Now test our health check
try:
    response = requests.get("http://localhost:5000/email_healthz", timeout=10)
    print(f"Health check status: {response.status_code}")
    if response.status_code == 200:
        print("Response:")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Response text: {response.text}")
except Exception as e:
    print(f"Health check error: {e}")
