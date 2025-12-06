#!/usr/bin/env python3
import os
import sys

# Ensure repo root is CWD so imports work
ROOT = os.path.dirname(__file__)
os.chdir(ROOT)
# Ensure backend and src are on sys.path so local imports like `dependencies` resolve
backend_dir = os.path.join(ROOT, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Also add the src directory used by some modules
src_dir = os.path.join(backend_dir, "helpchain-backend", "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Workarounds for local compatibility with installed Flask/Werkzeug versions.
# Ensure `werkzeug.urls.url_quote` and `flask.globals.app_ctx` exist before
# importing the application so imports don't fail on some environments.
try:
    import werkzeug.urls as _werkzeug_urls
    if not hasattr(_werkzeug_urls, "url_quote"):
        from urllib.parse import quote as _qp

        def url_quote(value: str) -> str:
            return _qp(value, safe="")

        _werkzeug_urls.url_quote = url_quote  # type: ignore[attr-defined]
except Exception:
    pass

try:
    import flask.globals as _flask_globals
    if not hasattr(_flask_globals, "app_ctx"):
        from werkzeug.local import LocalProxy

        _flask_globals.app_ctx = LocalProxy(lambda: _flask_globals._app_ctx_stack.top)  # type: ignore[attr-defined]
except Exception:
    pass

# Import the app and DB
from backend.app import _seed_if_empty, app
from backend.extensions import db

if __name__ == '__main__':
    with app.app_context():
        print('Creating database tables (if missing)...')
        try:
            db.create_all()
            print('Tables created or already exist.')
        except Exception as e:
            print('Error creating tables:', e)
        # Run seeder function from app (creates admin/test users/help requests)
        try:
            _seed_if_empty()
            print('Seeding completed (if necessary).')
        except Exception as e:
            print('Error during seeding:', e)
    print('Done.')
