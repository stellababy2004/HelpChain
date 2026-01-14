from __future__ import annotations

import os
from dotenv import load_dotenv
from backend.extensions import db, migrate

from flask import Flask, redirect, request, session, url_for
from flask_babel import get_locale, refresh
from flask_login import LoginManager
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_wtf.csrf import CSRFProtect, generate_csrf

from jinja2 import ChoiceLoader, FileSystemLoader

from .config import Config
from .controllers.helpchain_controller import HelpChainController

from backend.models import AdminUser  # was: from backend.models_with_analytics import AdminUser


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


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv()  # load .env at startup


def create_app(config_object=None) -> Flask:
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "templates"),
        static_folder=os.path.join(BASE_DIR, "static"),
    )
    app = Flask(__name__, instance_relative_config=True)
    app.config.setdefault("PROPAGATE_EXCEPTIONS", True)

    # Config from caller, then env, then sane defaults
    if isinstance(config_object, dict):
        app.config.update(config_object)
    app.config["PROPAGATE_EXCEPTIONS"] = True
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me-please")
    app.secret_key = app.config.get("SECRET_KEY")
    app.config.setdefault(
        "SQLALCHEMY_DATABASE_URI",
        os.getenv("SQLALCHEMY_DATABASE_URI", "sqlite:///helpchain.db"),
    )
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)

    # SECRET_KEY: env/.env > config > DEV fallback
    if not app.config.get("SECRET_KEY"):
        secret = os.environ.get("SECRET_KEY")
        if not secret:
            try:
                from dotenv import load_dotenv
                load_dotenv()
                secret = os.environ.get("SECRET_KEY")
            except Exception:
                secret = None
        if not secret:
            secret = "dev-only-change-me-please"
            app.logger.warning("SECRET_KEY missing. Using DEV fallback. Set SECRET_KEY via env/instance config.")
        app.config["SECRET_KEY"] = secret

    # DB + Migrate
    db.init_app(app)
    migrate.init_app(app, db)

    # Ensure models are imported so Alembic sees them
    with app.app_context():
        import backend.models  # noqa
        import backend.models_with_analytics  # noqa

    # --- CSRFProtect (единствена инициализация!) ---
    csrf = CSRFProtect()
    csrf.init_app(app)
    # Make {{ csrf_token() }} available in Jinja
    app.jinja_env.globals["csrf_token"] = generate_csrf

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

    # --- Init extensions (ONLY here; after config overrides) ---
    db.init_app(app)
    babel.init_app(app)
    mail.init_app(app)
    # csrf.init_app(app)  # Премахни тази, ако вече я има!
    try:
        migrate.init_app(app, db)
    except Exception:
        pass

    # --- Login manager ---
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "admin.admin_login"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return AdminUser.query.get(int(user_id))
        except Exception:
            return None

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

    app.config["PROPAGATE_EXCEPTIONS"] = True
    return app


if __name__ == "__main__":
    app = create_app(Config)
    socketio.run(app, debug=True)

import os
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import generate_csrf
from backend.extensions import db, migrate
from backend.models import AdminUser  # единственият източник


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv()  # load .env at startup


def create_app(config_object=None):
    # Use project-level templates/static (root /templates, /static)
    root_templates = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "..", "templates"))
    root_static = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "..", "static"))

    app = Flask(__name__, instance_relative_config=True, template_folder=root_templates, static_folder=root_static)

    # Config from caller, then env, then sane defaults
    if isinstance(config_object, dict):
        app.config.update(config_object)
    # load defaults from Config class
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

    # SECRET_KEY: env/.env > config > DEV fallback
    if not app.config.get("SECRET_KEY"):
        secret = os.environ.get("SECRET_KEY")
        if not secret:
            try:
                from dotenv import load_dotenv
                load_dotenv()
                secret = os.environ.get("SECRET_KEY")
            except Exception:
                secret = None
        if not secret:
            secret = "dev-only-change-me-please"
            app.logger.warning("SECRET_KEY missing. Using DEV fallback. Set SECRET_KEY via env/instance config.")
        app.config["SECRET_KEY"] = secret

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

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "admin.admin_login"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return AdminUser.query.get(int(user_id))
        except Exception:
            return None

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

    return app


