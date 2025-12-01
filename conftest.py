import pytest

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
