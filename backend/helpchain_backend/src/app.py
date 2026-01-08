from __future__ import annotations

import os
from dotenv import load_dotenv

from flask import Flask, redirect, request, session, url_for
from flask_babel import get_locale, refresh
from flask_login import LoginManager
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_wtf.csrf import CSRFProtect

from jinja2 import ChoiceLoader, FileSystemLoader

from .config import Config
from .controllers.helpchain_controller import HelpChainController
from .extensions import babel, db, mail, migrate, csrf


login_manager = LoginManager()
socketio = SocketIO(async_mode="threading")


@login_manager.user_loader
def load_user(user_id: str):
    # Import inside to avoid circular imports at module load
    from .models import User
    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return None


def create_app(config_object=None) -> Flask:
    # --- Resolve project base + load .env early ---
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    load_dotenv(dotenv_path=os.path.join(base, ".env"))

    static_dir = os.path.join(base, "backend", "static")
    templates_root = os.path.join(base, "backend", "templates")
    templates_backend = os.path.join(base, "backend", "templates")

    app = Flask(__name__, static_folder=static_dir, template_folder=templates_root, instance_relative_config=True)
    app.config.from_object(config_object or Config)

    # --- CSRFProtect (единствена инициализация!) ---
    csrf = CSRFProtect()
    csrf.init_app(app)

    # --- Templates: /templates + /backend/templates ---
    app.jinja_loader = ChoiceLoader(
        [
            FileSystemLoader(templates_root),
            FileSystemLoader(templates_backend),
        ]
    )

    # --- Jinja helpers ---
    def url_lang(endpoint: str, **values):
        # Placeholder for future i18n URLs; currently plain url_for
        return url_for(endpoint, **values)

    def safe_url_for(endpoint: str, **values):
        try:
            return url_for(endpoint, **values)
        except Exception:
            return "#"

    app.jinja_env.globals["url_lang"] = url_lang
    app.jinja_env.globals["safe_url_for"] = safe_url_for

    # --- Inject COPY into templates ---
    try:
        from .copy import COPY  # must be backend/helpchain_backend/src/copy.py
    except Exception:
        COPY = {}
    app.jinja_env.globals["COPY"] = COPY

    # --- get_locale safe for templates ---
    def _safe_get_locale():
        try:
            return str(get_locale())
        except Exception:
            return "bg"

    app.jinja_env.globals["get_locale"] = _safe_get_locale
    app.jinja_env.globals["str"] = str
    app.jinja_env.globals["getattr"] = getattr

    # --- Defaults / upload folder ---
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    app.config.setdefault("UPLOAD_FOLDER", os.path.join(static_dir, "uploads"))
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # IMPORTANT:
    # If SQLALCHEMY_DATABASE_URI is not set, Flask-SQLAlchemy will default to instance/app.db.
    # That's OK and consistent.

    # --- Init extensions (ONLY here) ---
    db.init_app(app)
    babel.init_app(app)
    mail.init_app(app)
    # csrf.init_app(app)  # Премахни тази, ако вече я има!
    try:
        migrate.init_app(app, db)
    except Exception:
        pass

    # --- Login manager ---
    login_manager.init_app(app)
    login_manager.login_view = "login"

    # --- SocketIO ---
    socketio.init_app(app, cors_allowed_origins="*")

    # Controller (after app exists) - keep if you rely on it
    _controller = HelpChainController()

    # --- Blueprints (single source of truth for routes) ---
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

    # --- Minimal route kept: language toggle (harmless) ---
    @app.route("/set_language/<language>", methods=["POST"])
    def set_language(language):
        if language in ["bg", "en"]:
            session["language"] = language
            refresh()
        return redirect(request.referrer or "/")

    # --- Service worker (avoid wrong mimetype) ---
    @app.route("/sw.js")
    def service_worker():
        from flask import send_from_directory
        return send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")

    # ---- SocketIO events ----
    @socketio.on("join")
    def on_join(data):
        room = data["room"]
        join_room(room)
        emit("status", {"msg": f'{data.get("username","user")} се присъедини към {room}'}, room=room)

    @socketio.on("leave")
    def on_leave(data):
        room = data["room"]
        leave_room(room)
        emit("status", {"msg": f'{data.get("username","user")} напусна {room}'}, room=room)

    @socketio.on("typing")
    def handle_typing(data):
        room = data["room"]
        username = data.get("username", "user")
        emit("typing", {"username": username, "is_typing": data.get("is_typing", False)}, room=room, skip_sid=True)

    # --- DB create_all (dev-friendly) ---
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            app.logger.warning("db.create_all failed: %s", e)

    return app


if __name__ == "__main__":
    app = create_app(Config)
    socketio.run(app, debug=True)

import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")

TEMPLATES_DIR = os.path.join(BACKEND_DIR, "templates")
STATIC_DIR = os.path.join(BACKEND_DIR, "static")

app = Flask(
    __name__,
    template_folder=TEMPLATES_DIR,
    static_folder=STATIC_DIR,
    static_url_path="/static",
)


