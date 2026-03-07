import os

from flask_babel import Babel
from flask_mail import Mail
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

_ENV_NAME = (
    os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or os.getenv("FLASK_CONFIG") or ""
).strip().lower()
_IS_PRODUCTION = _ENV_NAME in {"prod", "production"}

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except ModuleNotFoundError as exc:
    if _IS_PRODUCTION:
        raise
    Limiter = None

    def get_remote_address():
        return "0.0.0.0"


class _NoopLimiter:
    def init_app(self, app):
        app.logger.warning(
            "flask_limiter is not installed; running with no-op rate limiting."
        )

    def _passthrough(self, *args, **kwargs):
        def _decorator(fn):
            return fn

        return _decorator

    limit = _passthrough
    shared_limit = _passthrough
    exempt = _passthrough
    request_filter = _passthrough


# Core extensions
db = SQLAlchemy()
mail = Mail()
babel = Babel()
migrate = Migrate()
csrf = CSRFProtect()

# Rate limiter (REQUIRED by routes/main.py)
limiter = Limiter(key_func=get_remote_address) if Limiter else _NoopLimiter()


def init_extensions(app):
    db.init_app(app)
    mail.init_app(app)
    babel.init_app(app)
    migrate.init_app(app, db, directory="migrations")
    limiter.init_app(app)
    csrf.init_app(app)


__all__ = [
    "db",
    "mail",
    "babel",
    "migrate",
    "limiter",
    "csrf",
    "init_extensions",
]
