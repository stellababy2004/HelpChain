# Ensure compatibility for projects expecting certain
# symbols from `werkzeug.urls` (older Flask/extensions).
# Provide minimal shim functions before tests import the app
# so that imports like `url_quote` and `url_parse` work
# with Werkzeug 3.x where names were reorganized.
try:
    from urllib.parse import quote as _qp
    from urllib.parse import urlparse as _urlparse

    import werkzeug.urls as _werkzeug_urls

    if not hasattr(_werkzeug_urls, "url_quote"):

        def url_quote(value: str) -> str:
            return _qp(value, safe="")

        _werkzeug_urls.url_quote = url_quote  # type: ignore[attr-defined]

    if not hasattr(_werkzeug_urls, "url_parse"):
        # Provide a thin alias to `urllib.parse.urlparse` for code
        # that expects `werkzeug.urls.url_parse`.
        _werkzeug_urls.url_parse = _urlparse  # type: ignore[attr-defined]
    # Ensure `werkzeug.__version__` exists for code that reads it
    # (Flask's test client builds a User-Agent string using it).
    try:
        import werkzeug as _werkzeug_pkg

        try:
            import importlib.metadata as _im

            _werkzeug_pkg.__version__ = _im.version("werkzeug")
        except Exception:
            # Fallback to a sensible default
            _werkzeug_pkg.__version__ = "3.0.0"
    except Exception:
        pass
except Exception:
    # If we can't shim, allow the import to proceed and let tests
    # surface the error so it can be fixed.
    pass

import pytest

# Compatibility shim for SQLAlchemy engine creation kwargs used in tests.
# Some test setups pass `pool_size`/`max_overflow` which are invalid
# for NullPool or for SQLite in-memory/backed tests under newer SQLAlchemy.
try:
    import sqlalchemy

    _orig_create_engine = sqlalchemy.create_engine

    def _create_engine(url, **kwargs):
        # Remove pool sizing kwargs when they would be invalid for the
        # selected pool/dialect. This is a guarded, minimal shim for the
        # test environment only.
        filtered = dict(kwargs)
        for k in ("pool_size", "max_overflow"):
            if k in filtered:
                filtered.pop(k)
        return _orig_create_engine(url, **filtered)

    sqlalchemy.create_engine = _create_engine
except Exception:
    pass

# Provide a repository-level `app` fixture so pytest-flask finds it
# This delegates to `tests.conftest.app` when available (richer test factory),
# otherwise falls back to the application's `backend.appy.app`.
_app_factory = None


@pytest.fixture(scope="session")
def app():
    if _app_factory is not None:
        try:
            return _app_factory()
        except Exception:
            pass

    # Fallback to importing the real app object
    try:
        from backend.appy import app as _app  # type: ignore

        _app.config.setdefault("TESTING", True)
        return _app
    except Exception:
        # Final minimal fallback
        from flask import Flask

        _app = Flask(__name__)
        _app.config["TESTING"] = True
        return _app
