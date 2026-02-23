from flask_babel import Babel
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

# Core extensions
db = SQLAlchemy()
mail = Mail()
babel = Babel()
migrate = Migrate()
csrf = CSRFProtect()

# Rate limiter (REQUIRED by routes/main.py)
limiter = Limiter(key_func=get_remote_address)


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
