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

def app(environ, start_response: Callable):
    try:
        path = (environ.get('HTTP_X_FORWARDED_URI') or environ.get('REQUEST_URI') or environ.get('RAW_PATH') or environ.get('PATH_INFO') or '').strip()
        if not path:
            path = '/'
        method = (environ.get('REQUEST_METHOD') or 'GET').upper()
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
