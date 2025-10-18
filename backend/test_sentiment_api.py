import time

import requests

# Wait for server to start
time.sleep(2)

try:
    response = requests.get("http://127.0.0.1:8000/api/sentiment/analytics")
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print("API Response:")
        print(f"Total feedback: {data.get('total_feedback', 0)}")
        print(f"Processed feedback: {data.get('processed_feedback', 0)}")
        print(f"Sentiment distribution: {data.get('sentiment_distribution', {})}")
        print("SUCCESS: Sentiment analytics API is working!")
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Connection error: {e}")
