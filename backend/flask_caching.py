"""Minimal shim for ``flask_caching`` used in CI.

This provides a tiny, no-op :class:`Cache` with the minimal API the
application imports (``from flask_caching import Cache``). It's intended
only to satisfy import-time references during tests when the real
``Flask-Caching`` package is not installed in CI.
"""


class Cache:
    def __init__(self, app=None, **kwargs):
        self.app = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app

    def get(self, key, default=None):
        return default

    def set(self, key, value, timeout=None):
        return True

    def delete(self, key):
        return True

    def clear(self):
        return True
