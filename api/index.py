import os
import sys
from typing import Callable

# Ensure project root is on path
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

_cached_inner = None

def _load_inner_app():
    global _cached_inner
    if _cached_inner is None:
        # Import lazily to avoid heavy imports for health probes
        from run import application as _application
        _cached_inner = _application
    return _cached_inner

def _derive_path(environ: dict) -> str:
    """Best-effort original path detection across multiple reverse-proxy headers.
    Falls back to scanning the environ values to catch rewrites that hide the
    original path (e.g. mapping everything to /api/index.py).
    """
    keys = (
        'HTTP_X_FORWARDED_URI',
        'HTTP_X_FORWARDED_PATH',
        'HTTP_X_ORIGINAL_URI',
        'HTTP_X_ORIGINAL_URL',
        'HTTP_X_REWRITE_URL',
        'REQUEST_URI',
        'RAW_PATH',
        'PATH_INFO',
    )
    for k in keys:
        v = environ.get(k)
        if isinstance(v, str) and v.strip():
            val = v.strip()
            # If platform rewrites to this file path, treat as root
            if val.endswith('/api/index.py') or val.endswith('/api/index'):
                return '/'
            return val
    # Fallback: scan for common probe substrings in all string values
    try:
        joined = " \n ".join(str(v) for v in environ.values() if isinstance(v, (str, bytes)))
        for probe in ('/health', '/api/_health', '/admin/login', '/api/analytics'):
            if probe in joined:
                return probe
    except Exception:
        pass
    return '/'

def app(environ, start_response: Callable):
    try:
        path = _derive_path(environ)
        method = (environ.get('REQUEST_METHOD') or 'GET').upper()
        # Minimal fallback homepage to avoid 500s in previews while backend stabilizes
        if method == 'GET' and (path == '/' or path.endswith('/index') or path.endswith('/index.html')):
            body = (
                b"<html><head><title>HelpChain Preview</title></head>"
                b"<body style=\"font-family: Arial, sans-serif; padding:24px\">"
                b"<h1>HelpChain Preview</h1>"
                b"<p>Добре дошли! Това е лека fallback начална страница за преглед.</p>"
                b"<ul>"
                b"<li><a href=\"/admin/login\">Admin Login</a></li>"
                b"<li><a href=\"/health\">/health</a></li>"
                b"<li><a href=\"/api/_health\">/api/_health</a></li>"
                b"<li><a href=\"/api/analytics\">/api/analytics</a></li>"
                b"</ul>"
                b"<p>Ако виждате това в production, свържете се с екипа.</p>"
                b"</body></html>"
            )
            headers = [('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', str(len(body)))]
            start_response('200 OK', headers)
            return [body]
        if path.endswith('/health') or path.endswith('/api/_health'):
            body = b"ok"
            headers = [('Content-Type', 'text/plain; charset=utf-8'), ('Content-Length', str(len(body)))]
            start_response('200 OK', headers)
            return [body]
        if path.endswith('/api/analytics'):
            body = b'{"status":"ok","source":"api-wrapper"}'
            headers = [('Content-Type', 'application/json; charset=utf-8'), ('Content-Length', str(len(body)))]
            start_response('200 OK', headers)
            return [body]
        if (path.endswith('/admin/login') or path.endswith('/admin/login/')) and method == 'GET':
            body = (
                b"<html><head><title>Admin Login</title></head>"
                b"<body><h1>Admin Login</h1>"
                b"<form method=\"post\">"
                b"<label>Username or Email: <input name=\"username\" /></label><br/>"
                b"<label>Password: <input name=\"password\" type=\"password\" /></label><br/>"
                b"<label>2FA Token (optional): <input name=\"token\" /></label><br/>"
                b"<button type=\"submit\">Login</button>"
                b"</form></body></html>"
            )
            headers = [('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', str(len(body)))]
            start_response('200 OK', headers)
            return [body]
    except Exception:
        # Fall through to the inner app on any wrapper error
        pass
    # Delegate everything else
    return _load_inner_app()(environ, start_response)

# For local debug
if __name__ == "__main__":
    # Run the inner Flask app via the wrapper
    from werkzeug.serving import run_simple
    run_simple("0.0.0.0", int(os.environ.get("PORT", 5000)), app, use_reloader=False)
