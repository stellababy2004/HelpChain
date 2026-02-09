# Dedicated /api/analytics function


def app(environ, start_response):
    body = b'{"status":"ok","source":"api-analytics"}'
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Cache-Control", "no-store"),
        ("Content-Length", str(len(body))),
    ]
    start_response("200 OK", headers)
    return [body]
