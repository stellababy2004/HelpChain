import requests

try:
    response = requests.post(
        "http://localhost:5000/api/chatbot/message",
        json={"message": "Здравейте, какво е HelpChain?", "session_id": "test123"},
        timeout=30,
    )
    print("AI API Status:", response.status_code)
    if response.status_code == 200:
        data = response.json()
        print("Provider:", data.get("provider"))
        print("Confidence:", data.get("confidence"))
        print("Response:", repr(data.get("response")))
        if data.get("provider") == "Google Gemini":
            print("SUCCESS: Gemini API is working!")
        else:
            print("Using fallback provider")
    else:
        print("Response:", response.text)
except Exception as e:
    print("Error:", e)
