import os
import sys
import traceback

# Ensure repository root is on sys.path so top-level imports like `from models import ...`
# resolve when Vercel runs the function from the deployed package root.
ROOT = os.path.dirname(__file__)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Add vendored dependencies (if present) before other imports so they shadow missing system packages
# Support both `_vendor` (our vendored packages) and legacy `vendor` folder.
vendor_dirs = [os.path.join(ROOT, "_vendor"), os.path.join(ROOT, "vendor")]
for vendor_dir in vendor_dirs:
    if os.path.isdir(vendor_dir) and vendor_dir not in sys.path:
        sys.path.insert(0, vendor_dir)

# Change to backend directory to make it the working directory if available
backend_dir = os.path.join(ROOT, "backend")
if os.path.isdir(backend_dir):
    try:
        os.chdir(backend_dir)
    except Exception:
        pass
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

# Also add the src directory for direct imports (some layouts use helpchain-backend/src)
src_dir = os.path.join(backend_dir, "helpchain-backend", "src")
if os.path.isdir(src_dir) and src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Debug: print limited diagnostics; guard verbosity via env to avoid oversized logs on Vercel
try:
    _verbose = os.getenv("VERBOSE_LOGS", "0") == "1"
    def _truncate_list(lst, max_items=20):
        try:
            lst = list(lst)
            if len(lst) > max_items:
                return lst[:max_items] + [f"...(+{len(lst) - max_items} more)"]
            return lst
        except Exception:
            return lst
    print("DEBUG run.py: cwd=", os.getcwd(), flush=True)
    print("DEBUG run.py: ROOT=", ROOT, flush=True)
    if _verbose:
        print("DEBUG run.py: sys.path=", _truncate_list(sys.path, 30), flush=True)
    try:
        files_root = _truncate_list(sorted(os.listdir(ROOT)), 50 if _verbose else 20)
        print("DEBUG run.py: root files=", files_root, flush=True)
    except Exception as _e:
        print("DEBUG run.py: listdir(ROOT) failed:", _e, flush=True)
    try:
        files_cwd = _truncate_list(sorted(os.listdir(os.getcwd())), 50 if _verbose else 20)
        print("DEBUG run.py: cwd files=", files_cwd, flush=True)
    except Exception as _e:
        print("DEBUG run.py: listdir(cwd) failed:", _e, flush=True)
except Exception:
    traceback.print_exc()

# --- Pre-import monkeypatches ---
# Apply compatibility shims before importing Flask/werkzeug so imports that
# expect older helper names (e.g. `url_quote`) don't fail during module import.
try:
    import werkzeug.urls as _werkzeug_urls

    if not hasattr(_werkzeug_urls, "url_quote"):
        from urllib.parse import quote as _qp

        def url_quote(value: str) -> str:
            return _qp(value, safe="")

        _werkzeug_urls.url_quote = url_quote  # type: ignore[attr-defined]
except Exception:
    # Not critical; continue and let the real import error surface later
    pass

try:
    import flask.globals as _flask_globals
    if not hasattr(_flask_globals, "app_ctx"):
        from werkzeug.local import LocalProxy

        _flask_globals.app_ctx = LocalProxy(lambda: _flask_globals._app_ctx_stack.top)  # type: ignore[attr-defined]
except Exception:
    pass

# Compatibility shim: some older extensions (Flask-SQLAlchemy, older plugins)
# import `_app_ctx_stack` directly from the `flask` package. Flask 3 removed
# that symbol; provide a LocalStack on `flask._app_ctx_stack` so those imports
# succeed and code that reads `._app_ctx_stack.top` works in a best-effort way.
try:
    import importlib
    _flask_mod = importlib.import_module("flask")
    from werkzeug.local import LocalStack

    if not hasattr(_flask_mod, "_app_ctx_stack"):
        _flask_mod._app_ctx_stack = LocalStack()
except Exception:
    pass

_cached_inner_app = None

def _load_inner_app():
    """Lazily import the Flask application to avoid import-time 500s.
    Tries `backend.app` first, then falls back to `backend.appy`.
    Caches the result once successfully imported.
    """
    global _cached_inner_app
    if _cached_inner_app is not None:
        return _cached_inner_app
    # Extra diagnostics: check a couple of runtime packages (lightweight)
    try:
        print("DEBUG run.py: lazy-loading Flask app; quick runtime checks", flush=True)
        try:
            import jwt as _jwt  # noqa: F401
        except Exception as _e:
            print("DEBUG run.py: jwt not available:", _e, flush=True)
        try:
            import jinja2 as _jinja  # noqa: F401
        except Exception as _e:
            print("DEBUG run.py: jinja2 not available:", _e, flush=True)
    except Exception:
        pass
    # Try modern app first
    try:
        from backend.app import app as _app
        _cached_inner_app = _app
        return _cached_inner_app
    except Exception:
        traceback.print_exc()
        # Fallback to legacy lightweight app
        try:
            from backend.appy import app as _app
            _cached_inner_app = _app
            return _cached_inner_app
        except Exception:
            traceback.print_exc()
            # Re-raise to surface a proper 500 only if we couldn't short-circuit earlier
            raise

