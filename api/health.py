# Lightweight WSGI app for health/admin/analytics probes in Vercel


def app(environ, start_response):
    try:
        path = (
            environ.get("HTTP_X_FORWARDED_URI")
            or environ.get("REQUEST_URI")
            or environ.get("RAW_PATH")
            or environ.get("PATH_INFO")
            or ""
        ).strip()
        if not path:
            path = "/"
        method = (environ.get("REQUEST_METHOD") or "GET").upper()
        if path.endswith("/api/analytics"):
            body = b'{"status":"ok","source":"health-function"}'
            headers = [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Cache-Control", "no-store"),
                ("Content-Length", str(len(body))),
            ]
            start_response("200 OK", headers)
            return [body]
        if (
            path.endswith("/admin/login") or path.endswith("/admin/login/")
        ) and method == "GET":
            body = (
                b"<html><head><title>Admin Login</title></head>"
                b"<body><h1>Admin Login</h1>"
                b'<form method="post">'
                b'<label>Username or Email: <input name="username" /></label><br/>'
                b'<label>Password: <input name="password" type="password" /></label><br/>'
                b'<label>2FA Token (optional): <input name="token" /></label><br/>'
                b'<button type="submit">Login</button>'
                b"</form></body></html>"
            )
            headers = [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Cache-Control", "no-store"),
                ("Content-Length", str(len(body))),
            ]
            start_response("200 OK", headers)
            return [body]
        # Default health responses
        body = b"ok"
        headers = [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Cache-Control", "no-store"),
            ("Content-Length", str(len(body))),
        ]
        start_response("200 OK", headers)
        return [body]
    except Exception:
        # Fallback safe response
        body = b"ok"
        headers = [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Cache-Control", "no-store"),
            ("Content-Length", str(len(body))),
        ]
        start_response("200 OK", headers)
        return [body]
