# Dedicated /api/_health function


def app(environ, start_response):
    body = b"ok"
    headers = [
        ("Content-Type", "text/plain; charset=utf-8"),
        ("Cache-Control", "no-store"),
        ("Content-Length", str(len(body))),
    ]
    start_response("200 OK", headers)
    return [body]
