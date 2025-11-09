"""
Ensure tests use the same DATABASE_URL as CI by exporting the env var
early, before any test-time imports that may read configuration at import-time.

This file snippet intentionally runs before other imports in `conftest.py`.
If `DATABASE_URL` is set in the environment (CI), we make sure it's available
to code that reads environment variables at import time. If not set, we leave
the environment untouched so local development is unaffected.
"""

import os

# Propagate DATABASE_URL into os.environ as early as possible so modules that
# read configuration during import will see the CI-provided test DB.
_db_url = os.environ.get("DATABASE_URL")
if _db_url:
    os.environ["DATABASE_URL"] = _db_url
else:
    # Optional: uncomment to provide a local default when running tests
    # locally without CI. We leave commented to avoid surprising behavior.
    # os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
    pass

try:
    # If the Flask app object is already importable, set its SQLALCHEMY_DATABASE_URI
    # directly so code that reads app.config later will get the right value.
    from backend.appy import app as _app

    if _db_url:
        _app.config["SQLALCHEMY_DATABASE_URI"] = _db_url
except Exception:
    # app not available yet; the environment variable will be used when the app
    # is created/imported later.
    pass
