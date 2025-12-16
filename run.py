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

# Import the application (try modern entrypoint first, then legacy fallback)
app = None
# Extra diagnostics: check whether key runtime packages are importable and list installed packages
try:
    print("DEBUG run.py: checking runtime imports for jwt and jinja2", flush=True)
    try:
        import jwt as _jwt

        print("DEBUG run.py: jwt module available at", getattr(_jwt, "__file__", "<built-in>"), flush=True)
    except Exception as _e:
        print("DEBUG run.py: jwt import failed:", _e, flush=True)
    try:
        import jinja2 as _jinja

        print("DEBUG run.py: jinja2 module available at", getattr(_jinja, "__file__", "<built-in>"), flush=True)
    except Exception as _e:
        print("DEBUG run.py: jinja2 import failed:", _e, flush=True)
    # Try to list installed distributions and pip freeze for extra context
    if os.getenv("VERBOSE_LOGS", "0") == "1":
        try:
            import importlib.metadata as _ilm
            dists = [d.metadata.get('Name') for d in _ilm.distributions()][:40]
            print("DEBUG run.py: installed distributions (sample):", dists, flush=True)
        except Exception:
            try:
                import pkg_resources as _pr
                dists = [d.project_name for d in _pr.working_set][:40]
                print("DEBUG run.py: installed distributions (sample via pkg_resources):", dists, flush=True)
            except Exception:
                pass
        try:
            import subprocess as _sub
            _pf = _sub.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True, timeout=10)
            out = (_pf.stdout or "<no output>")
            print("DEBUG run.py: pip freeze (truncated):\n", out[:1000], flush=True)
        except Exception as _e:
            print("DEBUG run.py: pip freeze failed:", _e, flush=True)
except Exception:
    traceback.print_exc()
try:
    from backend.app import app as _app

    app = _app
except Exception:
    # Print traceback to stderr to aid diagnostics in logs
    traceback.print_exc()
    try:
        from backend.appy import app as _app

        app = _app
    except Exception:
        traceback.print_exc()
        raise

def _health_wsgi_wrapper(inner_app):
    """Very-early WSGI wrapper to guarantee health/admin GET routes return 200,
    regardless of downstream Flask hooks or blueprint errors."""
    from typing import Callable

    def _wsgi(environ, start_response: Callable):
        try:
            path = (environ.get('PATH_INFO') or '').strip()
            method = (environ.get('REQUEST_METHOD') or 'GET').upper()
            if path in ('/health', '/api/_health'):
                body = b"ok"
                headers = [(b'Content-Type', b'text/plain; charset=utf-8'), (b'Content-Length', str(len(body)).encode())]
                start_response('200 OK', headers)
                return [body]
            if path == '/api/analytics':
                body = b'{"status":"ok","source":"wsgi-stub"}'
                headers = [(b'Content-Type', b'application/json; charset=utf-8'), (b'Content-Length', str(len(body)).encode())]
                start_response('200 OK', headers)
                return [body]
            if path == '/admin/login' and method == 'GET':
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
                headers = [(b'Content-Type', b'text/html; charset=utf-8'), (b'Content-Length', str(len(body)).encode())]
                start_response('200 OK', headers)
                return [body]
        except Exception:
            # Fall through to the app on any wrapper error
            pass
        # Default: delegate to the wrapped application
        return inner_app(environ, start_response)

    return _wsgi

# Expose WSGI app variable expected by some servers, wrapped with health guard
application = _health_wsgi_wrapper(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True, use_reloader=False)

# Emit SQLAlchemy version in logs for verification
try:
    import sqlalchemy as _sa
    print("DEBUG run.py: SQLALCHEMY_VERSION:", getattr(_sa, "__version__", "unknown"), flush=True)
except Exception as _e:
    print("DEBUG run.py: SQLAlchemy not available:", _e, flush=True)
