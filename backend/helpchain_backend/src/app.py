import os
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import TooManyRequests
from __future__ import annotations
import datetime
import os
import sqlite3
import uuid
import secrets
from flask import Flask, Response, flash, jsonify, redirect, render_template, request, session, url_for
from .copy import get_copy
from backend.helpchain_backend.src.category_data import CATEGORIES, COMMON
from flask_socketio import SocketIO, emit, join_room, leave_room

def generate_honeypot_name():
    return "hp_" + secrets.token_hex(8)

def validate_request_form(data, valid_categories):
    """Validate universal request form. Returns (is_valid, error_message)."""
    # Only one error at a time (UX > perfection)
    contact = data.get("contact", "").strip()
    need = data.get("description", "").strip()
    category = data.get("category", "").strip()
    import re
    contact_regex = r"^[A-Za-zА-Яа-я0-9\s\-+.@()]{6,50}$"
    if not need:
        return False, "Моля, опишете накратко каква помощ Ви е нужна."
    if len(need) < 15:
        return False, "Моля, опишете нуждата си с поне няколко изречения."
    if not contact or not re.match(contact_regex, contact):
        return False, "Контактът изглежда невалиден. Моля, въведете телефон или имейл."
    if category not in valid_categories:
        return False, "Невалидна категория. Моля, презаредете страницата."
    return True, None

@app.context_processor
def inject_copy():
    # Най-прост вариант: ?lang=fr или ?lang=bg
    lang = request.args.get("lang")
    return {"COPY": get_copy(lang)}

# Jinja helper for lang-persistent URLs

# Language helpers
def current_lang(default="bg") -> str:
    return (request.args.get("lang") or request.form.get("lang") or default).lower()

@app.context_processor
def inject_lang_helpers():
    def url_lang(endpoint, **values):
        lang = values.pop("lang", None) or current_lang()
        values.setdefault("lang", lang)
        return url_for(endpoint, **values)
    return {"url_lang": url_lang}
# ...existing code...
import uuid
from flask import Flask, Response, flash, jsonify, redirect, render_template, request, session, url_for
# ... всички останали импорти ...
from dotenv import load_dotenv
from flask_babel import get_locale, refresh
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_mail import Message
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename
from backend.models import AdminUser, Request, RequestLog
from .config import Config
from .controllers.helpchain_controller import HelpChainController
from .extensions import babel, db, mail, migrate
from backend.helpchain_backend.src.routes.api import api_bp
from backend.helpchain_backend.src.routes.analytics import analytics_bp

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
print(f"MAILTRAP_USERNAME from env: {os.environ.get('MAILTRAP_USERNAME')}")
print(f"MAILTRAP_PASSWORD from env: {os.environ.get('MAILTRAP_PASSWORD')}")

controller = HelpChainController()

login_manager = LoginManager()
socketio = SocketIO(async_mode="threading")

@login_manager.user_loader
def load_user(user_id):
    from .models import User
    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return None

