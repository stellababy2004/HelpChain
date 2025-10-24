import requests
import time

try:
    response = requests.get('http://localhost:5000/analytics/stream', stream=True, timeout=5)
    print(f'Status Code: {response.status_code}')
    print(f'Content-Type: {response.headers.get("content-type", "N/A")}')

    lines_read = 0
    for line in response.iter_lines():
        if line:
            print(f'Line {lines_read + 1}: {line.decode("utf-8")[:100]}...')
            lines_read += 1
            if lines_read >= 3:
                break
        if lines_read >= 10:
            break

    print(f'Stream test completed - read {lines_read} lines')

except Exception as e:
    print(f'Error: {e}')