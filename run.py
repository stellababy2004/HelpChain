import os
import sys
import traceback

# Ensure repository root is on sys.path so top-level imports like `from models import ...`
# resolve when Vercel runs the function from the deployed package root.
ROOT = os.path.dirname(__file__)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

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

# Debug: print sys.path and deployed files to help Vercel logs diagnose missing packages/files
try:
    print("DEBUG run.py: cwd=", os.getcwd(), flush=True)
    print("DEBUG run.py: ROOT=", ROOT, flush=True)
    print("DEBUG run.py: sys.path=", sys.path, flush=True)
    try:
        print("DEBUG run.py: root files=", sorted(os.listdir(ROOT)), flush=True)
    except Exception as _e:
        print("DEBUG run.py: listdir(ROOT) failed:", _e, flush=True)
    try:
        print("DEBUG run.py: cwd files=", sorted(os.listdir(os.getcwd())), flush=True)
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

# Expose WSGI app variable expected by some servers
application = app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True, use_reloader=False)
