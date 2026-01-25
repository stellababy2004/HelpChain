from __future__ import annotations

import os
from dotenv import load_dotenv
from flask import Flask, request, session
from flask_login import LoginManager
from flask_wtf.csrf import generate_csrf
from flask_babel import get_locale as babel_get_locale

from backend.extensions import babel, db, migrate
from backend.models import AdminUser

load_dotenv()

SUPPORTED_LOCALES = {"bg", "fr", "en"}
DEFAULT_LOCALE = "en"
FR_CORE_REGIONS = {"FR", "CA", "CH"}


def select_locale():
    # 0) Език от URL ?lang=fr  (най-висок приоритет за тестове и ръчни линкове)
    url_lang = (request.args.get("lang") or "").lower()
    if url_lang in SUPPORTED_LOCALES:
        session["lang"] = url_lang
        session.pop("show_lang_choice_banner", None)
        return url_lang

    # 1) Cookie
    cookie_lang = (request.cookies.get("hc_lang") or "").lower()
    if cookie_lang in SUPPORTED_LOCALES:
        session.pop("show_lang_choice_banner", None)
        return cookie_lang

    # 2) Session
    sess_lang = (session.get("lang") or "").lower()
    if sess_lang in SUPPORTED_LOCALES:
        session.pop("show_lang_choice_banner", None)
        return sess_lang

    # 3) Accept-Language (компромисната логика за FR)
    best = request.accept_languages.best_match(["bg", "fr", "en"])

    header = request.headers.get("Accept-Language", "") or ""
    primary = header.split(",")[0].strip()
    region = None
    if "-" in primary:
        parts = primary.split("-", 1)
        if parts[0].lower() == "fr":
            region = parts[1].upper()

    if best == "fr":
        if region and region not in FR_CORE_REGIONS:
            session["show_lang_choice_banner"] = True
        else:
            session.pop("show_lang_choice_banner", None)
        return "fr"

    session.pop("show_lang_choice_banner", None)
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
    app.config.setdefault(
        "SQLALCHEMY_DATABASE_URI",
        os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///helpchain.db"),
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
        babel.init_app(app, locale_selector=select_locale)
    except TypeError:
        babel.init_app(app)

        @babel.localeselector
        def _get_locale():
            return select_locale()

    # Ensure models are imported so Alembic sees them
    with app.app_context():
        import backend.models  # noqa
        import backend.models_with_analytics  # noqa

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

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
