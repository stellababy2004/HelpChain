from __future__ import annotations

import os

from dotenv import load_dotenv
from flask import Flask, render_template, request, session
from flask_babel import get_locale as babel_get_locale
from flask_login import LoginManager
from flask_wtf import FlaskForm
from flask_wtf.csrf import generate_csrf
from werkzeug.middleware.proxy_fix import ProxyFix

from backend.extensions import babel, csrf, db, migrate
from backend.helpchain_backend.src.security_logging import log_security_event
from backend.helpchain_backend.src.statuses import (
    REQUEST_STATUS_META,
    REQUEST_STATUS_ORDER,
    normalize_request_status,
)
from backend.models import AdminUser

load_dotenv()

SUPPORTED_LOCALES = ("bg", "fr", "en")
DEFAULT_LOCALE = "fr"

# Guard against duplicate SQLAlchemy event registration under the dev reloader.
_SLOW_SQL_HOOKS_INSTALLED = False


def _install_slow_sql_logger(app: Flask) -> None:
    """
    Dev-only: log slow SQL statements to help pinpoint admin disk I/O / N+1 / missing indexes.
    """
    global _SLOW_SQL_HOOKS_INSTALLED
    if _SLOW_SQL_HOOKS_INSTALLED:
        return

    try:
        from time import perf_counter

        from sqlalchemy import event
        from sqlalchemy.engine import Engine
    except Exception:
        return

    # Default lower threshold in dev; override per-run via HC_SLOW_QUERY_MS=10 if needed.
    try:
        SLOW_QUERY_MS = int(os.getenv("HC_SLOW_QUERY_MS", "50"))
    except Exception:
        SLOW_QUERY_MS = 50

    @event.listens_for(Engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        context._query_start_time = perf_counter()

    @event.listens_for(Engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        start = getattr(context, "_query_start_time", None)
        if start is None:
            return
        total_ms = (perf_counter() - start) * 1000
        if total_ms >= SLOW_QUERY_MS:
            try:
                app.logger.warning("SLOW SQL (%.1f ms): %s", total_ms, (statement or "")[:500])
            except Exception:
                pass

    _SLOW_SQL_HOOKS_INSTALLED = True


def _locale_selector():
    # Priority order:
    # 1) explicit query param (?lang=fr)
    # 2) session ("lang")
    # 3) cookie ("hc_lang")
    # 4) Accept-Language header
    # 5) default

    q = (request.args.get("lang") or "").lower().strip()
    if q in SUPPORTED_LOCALES:
        session["lang"] = q
        return q

    s = (session.get("lang") or "").lower().strip()
    if s in SUPPORTED_LOCALES:
        return s

    c = (request.cookies.get("hc_lang") or "").lower().strip()
    if c in SUPPORTED_LOCALES:
        return c

    return request.accept_languages.best_match(SUPPORTED_LOCALES) or DEFAULT_LOCALE


def add_security_headers(app: Flask):
    @app.after_request
    def _set_security_headers(resp):
        # Baseline hardening
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=(), payment=(), usb=(), fullscreen=(self)"
        resp.headers["X-Frame-Options"] = "DENY"

        # CSP (start with Report-Only to avoid breaking inline scripts/styles)
        csp = (
            "default-src 'self'; "
            "base-uri 'self'; "
            "object-src 'none'; "
            "frame-ancestors 'none'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https:; "
            "style-src 'self' 'unsafe-inline' https:; "
            "script-src 'self' 'unsafe-inline' https:; "
            "connect-src 'self' https:; "
            "form-action 'self'; "
        )
        resp.headers["Content-Security-Policy-Report-Only"] = csp

        # HSTS only when really on HTTPS and in production-ish env
        if app.config.get("ENV") == "production" or app.config.get("APP_ENV") == "production" or ((app.config.get("FLASK_CONFIG") or "").lower() in ("prod", "production")):
            if request.is_secure:
                resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Strip Server header if present
        resp.headers.pop("Server", None)
        return resp

    return app


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
        from .config import DevConfig, ProdConfig

        env_name = (os.getenv("FLASK_CONFIG") or os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or "").lower()
        if config_object and not isinstance(config_object, dict):
            app.config.from_object(config_object)
        elif env_name in ("prod", "production"):
            app.config.from_object(ProdConfig)
        elif env_name in ("dev", "development"):
            app.config.from_object(DevConfig)
        else:
            app.config.from_object(_Cfg)
    except Exception:
        pass

    # Dev safety: if someone has SESSION_COOKIE_SECURE=1 in their environment but
    # is serving locally over plain HTTP, session cookies won't be sent and CSRF
    # will fail with "CSRF session token is missing".
    if app.debug or app.config.get("DEBUG"):
        app.config["SESSION_COOKIE_SECURE"] = False

    app.config["PROPAGATE_EXCEPTIONS"] = True
    instance_db_path = os.path.join(os.path.abspath(os.path.join(base_dir, "..", "..", "..")), "instance", "app.db")
    app.config.setdefault(
        "SQLALCHEMY_DATABASE_URI",
        os.getenv("SQLALCHEMY_DATABASE_URI") or os.getenv("DATABASE_URL") or f"sqlite:///{instance_db_path}",
    )
    # Serverless / preview safety: never leave URI empty
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault("BABEL_TRANSLATION_DIRECTORIES", root_translations)
    # FR-first: keep a single default locale across dev/prod unless explicitly overridden by env.
    app.config["BABEL_DEFAULT_LOCALE"] = os.getenv("BABEL_DEFAULT_LOCALE", DEFAULT_LOCALE)
    app.config["BABEL_DEFAULT_TIMEZONE"] = os.getenv("BABEL_DEFAULT_TIMEZONE", "Europe/Paris")

    # Secrets
    if not app.config.get("SECRET_KEY"):
        secret = os.environ.get("SECRET_KEY")
        if not secret:
            load_dotenv()
            secret = os.environ.get("SECRET_KEY")
        if not secret:
            secret = "dev-only-change-me"
            app.logger.warning("SECRET_KEY missing. Using DEV fallback. Set SECRET_KEY via env/instance config.")
        app.config["SECRET_KEY"] = secret
    app.config.setdefault("JWT_SECRET_KEY", os.getenv("JWT_SECRET_KEY", app.config.get("SECRET_KEY")))

    # Behind one proxy hop: trust X-Forwarded-For/Proto/Host early
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    if app.debug or app.config.get("DEBUG"):
        try:
            app.logger.info(
                "DEV cookies: SESSION_COOKIE_SECURE=%s SESSION_COOKIE_SAMESITE=%s",
                app.config.get("SESSION_COOKIE_SECURE"),
                app.config.get("SESSION_COOKIE_SAMESITE"),
            )
        except Exception:
            pass

    # Web push (VAPID) defaults
    app.config.setdefault("VAPID_PUBLIC_KEY", os.getenv("VAPID_PUBLIC_KEY"))
    app.config.setdefault("VAPID_PRIVATE_KEY", os.getenv("VAPID_PRIVATE_KEY"))
    app.config.setdefault("VAPID_SUBJECT", os.getenv("VAPID_SUBJECT", "mailto:admin@example.com"))

    # DB + Migrate
    db.init_app(app)
    if app.debug or app.config.get("DEBUG"):
        _install_slow_sql_logger(app)
    migrate.init_app(app, db)

    # i18n (Babel)
    babel.init_app(app, locale_selector=_locale_selector)

    # CSRF for browser forms (JWT APIs are exempted per-blueprint)
    csrf.init_app(app)

    # Global CSRF form for templates (navbar/logout and inline actions)
    class CSRFOnlyForm(FlaskForm):
        pass

    @app.context_processor
    def inject_csrf_form():
        return {"csrf_form": CSRFOnlyForm()}

    @app.after_request
    def add_content_language_header(resp):
        # Surface the resolved locale for debugging and intermediaries.
        try:
            resp.headers["Content-Language"] = str(babel_get_locale())
        except Exception:
            pass
        return resp

    # Ensure models are imported so Alembic sees them
    with app.app_context():
        # Single canonical model import (avoid multiple MetaData instances)
        import backend.helpchain_backend.src.models  # noqa

    # CSRF helper for Jinja (if templates call {{ csrf_token() }})
    app.jinja_env.globals["csrf_token"] = generate_csrf
    app.jinja_env.globals["get_locale"] = babel_get_locale

    # Login manager (admin UI)
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "admin.ops_login"
    login_manager.login_message = None

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

    @app.errorhandler(404)
    def not_found(e):
        # Keep privacy semantics (404) but give volunteers a human fallback page.
        try:
            path = request.path or ""
        except Exception:
            path = ""

        if path.startswith("/volunteer/"):
            return render_template("volunteer_404.html"), 404

        # If a global 404 template doesn't exist, fall back to Flask's default.
        try:
            return render_template("404.html"), 404
        except Exception:
            return e, 404

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

    add_security_headers(app)

    @app.context_processor
    def inject_config_flags():
        try:
            from flask import current_app as _ca

            return {
                "VOLUNTEER_DEV_BYPASS_ENABLED": _ca.config.get("VOLUNTEER_DEV_BYPASS_ENABLED"),
                "VOLUNTEER_DEV_BYPASS_EMAIL": _ca.config.get("VOLUNTEER_DEV_BYPASS_EMAIL"),
            }
        except Exception:
            return {}

    @app.context_processor
    def inject_unread_notification_count():
        """
        Expose unread notification count globally (for volunteer navbar badge).
        Only computed when a volunteer is logged in.
        """
        try:
            vid = session.get("volunteer_id")
            # keep backward compatibility with existing session flag, but don't require it
            if not vid:
                return {"unread_volunteer_notifs": 0, "VOLUNTEER_UNREAD_NOTIF_COUNT": 0}

            from backend.models import Notification

            cnt = Notification.query.filter_by(volunteer_id=vid, is_read=False).count()
            return {
                "unread_volunteer_notifs": cnt,
                "VOLUNTEER_UNREAD_NOTIF_COUNT": cnt,  # legacy template var
            }
        except Exception:
            return {"unread_volunteer_notifs": 0, "VOLUNTEER_UNREAD_NOTIF_COUNT": 0}

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
