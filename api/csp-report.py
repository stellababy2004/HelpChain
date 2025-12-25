import json


def handler(request, response):
    try:
        data = request.json()
        print("CSP report:", data)
    except Exception as e:
        print("CSP report error:", str(e))
    response.status_code = 204
    return ""