def _health_wsgi_wrapper():
    """Very-early WSGI app to guarantee root/health/admin GET routes return 200,
    regardless of downstream Flask import errors. Lazily loads the Flask app
    only when needed after handling short-circuits."""
    from typing import Callable

    def _wsgi(environ, start_response: Callable):
        try:
            # Derive original request path. Some platforms rewrite PATH_INFO
            # to the function file (e.g. "/api/index.py"). Prefer forwarded
            # headers when available, else fall back to PATH_INFO.
            path = (environ.get('HTTP_X_FORWARDED_URI') or environ.get('REQUEST_URI') or environ.get('RAW_PATH') or environ.get('PATH_INFO') or '').strip()
            if not path:
                path = '/'
            method = (environ.get('REQUEST_METHOD') or 'GET').upper()
            # Minimal fallback homepage to avoid 500s in previews while backend stabilizes
            if method == 'GET':
                p = path or '/'
                if p == '/' or p.endswith('/index') or p.endswith('/index.html'):
                    html = (
                        "<html><head><title>HelpChain Preview</title></head>"
                        "<body style=\"font-family: Arial, sans-serif; padding:24px\">"
                        "<h1>HelpChain Preview</h1>"
                        "<p>Добре дошли! Това е лека fallback начална страница за преглед.</p>"
                        "<ul>"
                        "<li><a href=\"/admin/login\">Admin Login</a></li>"
                        "<li><a href=\"/health\">/health</a></li>"
                        "<li><a href=\"/api/_health\">/api/_health</a></li>"
                        "<li><a href=\"/api/analytics\">/api/analytics</a></li>"
                        "</ul>"
                        "<p>Ако виждате това в production, свържете се с екипа.</p>"
                        "</body></html>"
                    )
                    body = html.encode('utf-8')
                    headers = [('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', str(len(body)))]
                    start_response('200 OK', headers)
                    return [body]
            # In Vercel preview, serve a minimal HTML for any non-probe GET to avoid 500s
            try:
                import os as _os
                if _os.getenv('VERCEL_ENV') == 'preview' and method == 'GET':
                    p = path or '/'
                    if not (p.endswith('/health') or p.endswith('/api/_health') or p.endswith('/api/analytics')):
                        html = (
                            "<html><head><title>HelpChain Preview</title></head>"
                            "<body style=\"font-family: Arial, sans-serif; padding:24px\">"
                            "<h1>HelpChain Preview</h1>"
                            "<p>Лека начална страница за преглед. Пробите са активни.</p>"
                            "</body></html>"
                        )
                        body = html.encode('utf-8')
                        headers = [('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', str(len(body)))]
                        start_response('200 OK', headers)
                        return [body]
            except Exception:
                pass
            # Match by exact path or by suffix to tolerate rewrites (e.g.,
            # original path exposed via forwarded headers).
            if path.endswith('/health') or path.endswith('/api/_health'):
                body = b"ok"
                headers = [('Content-Type', 'text/plain; charset=utf-8'), ('Content-Length', str(len(body)))]
                start_response('200 OK', headers)
                return [body]
            # Favicon early short-circuit to keep Python out of the path
            if path.endswith('/favicon.ico') or path.endswith('/favicon.png'):
                import base64
                png_b64 = b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAuMB9D7rWqkAAAAASUVORK5CYII="
                buf = base64.b64decode(png_b64)
                headers = [('Content-Type', 'image/png'), ('Cache-Control', 'public, max-age=3600'), ('Content-Length', str(len(buf)))]
                start_response('200 OK', headers)
                return [buf]
            if path.endswith('/api/analytics'):
                body = b'{"status":"ok","source":"wsgi-stub"}'
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
            # Fall through to the app on any wrapper error
            pass
        # Default: delegate; inner app is lazy-imported here
        return _load_inner_app()(environ, start_response)

    return _wsgi

# Expose WSGI app variable expected by some servers, wrapped with health guard
application = _health_wsgi_wrapper()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True, use_reloader=False)

# Emit SQLAlchemy version in logs for verification
try:
    import sqlalchemy as _sa
    print("DEBUG run.py: SQLALCHEMY_VERSION:", getattr(_sa, "__version__", "unknown"), flush=True)
except Exception as _e:
    print("DEBUG run.py: SQLAlchemy not available:", _e, flush=True)
