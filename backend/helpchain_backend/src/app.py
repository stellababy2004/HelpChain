from __future__ import annotations

import json
import os
import threading
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, g, jsonify, make_response, render_template, request, session
from flask_babel import get_locale as babel_get_locale
from flask_babel import gettext as babel_gettext
from flask_login import LoginManager
from flask_wtf.csrf import generate_csrf
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy.exc import OperationalError, ProgrammingError

try:
    from backend.extensions import babel, csrf, db, mail, migrate
except ModuleNotFoundError:
    from .extensions import babel, csrf, db, mail, migrate

from .security_logging import log_security_event

from .statuses import REQUEST_STATUS_META, REQUEST_STATUS_ORDER, normalize_request_status

try:
    from backend.models import AdminUser
except ModuleNotFoundError:
    from models import AdminUser

load_dotenv()

SUPPORTED_LOCALES = (
    "fr",
    "en",
    "de",
    "bg",
)
DEFAULT_LOCALE = "fr"

# Guard against duplicate SQLAlchemy event registration under the dev reloader.
_SLOW_SQL_HOOKS_INSTALLED = False
_L10N_MISSING_SEEN: set[str] = set()
_L10N_MISSING_LOCK = threading.Lock()


def _init_sentry_if_configured(app: Flask, env_name: str) -> None:
    """
    Optional Sentry setup. Safe no-op when SENTRY_DSN is absent or SDK is missing.
    """
    dsn = (os.getenv("SENTRY_DSN") or app.config.get("SENTRY_DSN") or "").strip()
    if not dsn:
        app.logger.info("Sentry disabled (SENTRY_DSN not set)")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
    except Exception as exc:
        app.logger.warning("Sentry requested but sentry_sdk is unavailable: %s", exc)
        return

    def _before_send(event, hint):
        # Minimize accidental PII leakage from request payloads.
        request_data = event.get("request")
        if isinstance(request_data, dict):
            request_data.pop("data", None)
            request_data.pop("cookies", None)
            headers = request_data.get("headers")
            if isinstance(headers, dict):
                for key in list(headers.keys()):
                    k = str(key).lower()
                    if k in {"authorization", "cookie", "set-cookie", "x-api-key"}:
                        headers[key] = "[Filtered]"
        return event

    environment = (
        os.getenv("SENTRY_ENVIRONMENT")
        or app.config.get("SENTRY_ENVIRONMENT")
        or env_name
        or "unknown"
    )
    release = (os.getenv("SENTRY_RELEASE") or app.config.get("SENTRY_RELEASE") or "").strip() or None
    try:
        traces_sample_rate = float(
            os.getenv("SENTRY_TRACES_SAMPLE_RATE")
            or app.config.get("SENTRY_TRACES_SAMPLE_RATE")
            or 0.0
        )
    except Exception:
        traces_sample_rate = 0.0

    sentry_sdk.init(
        dsn=dsn,
        integrations=[FlaskIntegration()],
        environment=environment,
        release=release,
        traces_sample_rate=traces_sample_rate,
        send_default_pii=False,
        before_send=_before_send,
    )
    app.logger.info("Sentry enabled (environment=%s)", environment)


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
    def before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        context._query_start_time = perf_counter()

    @event.listens_for(Engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        start = getattr(context, "_query_start_time", None)
        if start is None:
            return
        total_ms = (perf_counter() - start) * 1000
        if total_ms >= SLOW_QUERY_MS:
            try:
                app.logger.warning(
                    "SLOW SQL (%.1f ms): %s", total_ms, (statement or "")[:500]
                )
            except Exception:
                pass

    _SLOW_SQL_HOOKS_INSTALLED = True


def _locale_selector():
    # Honor explicit user choice first, but only for locales we actually ship.
    candidates = [
        (session.get("lang") or "").strip().lower(),
        (request.cookies.get("hc_lang") or "").strip().lower(),
    ]
    for cand in candidates:
        if cand in SUPPORTED_LOCALES:
            return cand
        short = cand.split("-")[0] if cand else ""
        if short in SUPPORTED_LOCALES:
            return short

    try:
        best = request.accept_languages.best_match(SUPPORTED_LOCALES)
        if best:
            return best
    except Exception:
        pass
    return DEFAULT_LOCALE


def add_security_headers(app: Flask):
    def _origin_from_url(url: str) -> str:
        try:
            parsed = urlparse(url or "")
            if parsed.scheme and parsed.netloc:
                return f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            return ""
        return ""

    @app.after_request
    def _set_security_headers(resp):
        # Baseline hardening
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=(), fullscreen=(self)"
        )
        resp.headers["X-Frame-Options"] = "DENY"

        plausible_enabled = bool(app.config.get("PLAUSIBLE_ENABLED", False))
        plausible_script_url = (app.config.get("PLAUSIBLE_SCRIPT_URL") or "").strip()
        plausible_api_host = (app.config.get("PLAUSIBLE_API_HOST") or "").strip()

        script_src = ["'self'"]
        style_src = ["'self'", "'unsafe-inline'"]
        connect_src = ["'self'"]
        img_src = ["'self'", "data:"]
        # Allow restrained map assets for admin territorial risk map.
        map_script_origin = "https://unpkg.com"
        map_tile_origin = "https://*.tile.openstreetmap.org"
        if map_script_origin not in script_src:
            script_src.append(map_script_origin)
        if map_script_origin not in style_src:
            style_src.append(map_script_origin)
        if map_tile_origin not in img_src:
            img_src.append(map_tile_origin)
        if plausible_enabled:
            script_origin = _origin_from_url(plausible_script_url)
            api_origin = _origin_from_url(plausible_api_host) or script_origin
            if script_origin and script_origin not in script_src:
                script_src.append(script_origin)
            if api_origin and api_origin not in connect_src:
                connect_src.append(api_origin)

        # CSP enforce policy
        csp_enforce = (
            "default-src 'self'; " + f"script-src {' '.join(script_src)}; "
            "script-src-attr 'none'; "
            f"style-src {' '.join(style_src)}; "
            f"img-src {' '.join(img_src)}; "
            "font-src 'self'; " + f"connect-src {' '.join(connect_src)}; "
            "frame-ancestors 'self'; "
            "form-action 'self'; "
            "base-uri 'self'; "
            "object-src 'none'; "
            "upgrade-insecure-requests"
        )
        resp.headers["Content-Security-Policy"] = csp_enforce

        # Keep Report-Only in parallel for visibility during rollout.
        csp_report_only = f"{csp_enforce}; report-uri /csp-report"
        resp.headers["Content-Security-Policy-Report-Only"] = csp_report_only

        # HSTS only when really on HTTPS and in production-ish env
        if (
            app.config.get("ENV") == "production"
            or app.config.get("APP_ENV") == "production"
            or (
                (app.config.get("FLASK_CONFIG") or "").lower() in ("prod", "production")
            )
        ):
            if request.is_secure:
                resp.headers["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains"
                )

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
    root_templates = os.path.abspath(
        os.path.join(base_dir, "..", "..", "..", "templates")
    )
    root_static = os.path.abspath(os.path.join(base_dir, "..", "..", "..", "static"))
    root_translations = os.path.abspath(
        os.path.join(base_dir, "..", "..", "..", "translations")
    )

    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=root_templates,
        static_folder=root_static,
    )
    try:
        from backend.core.tenant import current_structure_id
    except ModuleNotFoundError:
        from core.tenant import current_structure_id

    # Config: caller overrides, then Config class, then env defaults
    if isinstance(config_object, dict):
        app.config.update(config_object)
    try:
        from .config import Config as _Cfg
        from .config import DevConfig, ProdConfig

        env_name = (
            os.getenv("FLASK_CONFIG")
            or os.getenv("APP_ENV")
            or os.getenv("FLASK_ENV")
            or ""
        ).lower()
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

    # Local/dev safety: if tenant fallback is not explicitly configured,
    # keep default tenant enabled outside production.
    if env_name not in ("prod", "production"):
        if os.getenv("ALLOW_DEFAULT_TENANT_FALLBACK") is None:
            app.config["ALLOW_DEFAULT_TENANT_FALLBACK"] = True

    if env_name in ("prod", "production") and app.config.get(
        "VOLUNTEER_DEV_BYPASS_ENABLED"
    ):
        app.logger.warning(
            "[SECURITY] Forcing VOLUNTEER_DEV_BYPASS_ENABLED=False in production"
        )
        app.config["VOLUNTEER_DEV_BYPASS_ENABLED"] = False
        app.config["VOLUNTEER_DEV_BYPASS_EMAIL"] = ""

    app.logger.warning(
        "[ENV] PUBLIC_BASE_URL=%r | TRUST_PROXY_HEADERS=%r",
        os.getenv("PUBLIC_BASE_URL"),
        os.getenv("TRUST_PROXY_HEADERS"),
    )

    # Dev safety: if someone has SESSION_COOKIE_SECURE=1 in their environment but
    # is serving locally over plain HTTP, session cookies won't be sent and CSRF
    # will fail with "CSRF session token is missing".
    if app.debug or app.config.get("DEBUG"):
        app.config["SESSION_COOKIE_SECURE"] = False

    app.config["PROPAGATE_EXCEPTIONS"] = True
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault("BABEL_TRANSLATION_DIRECTORIES", root_translations)
    app.config.setdefault("SUPPORTED_LOCALES", list(SUPPORTED_LOCALES))
    # FR-first: keep a single default locale across dev/prod unless explicitly overridden by env.
    app.config["BABEL_DEFAULT_LOCALE"] = os.getenv(
        "BABEL_DEFAULT_LOCALE", DEFAULT_LOCALE
    )
    app.config["BABEL_DEFAULT_TIMEZONE"] = os.getenv(
        "BABEL_DEFAULT_TIMEZONE", "Europe/Paris"
    )

    # Secrets
    if not app.config.get("SECRET_KEY"):
        secret = os.environ.get("SECRET_KEY")
        if not secret:
            load_dotenv()
            secret = os.environ.get("SECRET_KEY")
        if not secret:
            secret = "dev-only-change-me"
            app.logger.warning(
                "SECRET_KEY missing. Using DEV fallback. Set SECRET_KEY via env/instance config."
            )
        app.config["SECRET_KEY"] = secret
    app.config.setdefault(
        "JWT_SECRET_KEY", os.getenv("JWT_SECRET_KEY", app.config.get("SECRET_KEY"))
    )

    _init_sentry_if_configured(app, env_name=env_name)

    # Trust proxy headers only when explicitly enabled for reverse-proxy deployments.
    if app.config.get("TRUST_PROXY_HEADERS", False):
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=int(app.config.get("PROXY_FIX_X_FOR", 1)),
            x_proto=int(app.config.get("PROXY_FIX_X_PROTO", 1)),
            x_host=int(app.config.get("PROXY_FIX_X_HOST", 1)),
        )
        app.logger.info(
            "ProxyFix enabled x_for=%s x_proto=%s x_host=%s",
            app.config.get("PROXY_FIX_X_FOR", 1),
            app.config.get("PROXY_FIX_X_PROTO", 1),
            app.config.get("PROXY_FIX_X_HOST", 1),
        )
    else:
        app.logger.info("ProxyFix disabled (TRUST_PROXY_HEADERS=false)")

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
    app.config.setdefault(
        "VAPID_SUBJECT", os.getenv("VAPID_SUBJECT", "mailto:admin@example.com")
    )

    # DB + Migrate
    db.init_app(app)
    from backend.system_guard import ensure_default_structure
    from backend.system_checks import check_database_integrity

    with app.app_context():
        if (
            not app.config.get("TESTING", False)
            and app.config.get("HC_AUTO_HEAL_DEFAULT_STRUCTURE", True)
        ):
            ensure_default_structure()
        check_database_integrity()
    # Mail (Flask-Mail): used by backend.tasks.send_email_task via backend.mail_service
    mail.init_app(app)
    if app.debug or app.config.get("DEBUG"):
        _install_slow_sql_logger(app)
    migrate.init_app(app, db, directory="migrations")

    # i18n (Babel)
    babel.init_app(app, locale_selector=_locale_selector)

    # CSRF for browser forms (JWT APIs are exempted per-blueprint)
    csrf.init_app(app)

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
        from . import models  # noqa: F401
        from .models.audit_guard import install_admin_audit_append_only_guard
        from .services.risk_engine import register_request_risk_hooks

        install_admin_audit_append_only_guard()
        register_request_risk_hooks()

    # CSRF helper for Jinja (if templates call {{ csrf_token() }})
    app.jinja_env.globals["csrf_token"] = generate_csrf
    app.jinja_env.globals["get_locale"] = babel_get_locale

    @app.template_filter("from_json")
    def from_json_filter(value):
        if not value:
            return []
        try:
            return json.loads(value)
        except Exception:
            return []

    def db_t(
        key: str,
        default: str | None = None,
        locale: str | None = None,
        domain: str | None = None,
    ) -> str:
        """
        DB translation override helper for templates.
        Usage:
          {{ t("submit_request") }}
          {{ t("submit_request", "Soumettre") }}
        """
        k = (key or "").strip()
        if not k:
            return ""

        loc = (locale or str(babel_get_locale()) or DEFAULT_LOCALE).strip().lower()
        loc_short = loc.split("-")[0]

        # Request-local cache to avoid repeated DB lookups.
        cache = getattr(g, "_ui_tr_cache", None)
        if cache is None:
            cache = {}
            g._ui_tr_cache = cache
        cache_key = f"{loc}|{k}"
        if cache_key in cache:
            return cache[cache_key]

        text = None
        try:
            try:
                from backend.models import UiTranslation
            except ModuleNotFoundError:
                from models import UiTranslation

            row = (
                UiTranslation.query.filter_by(key=k, locale=loc, is_active=True).first()
                or UiTranslation.query.filter_by(key=k, locale=loc_short, is_active=True).first()
            )
            if row and row.text:
                text = row.text
        except Exception:
            # Fail-open: never break page rendering because of i18n DB issue.
            text = None

        if not text:
            gettext_text = babel_gettext(k) or ""
            missing_gettext = (not gettext_text) or (gettext_text == k)
            if missing_gettext:
                fallback = default or k
                _log_l10n_missing_once(
                    locale=loc,
                    key=k,
                    domain=domain,
                    fallback=fallback,
                )
                text = fallback
            else:
                text = gettext_text
        cache[cache_key] = text
        return text

    app.jinja_env.globals["t"] = db_t

    # Login manager (admin UI)
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "admin.ops_login"
    login_manager.login_message = None

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(AdminUser, int(user_id))
        except Exception:
            return None

    @app.before_request
    def inject_structure_context():
        try:
            current_structure_id()
        except (OperationalError, ProgrammingError):
            # DB not ready yet (e.g., fresh instance without migrations).
            # Allow request handling to proceed; routes will handle DB errors.
            try:
                app.logger.warning(
                    "[TENANT] structure resolution skipped: DB schema unavailable."
                )
            except Exception:
                pass

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
        from .routes.social_requests import bp as social_requests_bp

        app.register_blueprint(social_requests_bp)
    except Exception as e:
        app.logger.info("social_requests blueprint not loaded: %s", e)

    try:
        from .routes.admin import admin_bp, ops_bp

        app.register_blueprint(admin_bp)
        app.register_blueprint(ops_bp)
    except Exception as e:
        app.logger.info("admin blueprint not loaded: %s", e)

    try:
        from .routes.admin_risk import admin_risk_bp

        app.register_blueprint(admin_risk_bp)
    except Exception as e:
        app.logger.info("admin_risk blueprint not loaded: %s", e)

    try:
        from .routes.organization import org_bp

        app.register_blueprint(org_bp)
    except Exception as e:
        app.logger.info("organization blueprint not loaded: %s", e)

    try:
        from .routes.admin_map import admin_map_bp

        app.register_blueprint(admin_map_bp)
    except Exception as e:
        app.logger.info("admin_map blueprint not loaded: %s", e)

    try:
        from .routes.admin_command import admin_command_bp

        app.register_blueprint(admin_command_bp)
    except Exception as e:
        app.logger.info("admin_command blueprint not loaded: %s", e)

    try:
        from .routes.risk_map import risk_map_bp

        app.register_blueprint(risk_map_bp)
    except Exception as e:
        app.logger.info("risk_map blueprint not loaded: %s", e)

    try:
        from backend.admin.ops_api import ops_api

        app.register_blueprint(ops_api)
    except Exception as e:
        app.logger.info("ops_api blueprint not loaded: %s", e)

    try:
        from backend.admin.risk_api import risk_api

        app.register_blueprint(risk_api)
    except Exception as e:
        app.logger.info("risk_api blueprint not loaded: %s", e)

    # Legacy but real RBAC admin routes (roles/permissions/users management).
    # Templates already reference endpoints under the `admin_roles` namespace.
    try:
        try:
            from backend.admin_roles import admin_roles_bp
        except ModuleNotFoundError:
            from admin_roles import admin_roles_bp

        app.register_blueprint(admin_roles_bp, url_prefix="/admin/roles")
    except Exception as e:
        app.logger.info("admin_roles blueprint not loaded: %s", e)

    def _alias_endpoint(app, alias: str, target: str, rule: str):
        # Register legacy endpoint names for template compatibility.
        view = app.view_functions.get(target)
        if not view:
            app.logger.warning("[ALIAS] target missing: %s (for %s)", target, alias)
            return
        if alias in app.view_functions:
            return
        try:
            app.add_url_rule(rule, endpoint=alias, view_func=view)
        except Exception as e:
            app.logger.info("[ALIAS] failed %s -> %s (%s): %s", alias, target, rule, e)

    # --- Legacy endpoint aliases (template compatibility) ---
    _alias_endpoint(
        app, "volunteer_settings", "main.volunteer_settings", "/volunteer/settings"
    )
    _alias_endpoint(app, "achievements", "main.achievements", "/achievements")
    _alias_endpoint(app, "leaderboard", "main.leaderboard", "/leaderboard")
    _alias_endpoint(app, "my_requests", "main.my_requests", "/my-requests")
    _alias_endpoint(app, "feedback", "main.feedback", "/feedback")
    _alias_endpoint(app, "forgot_password", "main.forgot_password", "/forgot-password")
    _alias_endpoint(
        app, "volunteer_register", "main.become_volunteer", "/become_volunteer"
    )
    _alias_endpoint(
        app, "become_volunteer", "main.become_volunteer", "/become_volunteer"
    )
    _alias_endpoint(app, "video_chat", "main.video_chat", "/video-chat")
    _alias_endpoint(app, "volunteer_chat", "main.volunteer_chat", "/volunteer/chat")
    _alias_endpoint(
        app, "volunteer_reports", "main.volunteer_reports", "/volunteer/reports"
    )

    @app.get("/health")
    def health():
        from datetime import UTC, datetime

        payload = {
            "status": "ok",
            "app": "ok",
            "db": "ok",
            "time": datetime.now(UTC).isoformat(),
            "environment": env_name or "unknown",
            "version": (
                os.getenv("APP_VERSION")
                or os.getenv("GIT_SHA")
                or os.getenv("HEROKU_SLUG_COMMIT")
                or ""
            ),
        }
        try:
            from sqlalchemy import text

            db.session.execute(text("SELECT 1"))
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            payload["status"] = "error"
            payload["db"] = "error"
            return jsonify(payload), 503
        return jsonify(payload), 200

    @app.cli.command("notifications.process")
    def notifications_process():
        """Process pending notification jobs."""
        try:
            from backend.helpchain_backend.src.services.notification_jobs import (
                process_pending_notifications,
            )
        except Exception:
            from .services.notification_jobs import process_pending_notifications

        stats = process_pending_notifications(limit=int(os.getenv("NOTIFY_BATCH", "50")))
        app.logger.info(
            "[NOTIFY] processed scanned=%s sent=%s retried=%s failed=%s",
            stats.get("scanned"),
            stats.get("sent"),
            stats.get("retried"),
            stats.get("failed"),
        )

    @app.errorhandler(404)
    def not_found(e):
        # Keep privacy semantics (404) but give volunteers a human fallback page.
        try:
            path = request.path or ""
        except Exception:
            path = ""

        app.logger.warning("404 Not Found: %s", path)
        try:
            from flask import g as _g
            _g.hc_protected_404 = path.startswith("/ops") or path.startswith("/admin")
        except Exception:
            pass

        if path.startswith("/api/"):
            resp = make_response(
                jsonify(
                    {
                        "error": "Not Found",
                        "message": "The requested resource was not found",
                        "status_code": 404,
                    }
                ),
                404,
            )
            if app.config.get("TESTING", False):
                resp.headers["X-Error-Logged"] = "1"
            return resp

        if path.startswith("/volunteer/"):
            resp = make_response(render_template("volunteer_404.html"), 404)
            if app.config.get("TESTING", False):
                resp.headers["X-Error-Logged"] = "1"
            return resp

        # If a global 404 template doesn't exist, fall back to Flask's default.
        try:
            resp = make_response(render_template("404.html"), 404)
            if app.config.get("TESTING", False):
                resp.headers["X-Error-Logged"] = "1"
            return resp
        except Exception:
            resp = make_response(e, 404)
            if app.config.get("TESTING", False):
                resp.headers["X-Error-Logged"] = "1"
            return resp

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
            try:
                from .models import ProAccessRequest as _PAR  # type: ignore
                _pro_access_available = _PAR is not None
            except Exception:
                _pro_access_available = False

            return {
                "VOLUNTEER_DEV_BYPASS_ENABLED": _ca.config.get(
                    "VOLUNTEER_DEV_BYPASS_ENABLED"
                ),
                "VOLUNTEER_DEV_BYPASS_EMAIL": _ca.config.get(
                    "VOLUNTEER_DEV_BYPASS_EMAIL"
                ),
                "HC_PRO_ACCESS_AVAILABLE": _pro_access_available,
            }
        except Exception:
            return {}

    @app.context_processor
    def inject_analytics():
        try:
            from flask import current_app as _ca

            return {
                "PLAUSIBLE_ENABLED": _ca.config.get("PLAUSIBLE_ENABLED", False),
                "PLAUSIBLE_DOMAIN": _ca.config.get("PLAUSIBLE_DOMAIN", ""),
                "PLAUSIBLE_SCRIPT_URL": _ca.config.get("PLAUSIBLE_SCRIPT_URL", ""),
                "PLAUSIBLE_API_HOST": _ca.config.get("PLAUSIBLE_API_HOST", ""),
            }
        except Exception:
            return {
                "PLAUSIBLE_ENABLED": False,
                "PLAUSIBLE_DOMAIN": "",
                "PLAUSIBLE_SCRIPT_URL": "",
                "PLAUSIBLE_API_HOST": "",
            }

    @app.context_processor
    def inject_unread_notification_count():
        """
        Expose volunteer notification counters + preview globally.
        Only computed when a volunteer is logged in.
        """
        try:
            vid = session.get("volunteer_id")
            # keep backward compatibility with existing session flag, but don't require it
            if not vid:
                return {
                    "unread_volunteer_notifs": 0,
                    "VOLUNTEER_UNREAD_NOTIF_COUNT": 0,
                    "volunteer_notif_preview": [],
                }

            try:
                from backend.models import Notification
            except ModuleNotFoundError:
                from models import Notification

            cnt = Notification.query.filter_by(volunteer_id=vid, is_read=False).count()
            preview_rows = (
                Notification.query.filter_by(volunteer_id=vid)
                .order_by(Notification.created_at.desc())
                .limit(10)
                .all()
            )
            preview = [
                {
                    "id": n.id,
                    "title": (n.title or "").strip(),
                    "body": (n.body or "").strip(),
                    "request_id": getattr(n, "request_id", None),
                    "is_unread": not bool(getattr(n, "is_read", False)),
                }
                for n in preview_rows
            ]
            return {
                "unread_volunteer_notifs": cnt,
                "VOLUNTEER_UNREAD_NOTIF_COUNT": cnt,  # legacy template var
                "volunteer_notif_preview": preview,
            }
        except Exception:
            return {
                "unread_volunteer_notifs": 0,
                "VOLUNTEER_UNREAD_NOTIF_COUNT": 0,
                "volunteer_notif_preview": [],
            }

    return app


def _log_l10n_missing_once(
    *,
    locale: str,
    key: str,
    domain: str | None = None,
    fallback: str | None = None,
) -> None:
    cache_key = f"{(locale or '').lower()}:{(key or '').strip()}"
    if not cache_key or cache_key.endswith(":"):
        return
    with _L10N_MISSING_LOCK:
        if cache_key in _L10N_MISSING_SEEN:
            return
        if len(_L10N_MISSING_SEEN) > 10000:
            _L10N_MISSING_SEEN.clear()
        _L10N_MISSING_SEEN.add(cache_key)
    try:
        from flask import current_app

        current_app.logger.warning(
            "[L10N_MISSING] locale=%s key=%s domain=%s fallback=%s",
            locale,
            key,
            (domain or "-"),
            (fallback or ""),
        )
    except Exception:
        return


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
