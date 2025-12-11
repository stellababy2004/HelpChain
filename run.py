import os
import sys

# Change to backend directory to make it the working directory
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
os.chdir(backend_dir)

# Add the backend directory to Python path so we can import modules
sys.path.insert(0, backend_dir)

# Also add the src directory for direct imports
src_dir = os.path.join(backend_dir, "helpchain-backend", "src")
sys.path.insert(0, src_dir)

# Import and run the app
# Workaround: ensure older Flask/extension imports that expect
# `werkzeug.urls.url_quote` don't fail if the installed Werkzeug
# version exposes a renamed function. This monkeypatch is local to
# the process and only runs before importing the app.
try:
    import werkzeug.urls as _werkzeug_urls

    if not hasattr(_werkzeug_urls, "url_quote"):
        from urllib.parse import quote as _qp

        def url_quote(value: str) -> str:  # simple alias with safe=""
            return _qp(value, safe="")

        _werkzeug_urls.url_quote = url_quote  # type: ignore[attr-defined]
except Exception:
    # If anything goes wrong here, fall back to normal import and let
    # the original ImportError surface so it can be handled upstream.
    pass

# Workaround for Flask-SQLAlchemy expecting `flask.globals.app_ctx`.
# Newer Flask versions don't expose `app_ctx` directly; create a
# LocalProxy alias pointing at the app context top so older
# extensions that import `app_ctx` keep working.
try:
    import flask.globals as _flask_globals

    if not hasattr(_flask_globals, "app_ctx"):
        from werkzeug.local import LocalProxy

        _flask_globals.app_ctx = LocalProxy(lambda: _flask_globals._app_ctx_stack.top)  # type: ignore[attr-defined]
except Exception:
    # If this fails, continue and let the import error surface later.
    pass

try:
    from backend.app import app
except Exception:
    # Fallback: some developer environments use `backend.appy` (legacy
    # or alternate entrypoint) which registers additional routes such as
    # `/logout`. Attempt to import it when `backend.app` doesn't expose
    # the expected application object.
    try:
        from backend.appy import app
    except Exception:
        # Re-raise the original error to preserve the traceback when
        # both imports fail.
        raise

# Disabled Flask auto-reloader to prevent incorrect restart behavior
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
