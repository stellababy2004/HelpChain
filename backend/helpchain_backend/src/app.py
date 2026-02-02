from __future__ import annotations

import os
from dotenv import load_dotenv
from flask import Flask, request, session
from flask_login import LoginManager
from flask_wtf.csrf import generate_csrf
from flask_babel import get_locale as babel_get_locale

from backend.extensions import babel, db, migrate
from backend.models import AdminUser
from backend.helpchain_backend.src.statuses import (
    REQUEST_STATUS_META,
    REQUEST_STATUS_ORDER,
    normalize_request_status,
)

load_dotenv()

SUPPORTED_LOCALES = ("bg", "fr", "en")
DEFAULT_LOCALE = "en"


def _country_from_headers() -> str | None:
    """Extract country code from common edge/CDN headers."""
    for header in ("CF-IPCountry", "X-Vercel-IP-Country", "X-Country"):
        cc = request.headers.get(header)
        if cc:
            return cc.upper()
    return None


def _locale_selector():
    # 1) Explicit query param always wins
    q = (request.args.get("lang") or "").lower()
    if q in SUPPORTED_LOCALES:
        session["lang"] = q
        return q

    # 2) Explicit cookie / session choice
    for source in ((request.cookies.get("hc_lang") or ""), (session.get("lang") or "")):
        val = source.lower()
        if val in SUPPORTED_LOCALES:
            return val

    # 3) Country-based default
    cc = _country_from_headers()
    if cc == "BG":
        return "bg"
    if cc == "FR":
        return "fr"

    # 4) Browser preference, then default
    best = request.accept_languages.best_match(SUPPORTED_LOCALES)
    return best or DEFAULT_LOCALE


def create_app(config_object=None) -> Flask:
    """
    Single source of truth for app factory.
    Uses root-level /templates and /static as the template/static folders.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    root_templates = os.path.abspath(os.path.join(base_dir, "..", "..", "..", "templates"))
    root_static = os.path.abspath(os.path.join(base_dir, "..", "..", "..", "static"))
    root_translations = os.path.abspath(os.path.join(base_dir, "..", "..", "..", "translations"))

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
    instance_db_path = os.path.join(os.path.abspath(os.path.join(base_dir, "..", "..", "..")), "instance", "app.db")
    app.config.setdefault(
        "SQLALCHEMY_DATABASE_URI",
        os.getenv("SQLALCHEMY_DATABASE_URI")
        or os.getenv("DATABASE_URL")
        or f"sqlite:///{instance_db_path}",
    )
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault("BABEL_TRANSLATION_DIRECTORIES", root_translations)

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

    # i18n (Babel)
    try:
        babel.init_app(app, locale_selector=_locale_selector)
    except TypeError:
        babel.init_app(app)

        @babel.localeselector
        def _get_locale():
            return _locale_selector()

    # Ensure models are imported so Alembic sees them
    with app.app_context():
        import backend.models  # noqa
        import backend.models_with_analytics  # noqa
        import backend.helpchain_backend.src.models.volunteer_interest  # noqa

    # CSRF helper for Jinja (if templates call {{ csrf_token() }})
    app.jinja_env.globals["csrf_token"] = generate_csrf
    app.jinja_env.globals["get_locale"] = babel_get_locale

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

    # Status helpers for templates
    @app.context_processor
    def inject_status_helpers():
        def status_meta(s: str):
            key = normalize_request_status(s)
            return REQUEST_STATUS_META.get(
                key,
                {
                    "label": key or "—",
                    "icon": "bi-question-circle",
                    "badge_class": "badge bg-light text-dark",
                },
            )

        return {
            "REQUEST_STATUS_META": REQUEST_STATUS_META,
            "REQUEST_STATUS_ORDER": REQUEST_STATUS_ORDER,
            "status_meta": status_meta,
        }

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
