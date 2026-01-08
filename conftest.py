import pytest

# Provide a repository-level `app` fixture so pytest-flask finds it
# This delegates to `tests.conftest.app` when available (richer test factory),
# otherwise falls back to the application's `backend.appy.app`.
_app_factory = None


