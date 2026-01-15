from __future__ import annotations

import os
from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import generate_csrf

from backend.extensions import db, migrate
from backend.models import AdminUser

load_dotenv()


def create_app(config_object=None) -> Flask:
    """
    Single source of truth for app factory.
    Uses root-level /templates and /static as the template/static folders.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    root_templates = os.path.abspath(os.path.join(base_dir, "..", "..", "..", "templates"))
    root_static = os.path.abspath(os.path.join(base_dir, "..", "..", "..", "static"))

    app = Flask(__name__, instance_relative_config=True, template_folder=root_templates, static_folder=root_static)

    # Config: caller overrides, then Config class, then env defaults
    if isinstance(config_object, dict):
        app.config.update(config_object)
    try:
        from .config import Config as _Cfg

        app.config.from_object(_Cfg)
    except Exception:
        pass

    app.config["PROPAGATE_EXCEPTIONS"] = True
    app.config.setdefault(
        "SQLALCHEMY_DATABASE_URI",
        os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///helpchain.db"),
    )
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)

    # Secrets
    if not app.config.get("SECRET_KEY"):
        secret = os.environ.get("SECRET_KEY")
        if not secret:
            load_dotenv()
            secret = os.environ.get("SECRET_KEY")
        if not secret:
            secret = "dev-only-change-me-please"
            app.logger.warning("SECRET_KEY missing. Using DEV fallback. Set SECRET_KEY via env/instance config.")
        app.config["SECRET_KEY"] = secret
    app.config.setdefault("JWT_SECRET_KEY", os.getenv("JWT_SECRET_KEY", app.config.get("SECRET_KEY")))

    # Web push (VAPID) defaults
    app.config.setdefault("VAPID_PUBLIC_KEY", os.getenv("VAPID_PUBLIC_KEY"))
    app.config.setdefault("VAPID_PRIVATE_KEY", os.getenv("VAPID_PRIVATE_KEY"))
    app.config.setdefault("VAPID_SUBJECT", os.getenv("VAPID_SUBJECT", "mailto:admin@example.com"))

    # DB + Migrate
    db.init_app(app)
    migrate.init_app(app, db)

    # Ensure models are imported so Alembic sees them
    with app.app_context():
        import backend.models  # noqa
        import backend.models_with_analytics  # noqa

    # CSRF helper for Jinja (if templates call {{ csrf_token() }})
    app.jinja_env.globals["csrf_token"] = generate_csrf

    # Login manager (admin UI)
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "admin.admin_login"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return AdminUser.query.get(int(user_id))
        except Exception:
            return None

    # Blueprints
    try:
        from .routes.api_auth import api_auth_bp

        app.register_blueprint(api_auth_bp)
    except Exception as e:
        app.logger.info("api_auth blueprint not loaded: %s", e)

    try:
        from .routes.api import api_bp

        app.register_blueprint(api_bp, url_prefix="/api")
    except Exception as e:
        app.logger.info("api blueprint not loaded: %s", e)

    try:
        from .routes.analytics import analytics_bp

        app.register_blueprint(analytics_bp)
    except Exception:
        pass

    try:
        from .routes.main import main_bp

        app.register_blueprint(main_bp)
    except Exception as e:
        app.logger.info("main blueprint not loaded: %s", e)

    try:
        from .routes.admin import admin_bp

        app.register_blueprint(admin_bp)
    except Exception as e:
        app.logger.info("admin blueprint not loaded: %s", e)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