def create_app(config_object=None):
    # Flask app must be created before registering routes
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../static"))
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

    # 1) Trust proxy headers for real client IP
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # 2) Limiter storage (Redis preferred, fallback to memory)
    storage_uri = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        storage_uri=storage_uri,
        strategy="fixed-window",
        default_limits=[],
    )
    app.extensions["limiter"] = limiter

    # 3) Emergency email cooldown (MVP, in-memory)
    import time
    def can_send_emergency_email(app):
        now = time.time()
        last = app.config.get("EMERGENCY_EMAIL_LAST_SENT_AT", 0)
        cooldown = int(app.config.get("EMERGENCY_EMAIL_COOLDOWN_SECONDS", 300))
        if now - last < cooldown:
            return False
        app.config["EMERGENCY_EMAIL_LAST_SENT_AT"] = now
        return True
    app.can_send_emergency_email = lambda: can_send_emergency_email(app)
    # 4) 429 error handler with COPY
    @app.errorhandler(TooManyRequests)
    def ratelimit_handler(e):
        return render_template("errors/429.html"), 429

    # Debug route: показва абсолютния път до static директорията и файловете вътре
    @app.route("/_static_debug")
    def _static_debug():
        import os
        static_path = app.static_folder
        cwd = os.getcwd()
        try:
            files = os.listdir(static_path)
        except Exception as e:
            files = [f"Error: {e}"]
        return f"<h2>STATIC FOLDER:</h2><pre>{static_path}</pre><h3>Current Working Directory:</h3><pre>{cwd}</pre><h3>Files:</h3><pre>{files}</pre>", 200, {"Content-Type": "text/html; charset=utf-8"}
    login_manager.init_app(app)

    # Основни навигационни route-ове след създаване на app


    @app.route("/volunteer_register", methods=["GET", "POST"], endpoint="volunteer_register")
    def volunteer_register():
        return "<h2>Форма за регистрация на доброволец (очаквайте скоро)</h2>", 200

    # Safe url_for за шаблони, които го изискват
    def safe_url_for(endpoint, **values):
        try:
            return url_for(endpoint, **values)
        except Exception:
            return "#"
    app.jinja_env.globals["safe_url_for"] = safe_url_for
    app.config.from_object(config_object or Config)
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault(
        "SQLALCHEMY_DATABASE_URI",
        os.environ.get("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:"),
    )
    # ...existing code...
    from .copy import get_copy

    @app.context_processor
    def inject_copy():
        # Ако имаш set_language, можеш да подадеш текущия lang
        return {"COPY": get_copy()}


    # Debug: Изведи всички route-ове при стартиране
    def print_all_routes(app):
        print("\n[DEBUG] Registered routes:")
        for rule in app.url_map.iter_rules():
            print(f"  {rule} -> endpoint: {rule.endpoint}, methods: {','.join(rule.methods)}")
        print("[DEBUG] --- End routes ---\n")

    # Safe url_for за шаблони, които го изискват
    def safe_url_for(endpoint, **values):
        try:
            return url_for(endpoint, **values)
        except Exception:
            return "#"
    app.jinja_env.globals["safe_url_for"] = safe_url_for
    app.config.from_object(config_object or Config)
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault(
        "SQLALCHEMY_DATABASE_URI",
        os.environ.get("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:"),
    )

    # --- Премахнати app-level /request и /request/food route-ове (остават само в blueprint) ---

    # --- ВСИЧКИ ОСТАНАЛИ ROUTE-ОВЕ СЛЕД ТОВА ---

    @app.before_request
    def _preview_short_circuit_early():
        try:
            p = request.path or ""
            if p in ("/health", "/api/_health"):
                return Response("ok", mimetype="text/plain")
            if p == "/api/analytics":
                return jsonify(status="ok", source="stub", message="analytics service reachable")
            if p == "/admin/login" and request.method == "GET":
                try:
                    from flask_wtf.csrf import generate_csrf  # type: ignore
                    token = generate_csrf()
                except Exception:
                    try:
                        import secrets
                        if "csrf_token" not in session:
                            session["csrf_token"] = secrets.token_urlsafe(32)
                        token = session.get("csrf_token", "")
                    except Exception:
                        token = ""
                return Response(
                    (
                        f"<html><head><title>Admin Login</title><!-- csrf-v2-marker --><meta name=\"csrf-token\" content=\"{token}\" /></head>"
                        "<body>"
                        "<h1>Admin Login</h1>"
                        f"<form method=\"post\">\n<input type=\"hidden\" name=\"csrf_token\" value=\"{token}\" />"
                        "<label>Username or Email: <input name=\"username\" /></label><br/>"
                        "<label>Password: <input name=\"password\" type=\"password\" /></label><br/>"
                        "<label>2FA Token (optional): <input name=\"token\" /></label><br/>"
                        "<button type=\"submit\">Login</button>"
                        "</form>"
                        "</body></html>"
                    ),
                    mimetype="text/html",
                )
        except Exception:

                # --- Създай Flask app ПЪРВО ---
                app = Flask(__name__, template_folder=template_dir, static_folder="static")


    def _safe_get_locale():
        try:
            return str(get_locale())
        except Exception:
            return "bg"
    app.jinja_env.globals["get_locale"] = _safe_get_locale
    app.jinja_env.globals["str"] = str
    app.jinja_env.globals["getattr"] = getattr

    @app.context_processor
    def _inject_csrf_token():
        def csrf_token():
            try:
                from flask_wtf.csrf import generate_csrf  # type: ignore
                return generate_csrf()
            except Exception:
                try:
                    import secrets
                    if "csrf_token" not in session:
                        session["csrf_token"] = secrets.token_urlsafe(32)
                    return session.get("csrf_token", "")
                except Exception:
                    return ""
        return {"csrf_token": csrf_token}

    # Регистрирай blueprint-ите с url_prefix

    app.register_blueprint(api_bp, url_prefix="/api")
    # analytics_bp вече се регистрира по-горе, не го регистрирай втори път

    from .routes.main import main_bp
    #
    app.register_blueprint(main_bp)
    #

    try:
        from .routes.admin import admin_bp
        app.register_blueprint(admin_bp, url_prefix="/admin")
    except Exception as e:
        app.logger.info("admin blueprint not loaded: %s", e)

    try:
        from .routes.analytics import analytics_bp
        app.register_blueprint(analytics_bp)
    except Exception as e:
        app.logger.info("analytics blueprint not loaded: %s", e)



    @app.route("/")
    def index():
        return render_template("index.html")

    # Catch-all за всички други пътища (освен API и статични)
    # Catch-all route временно премахнат за диагностика на routing проблеми

    @app.route("/static/previews/new-page.html")
    def legacy_preview_redirect():
        from flask import redirect
        return redirect(url_lang("index"), code=301)

    # ...set_language премахнат, остава само във blueprint-а (main_bp)...

    @app.route("/submit_request", methods=["GET", "POST"])
    def set_language(language):
        if language in ["bg", "en", "fr"]:
            session["language"] = language
            refresh()
        return redirect(request.referrer or "/")
    # ...legacy /submit_request, /category/food, /request routes премахнати. Оставен само blueprint-ът.
    def admin_analytics():
        return (
            "<html><body><h1>Admin Analytics</h1><div id='admin-analytics'>OK</div></body></html>",
            200,
            {"Content-Type": "text/html; charset=utf-8"},
        )

    # ---- SAFETY GUARANTEE: never return None ----
    import logging
    logger = logging.getLogger("helpchain.app")
    logger.debug("CREATE_APP returning app: %s", type(app))
    return app

