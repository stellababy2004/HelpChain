import requests
import threading

URL = "http://127.0.0.1:5000/requests/new"

payload = {
    "structure_id": "1",   # използвай валиден structure_id
    "need_type": "urgence_sociale",
    "urgency": "medium",
    "description": "Load test request"
}

def send_request(i):
    try:
        r = requests.post(URL, data=payload, timeout=5)
        print(f"Request {i}: {r.status_code}")
    except Exception as e:
        print(f"Request {i} failed: {e}")

threads = []

for i in range(50):
    t = threading.Thread(target=send_request, args=(i,))
    t.start()
    threads.append(t)

for t in threads:
    t.join()

print("Load test finished.")
