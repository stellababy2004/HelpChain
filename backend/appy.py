# ruff: noqa: I001  # Complex import order with optional modules
import csv
import gzip
import importlib
import json
import logging
import os
import secrets
import sys
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse
from datetime import UTC, datetime
from math import atan2, cos, radians, sin, sqrt
from io import BytesIO, StringIO
from types import SimpleNamespace
from unittest.mock import Mock

# Ensure backend modules are importable regardless of working directory
BACKEND_DIR = os.path.dirname(__file__)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Import Celery for background tasks
from celery import Celery
from flask import (
    Blueprint,
    Flask,
    Response,
    current_app,
    has_app_context,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from flask_babel import Babel, refresh
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_migrate import Migrate
from flask_socketio import join_room, leave_room
from flask_talisman import Talisman

try:
    from flask_sqlalchemy.session import SignallingSession
except ImportError:  # Flask-SQLAlchemy>=3 renamed SignallingSession to Session
    from flask_sqlalchemy.session import Session as SignallingSession
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import joinedload, sessionmaker
from werkzeug.exceptions import BadRequest
from werkzeug.utils import secure_filename

# First-party imports
try:
    from analytics_service import get_db
except ImportError:  # pragma: no cover - deployment fallback
    from backend.analytics_service import get_db  # type: ignore[import-not-found]
from extensions import babel, cache, db, mail as mail_ext
from models import (
    AdminUser,
    ChatMessage,
    ChatParticipant,
    ChatRoom,
    HelpRequest,
    Notification,
    Role,
    RoleEnum,
    RolePermission,
    User,
    UserRole,
    Volunteer,
)
from models_with_analytics import Task, TaskAssignment, TaskPerformance
from permissions import initialize_default_roles_and_permissions, require_admin_login
from routes.notifications import (
    notification_bp,
    notification_settings as notification_settings_view,
    subscribe_push as subscribe_push_view,
    test_email as test_email_view,
    test_sms as test_sms_view,
    unsubscribe_push as unsubscribe_push_view,
    vapid_public_key as vapid_public_key_view,
)

SUPPORTED_DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d")


def _parse_date_param(raw_value, *, end_of_day=False):
    """Parse user supplied date strings into naive UTC datetimes."""
    if not raw_value:
        return None

    value = str(raw_value).strip()
    if not value:
        return None

    parsed = None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        for fmt in SUPPORTED_DATE_FORMATS:
            try:
                parsed = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue

    if parsed is None:
        return None

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)

    if end_of_day and parsed.hour == 0 and parsed.minute == 0 and parsed.second == 0:
        parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)

    return parsed


def _format_datetime_for_response(value):
    if not value:
        return {"iso": None, "display": None}

    return {
        "iso": value.isoformat(),
        "display": value.strftime("%Y-%m-%d %H:%M"),
    }


# API alias blueprint to expose notification endpoints under /api/notification
notification_api_alias_bp = Blueprint("notification_api_alias", __name__)


@notification_api_alias_bp.route("/settings", methods=["GET", "POST"])
def notification_api_settings():
    return notification_settings_view()


@notification_api_alias_bp.route("/subscribe", methods=["POST"])
def notification_api_subscribe():
    return subscribe_push_view()


@notification_api_alias_bp.route("/unsubscribe", methods=["POST"])
def notification_api_unsubscribe():
    return unsubscribe_push_view()


@notification_api_alias_bp.route("/vapid-public-key", methods=["GET"])
def notification_api_vapid_key():
    return vapid_public_key_view()


@notification_api_alias_bp.route("/test-email", methods=["POST"])
def notification_api_test_email():
    return test_email_view()


@notification_api_alias_bp.route("/test-sms", methods=["POST"])
def notification_api_test_sms():
    return test_sms_view()


# Optional imports - handle gracefully if not available
try:
    from flask_compress import Compress

    FLASK_COMPRESS_AVAILABLE = True
except ImportError:
    FLASK_COMPRESS_AVAILABLE = False
    Compress = None

# Ensure the module is addressable both as 'appy' and 'backend.appy' for tests.
sys.modules.setdefault("backend.appy", sys.modules[__name__])

try:
    from ai_service import ai_service
except ImportError:  # pragma: no cover - optional dependency
    ai_service = None

# Import admin_roles blueprint with fallback
try:
    from admin_roles import admin_roles_bp
except ImportError:
    # Fallback for production environments
    import admin_roles

    admin_roles_bp = admin_roles.admin_roles_bp

# Зареди environment variables от .env файла (от корена на проекта)
# load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# Sentry for error monitoring

# Настройка на logging преди всичко друго
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("helpchain.log", encoding="utf-8"),
    ],
)


# Enhanced logging configuration
def setup_logging():
    """Setup comprehensive logging configuration"""
    # Clear existing handlers to avoid duplicates
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Set root logger level
    root_logger.setLevel(logging.INFO)

    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    )
    simple_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # Console handler for development
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)

    # File handler for all logs
    file_handler = logging.FileHandler("helpchain.log", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)

    # Error file handler for errors only
    error_handler = logging.FileHandler("helpchain_errors.log", encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_handler)

    # Security logger for sensitive operations
    security_logger = logging.getLogger("security")
    security_logger.setLevel(logging.INFO)
    security_handler = logging.FileHandler("helpchain_security.log", encoding="utf-8")
    security_handler.setFormatter(detailed_formatter)
    security_logger.addHandler(security_handler)
    security_logger.propagate = False  # Don't propagate to root logger

    # API logger for API operations
    api_logger = logging.getLogger("api")
    api_logger.setLevel(logging.INFO)
    api_handler = logging.FileHandler("helpchain_api.log", encoding="utf-8")
    api_handler.setFormatter(detailed_formatter)
    api_logger.addHandler(api_handler)
    api_logger.propagate = False

    return root_logger


def _mask_secret_in_uri(uri: str | None) -> str:
    """Mask password portion of a database URI before logging."""
    if not uri:
        return ""

    try:
        scheme, rest = uri.split("://", 1)
    except ValueError:
        return "<hidden>"

    if "@" not in rest:
        return f"{scheme}://<hidden>"

    userinfo, host = rest.rsplit("@", 1)
    if ":" not in userinfo:
        return f"{scheme}://{userinfo}@{host}"

    username, _, password = userinfo.partition(":")
    masked_userinfo = username if not password else f"{username}:***"
    return f"{scheme}://{masked_userinfo}@{host}"


# Setup enhanced logging
logger = setup_logging()


def initialize_default_admin():
    """
    Initialize default admin user if it doesn't exist
    """
    try:
        logger.info("Checking for existing admin user...")
        db = get_db()
        # Check if admin user exists
        admin_user = db.session.query(AdminUser).filter_by(username="admin").first()
        if admin_user:
            logger.info("Admin user already exists")
            return admin_user

        logger.info("Creating default admin user...")
        # Create admin user
        admin_user = AdminUser(
            username="admin",
            email="admin@helpchain.live",
        )
        admin_user.set_password(os.getenv("ADMIN_USER_PASSWORD", "Admin123"))
        db.session.add(admin_user)
        db.session.flush()  # Get admin_user ID
        logger.info(f"AdminUser created with ID: {admin_user.id}")

        # Also create a User record for permissions system with superadmin role
        logger.info("Creating User record with superadmin role...")
        user = User(
            username="admin",
            email="admin@helpchain.live",
            password_hash=admin_user.password_hash,  # Use same password hash
            role=RoleEnum.superadmin,  # Use the enum directly
            is_active=True,
        )
        logger.info(f"User object created: username={user.username}, role={user.role}")
        db.session.add(user)
        logger.info("User added to session")
        db.session.commit()
        logger.info("Default admin user created successfully")
        return admin_user

    except Exception as e:
        logger.error(f"Error creating default admin user: {e}", exc_info=app.debug)
        db.session.rollback()
        return None


# Add helpchain_backend/src directory to Python path
HELPCHAIN_BACKEND_DIR = os.path.join(BACKEND_DIR, "helpchain-backend")
if HELPCHAIN_BACKEND_DIR not in sys.path:
    sys.path.insert(0, HELPCHAIN_BACKEND_DIR)

SRC_DIR = os.path.join(HELPCHAIN_BACKEND_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

logger.debug(f"Python path: {sys.path[:3]}...")  # Debug print
logger.debug(f"Current directory: {os.getcwd()}")

logger.info("Starting HelpChain application...")
logger.info(f"Python version: {sys.version}")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"Python path: {sys.path[:3]}...")

logger.info("Starting appy.py...")

#         def enable_2fa(self):
#             self.two_factor_enabled = True

#         def disable_2fa(self):
#             self.two_factor_enabled = False
#             self.totp_secret = None

#     mock_admin = MockAdminUser()
#     AdminUser = MockAdminUser  # Replace with mock

HAS_2FA = False
mock_admin = None

# Email 2FA settings
EMAIL_2FA_ENABLED = False  # Enable email-based 2FA for admin login
EMAIL_2FA_RECIPIENT = "contact@helpchain.live"  # Email to send 2FA codes to


# Optional bypass for volunteer OTP in development/testing
DISABLE_VOLUNTEER_OTP = os.getenv("DISABLE_VOLUNTEER_OTP", "false").lower() == "true"
VOLUNTEER_OTP_BYPASS_EMAILS = {
    email.strip().lower()
    for email in os.getenv(
        "VOLUNTEER_OTP_BYPASS",
        "ivan@example.com",
    ).split(",")
    if email.strip()
}


def generate_email_2fa_code():
    """Generate a 6-digit 2FA code"""
    return str(secrets.randbelow(900000) + 100000)


def send_email_2fa_code(code, ip_address, user_agent):
    """Send 2FA code via email"""
    try:
        logger.info(f"Attempting to send 2FA code to {EMAIL_2FA_RECIPIENT}")

        # Use Celery task for reliable email delivery with retry
        from tasks import send_email_task

        body = f"""Здравейте,

Получен е опит за вход в администраторския панел на HelpChain.

Код за верификация: {code}

Детайли за достъпа:
- IP адрес: {ip_address}
- Браузър: {user_agent}
- Време: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Ако това не сте вие, моля игнорирайте това съобщение.

С уважение,
HelpChain системата
"""

        if celery and is_realtime_feature_enabled("background"):
            send_email_task.delay(
                recipient=EMAIL_2FA_RECIPIENT,
                subject="HelpChain - Код за верификация на администратор",
                template=None,  # Direct body content
                context={"body": body},
            )
        else:
            send_email_task(
                recipient=EMAIL_2FA_RECIPIENT,
                subject="HelpChain - Код за верификация на администратор",
                template=None,
                context={"body": body},
            )

        logger.info(f"Email 2FA code queued for delivery to {EMAIL_2FA_RECIPIENT}")
        return True

    except Exception as e:
        logger.error(f"Failed to queue email 2FA code: {e}", exc_info=app.debug)
        # Fallback: save to file
        try:
            logger.warning("Attempting fallback: saving email to file")
            with open("sent_emails.txt", "a", encoding="utf-8") as f:
                email_content = (
                    f"Subject: HelpChain - Код за верификация на администратор\n"
                    f"To: {EMAIL_2FA_RECIPIENT}\n"
                    f"From: {app.config['MAIL_DEFAULT_SENDER']}\n\n"
                    "Здравейте,\n\n"
                    "Получен е опит за вход в администраторския панел на HelpChain.\n\n"
                    f"Код за верификация: {code}\n\n"
                    "Детайли за достъпа:\n"
                    f"- IP адрес: {ip_address}\n"
                    f"- Браузър: {user_agent}\n"
                    f"- Време: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    "Ако това не сте вие, моля игнорирайте това съобщение.\n\n"
                    "С уважение,\n"
                    "HelpChain системата\n\n"
                    f"{'=' * 50}\n"
                )
                f.write(email_content)
            logger.info("Email 2FA code saved to file as fallback")
            return True
        except Exception as file_e:
            logger.error(
                f"Failed to save email 2FA code to file: {file_e}", exc_info=app.debug
            )
            return False


# Създай папката instance ако не съществува
os.makedirs(os.path.join(os.path.dirname(__file__), "instance"), exist_ok=True)

# Задаваме явни папки за шаблони и статични файлове (адаптирай пътищата ако е нужно)
_templates = os.path.join(os.path.dirname(__file__), "templates")
_static = os.path.join(os.path.dirname(__file__), "static")

# from flask_session import Session

# Import shared Flask app and mail instances
# Initialize Flask-SocketIO for real-time features
# from app_init import app, mail
# Instead of importing, create the app directly here
from flask import Flask
from flask_mail import Mail, Message

# Create Flask app with async support
app = Flask(__name__, static_folder="static", template_folder="templates")

# Default configuration for admin real-time feature toggles
REALTIME_SETTINGS_DEFAULTS = {
    "websocket": True,
    "notifications": False,
    "charts": False,
    "background": False,
}

REALTIME_SETTINGS_FILE = os.path.join(app.instance_path, "realtime_settings.json")


def load_realtime_settings():
    """Load persisted real-time feature settings or return defaults."""
    try:
        with open(REALTIME_SETTINGS_FILE, encoding="utf-8") as settings_file:
            persisted = json.load(settings_file)
    except FileNotFoundError:
        return REALTIME_SETTINGS_DEFAULTS.copy()
    except json.JSONDecodeError as error:
        app.logger.warning(
            "Realtime settings file corrupted (%s). Using defaults.", error
        )
        return REALTIME_SETTINGS_DEFAULTS.copy()

    merged = REALTIME_SETTINGS_DEFAULTS.copy()
    merged.update(
        {
            key: bool(persisted.get(key, default))
            for key, default in REALTIME_SETTINGS_DEFAULTS.items()
        }
    )
    return merged


def save_realtime_settings(settings):
    """Persist real-time feature settings to disk."""
    os.makedirs(app.instance_path, exist_ok=True)
    with open(REALTIME_SETTINGS_FILE, "w", encoding="utf-8") as settings_file:
        json.dump(settings, settings_file, ensure_ascii=False, indent=2)


def is_realtime_feature_enabled(feature_name: str) -> bool:
    """Return current enabled state for a given real-time feature toggle."""
    settings = load_realtime_settings()
    default_value = REALTIME_SETTINGS_DEFAULTS.get(feature_name, False)
    return bool(settings.get(feature_name, default_value))


# Provide safe mail defaults for development and tests
app.config.setdefault("MAIL_SERVER", "localhost")
app.config.setdefault("MAIL_PORT", 1025)
app.config.setdefault("MAIL_USE_TLS", False)
app.config.setdefault("MAIL_USE_SSL", False)
app.config.setdefault("MAIL_USERNAME", None)
app.config.setdefault("MAIL_PASSWORD", None)
app.config.setdefault("MAIL_DEFAULT_SENDER", "noreply@helpchain.test")
app.config.setdefault("MAIL_SUPPRESS_SEND", False)

# Initialize Flask-Mail
mail = Mail(app)


def _utcnow() -> datetime:
    """Return naive UTC timestamp without relying on deprecated datetime.utcnow."""
    return datetime.now(UTC).replace(tzinfo=None)


def _ensure_db_engine_registration():
    """Ensure SQLAlchemy has a registered engine for the active Flask app."""
    if not has_app_context():
        return

    app_obj = current_app._get_current_object()
    engines = getattr(db, "_app_engines", None)

    if engines is None:
        return

    app_engines = engines.get(app_obj)
    if app_engines is None:
        app_engines = {}
    else:
        for existing_engine in list(app_engines.values()):
            try:
                existing_engine.dispose()
            except Exception as dispose_error:  # pragma: no cover - defensive
                app.logger.debug(
                    "Failed disposing old SQLAlchemy engine: %s", dispose_error
                )
        app_engines.clear()

    database_uri = app_obj.config.get("SQLALCHEMY_DATABASE_URI")
    if not database_uri:
        return

    engine_options = db._engine_options.copy()
    engine_options.update(app_obj.config.get("SQLALCHEMY_ENGINE_OPTIONS", {}))
    engine_options.setdefault("echo", app_obj.config.get("SQLALCHEMY_ECHO", False))
    engine_options.setdefault("echo_pool", app_obj.config.get("SQLALCHEMY_ECHO", False))
    engine_options["url"] = database_uri

    # These helpers ensure SQLite file paths and other driver-specific defaults are applied.
    db._make_metadata(None)
    db._apply_driver_defaults(engine_options, app_obj)

    app_engines[None] = db._make_engine(None, engine_options, app_obj)
    engines[app_obj] = app_engines
    app.logger.debug(
        "Registered SQLAlchemy engine for app %s (engines=%s)",
        id(app_obj),
        [id(k) for k in engines.keys()],
    )


_original_get_bind = SignallingSession.get_bind


def _get_bind_with_registration(self, mapper=None, clause=None, **kwargs):
    app.logger.debug(
        "Attempting SQLAlchemy bind for app %s", id(current_app._get_current_object())
    )
    try:
        return _original_get_bind(self, mapper, clause, **kwargs)
    except RuntimeError as exc:
        if "not registered" in str(exc).lower():
            _ensure_db_engine_registration()
            app_obj = current_app._get_current_object()
            app_engines = getattr(db, "_app_engines", {}).get(app_obj, {})

            try:
                return _original_get_bind(self, mapper, clause, **kwargs)
            except RuntimeError:
                fallback_engine = app_engines.get(None)
                if fallback_engine is not None:
                    return fallback_engine
                raise
        raise


SignallingSession.get_bind = _get_bind_with_registration


def send_email_now(*, subject, recipients, body, sender=None, html=None, template=None):
    """Send email synchronously via Flask-Mail. Raises on failure."""
    if not recipients:
        raise ValueError("Recipients list cannot be empty")

    message = Message(
        subject=subject,
        recipients=recipients,
        sender=sender or app.config.get("MAIL_DEFAULT_SENDER"),
    )

    if html:
        message.html = html
    else:
        message.body = body

    if app.config.get("TESTING"):
        outbox = app.extensions.setdefault("test_email_outbox", [])
        outbox.append(
            {
                "subject": message.subject,
                "recipients": list(message.recipients),
                "sender": message.sender,
                "body": message.body,
                "html": getattr(message, "html", None),
                "template": template,
            }
        )

    if app.config.get("MAIL_SUPPRESS_SEND"):
        app.logger.info(
            "MAIL_SUPPRESS_SEND active; recorded email to in-memory outbox only"
        )
        return message

    mail.send(message)
    app.logger.info("Email dispatched directly to %s", recipients)
    return message


def _dispatch_email(
    *, subject, recipients, body, sender=None, html=None, template=None
):
    """Send email synchronously in tests, optionally delegating to Celery in production."""
    use_async = (
        celery
        and not app.config.get("TESTING")
        and is_realtime_feature_enabled("background")
    )

    if use_async:
        try:
            from tasks import send_email_task

            send_email_task.delay(
                subject=subject,
                recipients=recipients,
                body=body,
                sender=sender,
                html=html,
            )
            return None
        except Exception as exc:  # pragma: no cover - defensive logging
            app.logger.error("Falling back to direct email send: %s", exc)

    return send_email_now(
        subject=subject,
        recipients=recipients,
        body=body,
        sender=sender,
        html=html,
        template=template,
    )


# Set SECRET_KEY for sessions and security
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", secrets.token_hex(32))

# Initialize SocketIO conditionally
if is_realtime_feature_enabled("websocket"):
    from flask_socketio import SocketIO

    transports = ["polling", "websocket"]
    allow_upgrades = True
    async_mode = "gevent"
    gevent_ready = False

    try:
        from gevent import monkey

        monkey.patch_all()
        from gevent import __version__ as gevent_version
        from gevent.pywsgi import WSGIServer
        from geventwebsocket.handler import WebSocketHandler

        gevent_ready = True
        app.logger.info("Gevent detected; enabling native WebSocket transport")
        app.logger.debug("Gevent version: %s", gevent_version)
        app.config["SOCKETIO_GEVENT_SERVER"] = WSGIServer
        app.config["SOCKETIO_WEBSOCKET_HANDLER"] = WebSocketHandler
    except Exception as err:
        gevent_ready = False
        async_mode = "threading"
        transports = ["polling"]
        allow_upgrades = False
        app.logger.warning(
            "Gevent dependencies missing or failed to initialize; falling back to long-polling only. Error: %s",
            err,
        )

    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode=async_mode,
        transports=transports,
        allow_upgrades=allow_upgrades,
    )

    app.config["SOCKETIO_TRANSPORTS"] = transports
    app.config["SOCKETIO_ALLOW_UPGRADES"] = allow_upgrades
    app.config["SOCKETIO_ASYNC_MODE"] = async_mode
    app.config["SOCKETIO_GEVENT_ENABLED"] = gevent_ready

    # Initialize RealTimeNotifications with SocketIO instance
    from advanced_analytics import RealTimeNotifications

    realtime_notifications = RealTimeNotifications(
        socketio, feature_checker=is_realtime_feature_enabled
    )
else:
    socketio = None
    realtime_notifications = None
    app.logger.info("WebSocket integration disabled via realtime settings")
    app.config["SOCKE" "TIO_TRANSPORTS"] = ["polling"]
    app.config["SOCKETIO_ALLOW_UPGRADES"] = False

# TEMPORARILY DISABLE Flask-Session to test standard Flask sessions
# Configure Flask-Session for better session persistence in development
# app.config['SESSION_TYPE'] = 'filesystem'  # Store sessions on filesystem
# app.config['SESSION_FILE_DIR'] = os.path.join(os.path.dirname(__file__), 'flask_sessions')
# app.config['SESSION_PERMANENT'] = True
# app.config['SESSION_USE_SIGNER'] = True
# app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 hour

# Initialize Flask-Session
# Session(app)


# Initialize Celery (optional - app will work without it)
def make_celery(app):
    try:
        celery = Celery(
            app.import_name,
            backend=os.getenv(
                "CELERY_RESULT_BACKEND",
                os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            ),
            broker_url=os.getenv(
                "CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0")
            ),
        )
        celery.conf.update(app.config)

        class ContextTask(celery.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        celery.Task = ContextTask
        return celery
    except Exception as e:
        app.logger.warning(f"Celery initialization failed (Redis not available): {e}")
        app.logger.warning("Background tasks will not be available")
        return None


# Initialize Celery only when background processing is enabled
if is_realtime_feature_enabled("background"):
    celery = make_celery(app)
else:
    celery = None
    app.logger.info("Background processing disabled via realtime settings")

# Configure Celery if available
if celery:
    celery.conf.update(
        result_expires=3600,
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
    )

# Задаваме SECRET_KEY за сесии и сигурност - ПРЕМЕСТЕН ПО-ГОРЕ ПРЕДИ Session(app)

# Конфигурация за URL генерация извън контекста на заявка
# app.config["SERVER_NAME"] = os.getenv("SERVER_NAME", "localhost:3000")
app.config["PREFERRED_URL_SCHEME"] = os.getenv("PREFERRED_URL_SCHEME", "http")

# Initialize Sentry for error monitoring
try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration

    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[FlaskIntegration()],
            traces_sample_rate=1.0,
            environment="production" if not app.debug else "development",
            # Capture performance data
            enable_tracing=True,
            # Capture request bodies for debugging (be careful with sensitive data)
            request_bodies="small",
            # Capture SQL queries
            sql_queries=True,
            # Set sample rate for performance monitoring
            profiles_sample_rate=1.0 if not app.debug else 0.1,
        )
        app.logger.info("Sentry error monitoring initialized successfully")
    else:
        app.logger.warning("SENTRY_DSN not configured, Sentry monitoring disabled")
except ImportError:
    app.logger.warning("sentry-sdk not installed, error monitoring disabled")
except Exception as e:
    app.logger.error(f"Failed to initialize Sentry: {e}")

# Абсолютен път до базата за по-голяма сигурност
basedir = os.path.abspath(os.path.dirname(__file__))
# За production на Render, използвайме променлива от средата или persistent директория
database_url = os.getenv("DATABASE_URL")
use_postgres = os.getenv("USE_POSTGRES") == "true"

if database_url and use_postgres:
    # Use PostgreSQL when DATABASE_URL is provided and USE_POSTGRES is true
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    logger.info("Using PostgreSQL database from environment")
else:
    # Локално development - използвайме instance директория в backend папката
    instance_dir = os.path.join(basedir, "instance")
    os.makedirs(instance_dir, exist_ok=True)
    db_path = os.path.join(instance_dir, "volunteers.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    logger.info(f"Using SQLite database: {db_path}")

masked_db_uri = _mask_secret_in_uri(app.config.get("SQLALCHEMY_DATABASE_URI"))
logger.info("Database URI configured: %s", masked_db_uri)
logger.debug("Database URI (debug): %s", masked_db_uri)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Configure database connection pooling
if database_url and use_postgres:
    # PostgreSQL production configuration
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,  # Check connections before use
        "pool_size": 10,  # Number of connections to keep in pool
        "max_overflow": 20,  # Additional connections beyond pool_size
        "pool_timeout": 30,  # Seconds to wait for a connection
        "pool_recycle": 3600,  # Recycle connections after 1 hour
        "echo": False,  # Disable SQL query logging in production
        "connect_args": {"server_settings": {"application_name": "helpchain"}},
    }
    logger.info("Configured PostgreSQL connection pooling")
else:
    # SQLite development configuration
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,  # Check connections before use
        "pool_timeout": 30,  # Seconds to wait for a connection
        "pool_recycle": 3600,  # Recycle connections after 1 hour (SQLite specific)
        "connect_args": {
            "check_same_thread": False,  # Allow multi-threading with SQLite
        },
        "echo": False,  # Disable SQL query logging
    }
    logger.info("Configured SQLite connection pooling")

db.init_app(app)
migrate = Migrate(app, db)

# Ensure the SQLAlchemy engine is initialized for the primary app context.
with app.app_context():
    _ = db.engine

# Initialize cache
if cache is not None:
    cache.init_app(app)


def _run_migrations_with_fallback():
    """Apply Alembic migrations when available, or fall back to create_all."""
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "") or ""

    if uri.startswith("sqlite:///:memory:"):
        app.logger.info(
            "In-memory database detected; using db.create_all() for schema setup."
        )
        db.create_all()
        return

    try:
        from flask_migrate import upgrade as flask_upgrade
    except ImportError:
        app.logger.warning(
            "Flask-Migrate not available; falling back to db.create_all()."
        )
        db.create_all()
        return

    try:
        flask_upgrade()
        app.logger.info("Database migrations applied successfully")
    except Exception as migration_error:  # pragma: no cover - protective fallback
        app.logger.warning(
            "Migration upgrade failed (%s); falling back to db.create_all().",
            migration_error,
        )
        db.create_all()
        app.logger.info("Database tables created via db.create_all() fallback")


# Initialize database in production mode
def initialize_database():
    """Initialize database tables and default data for production"""
    try:
        with app.app_context():
            _run_migrations_with_fallback()

            # Initialize default admin user
            try:
                admin_user = initialize_default_admin()
                if admin_user:
                    app.logger.info("Default admin user initialized")
                else:
                    app.logger.warning("Failed to initialize default admin user")
            except Exception as admin_error:
                app.logger.warning(f"Admin initialization failed: {admin_error}")

            # Initialize default roles and permissions
            try:
                initialize_default_roles_and_permissions()
                app.logger.info("Default roles and permissions initialized")
            except Exception as roles_error:
                app.logger.warning(f"Roles initialization failed: {roles_error}")

            # Initialize performance optimizations
            try:
                from performance_optimization import setup_performance_optimizations

                setup_performance_optimizations(app, db)
                app.logger.info("Performance optimizations initialized")

                # Initialize performance benchmarking when available
                try:
                    importlib.import_module("performance_benchmarking")
                except ImportError:
                    app.logger.info(
                        "Performance benchmarking module not available; skipping"
                    )
                else:
                    app.logger.info("Performance benchmarking initialized")
            except Exception as perf_error:
                app.logger.warning(f"Performance optimizations failed: {perf_error}")

    except Exception as e:
        app.logger.error(f"Database initialization failed: {e}")
        # Don't fail the app startup, just log the error


# Initialize database if in production mode
if os.getenv("RENDER") == "true" or os.getenv("PRODUCTION") == "true":
    initialize_database()
else:
    # Initialize database in development mode
    try:
        with app.app_context():
            _run_migrations_with_fallback()

            # Initialize default admin user for development
            try:
                admin_user = initialize_default_admin()
                if admin_user:
                    app.logger.info("Default admin user initialized for development")
                else:
                    app.logger.warning(
                        "Failed to initialize default admin user for development"
                    )
            except Exception as admin_error:
                app.logger.warning(
                    f"Admin initialization failed for development: {admin_error}"
                )

            # Initialize default roles and permissions for development
            try:
                initialize_default_roles_and_permissions()
                app.logger.info(
                    "Default roles and permissions initialized for development"
                )
            except Exception as roles_error:
                app.logger.warning(
                    f"Roles initialization failed for development: {roles_error}"
                )

            # Initialize performance optimizations for development
            try:
                # Check if Redis is available, otherwise use simple cache
                redis_url = os.getenv("REDIS_URL")
                if redis_url:
                    # Use Redis cache if REDIS_URL is set
                    app.config["CACHE_TYPE"] = "redis"
                    app.config["CACHE_REDIS_URL"] = redis_url
                    app.config["CACHE_DEFAULT_TIMEOUT"] = 300
                    print("✅ Using Redis cache for development")
                else:
                    # Force simple cache for development (no Redis dependency)
                    app.config["CACHE_TYPE"] = "simple"
                    app.config["CACHE_DEFAULT_TIMEOUT"] = 300
                    print("⚠️  Using simple cache for development (no REDIS_URL)")

                from performance_optimization import setup_performance_optimizations

                setup_performance_optimizations(app, db)
                app.logger.info("Performance optimizations initialized for development")

                # Initialize performance benchmarking
                try:
                    importlib.import_module("performance_benchmarking")
                except ImportError:
                    app.logger.info(
                        "Performance benchmarking module not available; skipping"
                    )
                except Exception as perf_error:
                    app.logger.warning(f"Performance benchmarking failed: {perf_error}")
                    # Continue without performance benchmarking
            except Exception as perf_error:
                app.logger.warning(
                    f"Performance setup failed for development: {perf_error}"
                )

    except Exception as e:
        app.logger.error(f"Database initialization failed for development: {e}")
        # Don't fail the app startup, just log the error

# Езици
app.config["BABEL_DEFAULT_LOCALE"] = "bg"
app.config["BABEL_SUPPORTED_LOCALES"] = ["bg", "en", "fr"]
app.config["BABEL_TRANSLATION_DIRECTORIES"] = os.path.join(
    os.path.dirname(__file__),
    "translations",
)


def get_locale():
    """Determine the best locale for the current request"""
    supported_locales = {"bg", "en", "fr"}

    # Allow explicit override via query parameter to work without cookies
    url_lang = request.args.get("lang")
    if url_lang in supported_locales:
        session["language"] = url_lang
        app.logger.debug("Locale resolved from query parameter: %s", url_lang)
        return url_lang

    # Check if language is set in session
    session_lang = session.get("language")
    if session_lang and session_lang in supported_locales:
        app.logger.debug("Locale resolved from session: %s", session_lang)
        return session_lang

    # Check browser language preference
    browser_lang = request.accept_languages.best_match(sorted(supported_locales))
    if browser_lang:
        app.logger.debug("Locale resolved from browser: %s", browser_lang)
        return browser_lang

    # Default to Bulgarian
    app.logger.debug("Locale defaulted to 'bg'")
    return "bg"


babel = Babel(app, locale_selector=get_locale)


def _is_safe_redirect_target(target: str | None) -> bool:
    """Ensure redirect stays on the same host."""
    if not target:
        return False

    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in {"http", "https"} and ref_url.netloc == test_url.netloc


def _add_language_query(target: str, language: str | None) -> str:
    """Ensure the redirect target carries a lang query parameter for stateless clients."""
    if not language:
        return target

    parsed = urlparse(target)
    if not parsed.netloc and not parsed.path:
        return target

    query_params = parse_qs(parsed.query, keep_blank_values=True)
    current_value = query_params.get("lang", [None])
    if current_value == [language]:
        return target

    query_params["lang"] = [language]
    new_query = urlencode(query_params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _get_language_redirect_target(language: str | None) -> str:
    """Pick a safe redirect target after changing language."""
    candidate = request.values.get("next")
    if _is_safe_redirect_target(candidate):
        return _add_language_query(candidate, language)

    referrer = request.referrer
    if _is_safe_redirect_target(referrer):
        return _add_language_query(referrer, language)

    return _add_language_query(url_for("index"), language)


@app.route("/set_language/<language>", methods=["GET", "POST"])
def set_language(language):
    """Set language preference for the user session"""
    if language in {"bg", "en", "fr"}:
        session["language"] = language
        # Refresh babel to use new language
        refresh()
    return redirect(_get_language_redirect_target(language))


@app.context_processor
def inject_global_locale():
    """Expose current locale to templates for lang attributes and helpers."""
    return {
        "current_locale": get_locale(),
        "socketio_transports": app.config.get("SOCKETIO_TRANSPORTS", ["polling"]),
    }


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# Email configuration
app.config["MAIL_DEFAULT_SENDER"] = os.getenv(
    "MAIL_DEFAULT_SENDER", app.config.get("MAIL_DEFAULT_SENDER")
)

mail_server_env = os.getenv("MAIL_SERVER")
if mail_server_env:
    app.config["MAIL_SERVER"] = mail_server_env

app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", app.config.get("MAIL_PORT", 587)))
app.config["MAIL_USE_TLS"] = (
    os.getenv("MAIL_USE_TLS", str(app.config.get("MAIL_USE_TLS", True))).lower()
    == "true"
)
app.config["MAIL_USE_SSL"] = (
    os.getenv("MAIL_USE_SSL", str(app.config.get("MAIL_USE_SSL", False))).lower()
    == "true"
)
app.config["MAIL_USERNAME"] = os.getenv(
    "MAIL_USERNAME", app.config.get("MAIL_USERNAME")
)
app.config["MAIL_PASSWORD"] = os.getenv(
    "MAIL_PASSWORD", app.config.get("MAIL_PASSWORD")
)

logger.info("Email configuration loaded")
logger.debug(f"MAIL_SERVER: {app.config.get('MAIL_SERVER')}")
logger.debug(f"MAIL_PORT: {app.config.get('MAIL_PORT')}")
logger.debug(f"MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS')}")
logger.debug(f"MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
logger.debug(f"MAIL_DEFAULT_SENDER: {app.config.get('MAIL_DEFAULT_SENDER')}")

# Compression configuration
app.config["COMPRESS_MIMETYPES"] = [
    "text/html",
    "text/css",
    "text/xml",
    "application/json",
    "application/javascript",
    "text/javascript",
]
app.config["COMPRESS_LEVEL"] = 6  # Compression level (1-9)
app.config["COMPRESS_MIN_SIZE"] = 500  # Minimum size to compress (bytes)


def _should_gzip_response(response):
    """Determine whether the current response should be gzip-compressed."""
    if response.direct_passthrough:
        return False

    if response.status_code < 200 or response.status_code >= 300:
        return False

    if "Content-Encoding" in response.headers:
        return False

    accept_encoding = request.headers.get("Accept-Encoding", "")
    if "gzip" not in accept_encoding.lower():
        return False

    if response.mimetype not in app.config["COMPRESS_MIMETYPES"]:
        return False

    payload = response.get_data()
    if payload is None or len(payload) < app.config["COMPRESS_MIN_SIZE"]:
        return False

    return True


def _gzip_response(response):
    """Apply gzip compression to the response payload."""
    payload = response.get_data()
    compressed_payload = gzip.compress(
        payload, compresslevel=app.config.get("COMPRESS_LEVEL", 6)
    )
    response.set_data(compressed_payload)
    response.headers["Content-Encoding"] = "gzip"
    vary = response.headers.get("Vary")
    response.headers["Vary"] = (
        "Accept-Encoding" if not vary else f"{vary}, Accept-Encoding"
    )
    response.headers["Content-Length"] = str(len(compressed_payload))
    return response


# Initialize Flask-Compress for API response compression (optional)
if FLASK_COMPRESS_AVAILABLE:
    try:
        compress = Compress()
        compress.init_app(app)
        app.logger.info("Flask-Compress initialized successfully")
    except Exception as e:
        app.logger.warning(f"Flask-Compress initialization failed: {e}")
        compress = None
else:
    app.logger.warning("Flask-Compress not available, compression disabled")
    compress = None


if not compress:

    @app.after_request
    def apply_manual_gzip(response):
        try:
            if _should_gzip_response(response):
                return _gzip_response(response)
        except Exception as compression_error:  # pragma: no cover - fallback logging
            app.logger.warning("Manual gzip compression failed: %s", compression_error)
        return response


# Security configurations
app.config["SESSION_COOKIE_SECURE"] = False  # Disabled for development
app.config["SESSION_COOKIE_HTTPONLY"] = False  # Changed to False for testing
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # Lax works for localhost HTTP
# app.config["SESSION_COOKIE_DOMAIN"] = "localhost"  # Not set for localhost development

# Upload folder configuration
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB limit

if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])

# Initialize security extensions
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",  # In production, use Redis
)


@limiter.request_filter
def skip_realtime_rate_limits():
    """Allow high-frequency endpoints to bypass global rate limiting."""
    path = request.path or ""
    if path.startswith("/socket.io/") or path == "/socket.io":
        return True
    if path == "/sw.js":
        return True
    return False


# Register blueprints after app is created

# Register analytics blueprint first to avoid import issues
try:
    analytics_routes_module = importlib.import_module("analytics_routes")
except ImportError:
    analytics_routes_module = importlib.import_module("backend.analytics_routes")

analytics_bp = analytics_routes_module.analytics_bp

app.register_blueprint(analytics_bp, url_prefix="/analytics")

# Initialize analytics cache with app
try:
    from performance_optimization import AnalyticsCache

    analytics_cache = AnalyticsCache()
    analytics_cache.init_app(app)
    app.analytics_cache = analytics_cache  # Store in app for access by decorators
    app.logger.info("Analytics cache initialized successfully")
except Exception as e:
    app.logger.error(f"Failed to initialize analytics cache: {e}")
    app.analytics_cache = None

# Initialize analytics service with database session
try:
    from analytics_service import init_analytics_service

    init_analytics_service(db.session)
    app.logger.info("Analytics service initialized successfully")
except Exception as e:
    app.logger.error(f"Failed to initialize analytics service: {e}")


# Test direct route
@app.route("/test_analytics")
def test_analytics():
    return "test analytics direct"


@app.route("/test_notifications")
def test_notifications():
    """Test endpoint to trigger real-time notifications"""
    if not realtime_notifications:
        return (
            jsonify(
                {"error": "Real-time notifications not available (SocketIO disabled)"}
            ),
            503,
        )

    from datetime import datetime

    # Test anomaly broadcast
    anomaly = {
        "type": "traffic_spike",
        "severity": "high",
        "description": "Test anomaly: High traffic detected",
        "timestamp": datetime.now(),
    }
    realtime_notifications.broadcast_anomaly(anomaly)

    # Test milestone broadcast
    milestone = {"value": 100, "metric": "requests processed today"}
    realtime_notifications.broadcast_milestone(milestone)

    return jsonify(
        {"status": "Notifications sent", "anomaly": anomaly, "milestone": milestone}
    )


# Test routes for error handlers
@app.route("/test/trigger-400", methods=["GET"])
def trigger_400():
    """Test route to trigger 400 Bad Request error"""
    app.logger.info("trigger_400 route called")
    print("DEBUG: trigger_400 route handler executed")
    from flask import abort

    abort(400, "Test 400 error for bad request")


@app.route("/test/trigger-401")
def trigger_401():
    """Test route to trigger 401 Unauthorized error"""
    from flask import abort

    print("DEBUG: trigger_401 route handler executed")
    abort(401, "Test 401 error for authentication")


@app.route("/test/trigger-429")
def trigger_429():
    """Test route to trigger 429 Too Many Requests error"""
    from flask import abort

    print("DEBUG: trigger_429 route handler executed")
    abort(429, "Test 429 error for rate limiting")


@app.route("/test/trigger-validation-error")
def trigger_validation_error():
    """Test route to trigger ValueError (validation error)"""
    print("DEBUG: trigger_validation_error route handler executed")
    raise ValueError("Test validation error")


@app.route("/test/trigger-database-error")
def trigger_database_error():
    """Test route to trigger database OperationalError"""
    print("DEBUG: trigger_database_error route handler executed")
    raise OperationalError("Test database error", None, None)


@app.route("/email_healthz")
def email_healthz():
    """Health check endpoint for email/SMTP connectivity"""
    try:
        import smtplib
        import ssl

        server = app.config.get("MAIL_SERVER")
        port = app.config.get("MAIL_PORT", 587)
        use_ssl = app.config.get("MAIL_USE_SSL", False)
        use_tls = app.config.get("MAIL_USE_TLS", True)
        username = app.config.get("MAIL_USERNAME")
        password = app.config.get("MAIL_PASSWORD")

        if not server:
            return (
                jsonify({"status": "error", "message": "MAIL_SERVER not configured"}),
                500,
            )

        # Test SMTP connection
        try:
            if use_ssl:
                smtp = smtplib.SMTP_SSL(server, port, timeout=10)
            else:
                smtp = smtplib.SMTP(server, port, timeout=10)

            # Test EHLO
            smtp.ehlo()

            # Start TLS if configured and not using SSL
            if use_tls and not use_ssl:
                context = ssl.create_default_context()
                smtp.starttls(context=context)
                smtp.ehlo()

            # Test authentication if credentials provided
            if username and password:
                smtp.login(username, password)

            # Close connection
            smtp.quit()

            return jsonify(
                {
                    "status": "ok",
                    "server": server,
                    "port": port,
                    "secure": use_ssl or use_tls,
                    "auth": bool(username and password),
                    "timestamp": datetime.now().isoformat(),
                }
            )

        except smtplib.SMTPException as e:
            return (
                jsonify(
                    {
                        "status": "error",
                        "server": server,
                        "port": port,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    }
                ),
                503,
            )
        except Exception as e:
            return (
                jsonify(
                    {
                        "status": "error",
                        "server": server,
                        "port": port,
                        "error": f"Connection failed: {str(e)}",
                        "timestamp": datetime.now().isoformat(),
                    }
                ),
                503,
            )

    except Exception as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "error": f"Health check failed: {str(e)}",
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            500,
        )


@app.route("/sw.js")
def service_worker():
    """Serve the service worker file from the root directory"""
    sw_path = os.path.join(os.path.dirname(__file__), "sw.js")
    return send_file(sw_path, mimetype="application/javascript")


app.register_blueprint(admin_roles_bp, url_prefix="/admin/roles")

# Register notification blueprint
app.register_blueprint(notification_bp, url_prefix="/notifications")
app.register_blueprint(notification_api_alias_bp, url_prefix="/api/notification")


# SocketIO Event Handlers for real-time features (only if SocketIO is enabled)
if socketio:
    # User presence tracking
    active_users = {}

    @socketio.on("connect")
    def handle_connect():
        """Handle client connection"""
        if not is_realtime_feature_enabled("websocket"):
            app.logger.info(
                "Rejecting SocketIO connection because websocket feature is disabled"
            )
            return False
        app.logger.info(f"Client connected: {request.sid}")
        socketio.emit("connected", {"status": "success", "sid": request.sid})

    @socketio.on("disconnect")
    def handle_disconnect():
        """Handle client disconnection"""
        app.logger.info(f"Client disconnected: {request.sid}")

        # Remove user from active users
        user_id = None
        for uid, sid in active_users.items():
            if sid == request.sid:
                user_id = uid
                break

        if user_id:
            del active_users[user_id]
            # Broadcast user offline status
            socketio.emit(
                "user_status_change",
                {
                    "user_id": user_id,
                    "status": "offline",
                    "timestamp": datetime.now().isoformat(),
                },
            )

    @socketio.on("join_analytics")
    def handle_join_analytics(data):
        """Handle joining analytics room for real-time updates"""
        if not is_realtime_feature_enabled(
            "websocket"
        ) or not is_realtime_feature_enabled("charts"):
            app.logger.debug("join_analytics ignored because charts feature disabled")
            return
        room = data.get("room", "analytics")
        join_room(room)
        app.logger.info(f"Client joined analytics room: {room}")
        socketio.emit("joined_room", {"room": room}, room=room)

    @socketio.on("leave_analytics")
    def handle_leave_analytics(data):
        """Handle leaving analytics room"""
        room = data.get("room", "analytics")
        leave_room(room)
        app.logger.info(f"Client left analytics room: {room}")

    @socketio.on("request_analytics_update")
    def handle_analytics_update():
        """Handle request for analytics data update"""
        if not is_realtime_feature_enabled(
            "websocket"
        ) or not is_realtime_feature_enabled("charts"):
            app.logger.debug("Analytics update skipped (charts feature disabled)")
            return
        try:
            from analytics_service import analytics_service

            # Get latest analytics data
            dashboard_data = analytics_service.get_dashboard_analytics()

            # Structure data for real-time chart updates
            realtime_data = {
                "trends": {
                    "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
                    "requests": [10, 15, 8, 22, 18, 25],
                    "completed": [8, 12, 6, 18, 15, 20],
                    "volunteers": [5, 7, 4, 12, 9, 14],
                },
                "categories": {
                    "labels": ["Medical", "Transport", "Household", "Education"],
                    "data": [15, 8, 12, 6],
                },
                "geo": {
                    "labels": ["Sofia", "Plovdiv", "Varna", "Burgas", "Other"],
                    "data": [45, 23, 18, 12, 8],
                },
                "requests_today": dashboard_data.get("totals", {}).get("requests", 0),
                "success_rate": 85.5,
                "avg_response_time": 2.3,
                "active_volunteers": dashboard_data.get("totals", {}).get(
                    "volunteers", 0
                ),
                "timestamp": datetime.now().isoformat(),
            }

            socketio.emit("analytics_update", realtime_data)
        except Exception as e:
            app.logger.error(f"Error sending analytics update: {e}")

    # Chat WebSocket Events
    @socketio.on("join_chat_room")
    def handle_join_chat_room(data):
        """Handle joining a chat room"""
        room_id = data.get("room_id")
        user_id = data.get("user_id")
        user_name = data.get("user_name", "Anonymous")

        if room_id and user_id:
            room_name = f"chat_{room_id}"
            join_room(room_name)

            # Update user presence
            active_users[user_id] = request.sid

            # Broadcast user joined
            socketio.emit(
                "user_joined",
                {
                    "user_id": user_id,
                    "user_name": user_name,
                    "timestamp": datetime.now().isoformat(),
                },
                room=room_name,
            )

            # Send online status update
            socketio.emit(
                "user_status_change",
                {
                    "user_id": user_id,
                    "status": "online",
                    "room_id": room_id,
                    "timestamp": datetime.now().isoformat(),
                },
            )

            app.logger.info(f"User {user_id} joined chat room {room_id}")

    @socketio.on("leave_chat_room")
    def handle_leave_chat_room(data):
        """Handle leaving a chat room"""
        room_id = data.get("room_id")
        user_id = data.get("user_id")
        user_name = data.get("user_name", "Anonymous")

        if room_id:
            room_name = f"chat_{room_id}"
            leave_room(room_name)

            # Broadcast user left
            socketio.emit(
                "user_left",
                {
                    "user_id": user_id,
                    "user_name": user_name,
                    "timestamp": datetime.now().isoformat(),
                },
                room=room_name,
            )

            app.logger.info(f"User {user_id} left chat room {room_id}")

    @socketio.on("send_message")
    def handle_send_message(data):
        """Handle sending a chat message"""
        try:
            room_id = data.get("room_id")
            user_id = data.get("user_id")
            user_name = data.get("user_name", "Anonymous")
            message_text = data.get("message", "").strip()
            message_type = data.get("message_type", "text")

            if not room_id or not message_text:
                return

            # Save message to database
            from extensions import db
            from models import ChatMessage

            message = ChatMessage(
                room_id=room_id,
                sender_id=user_id,
                sender_name=user_name,
                message=message_text,
                message_type=message_type,
            )

            db.session.add(message)
            db.session.commit()

            # Broadcast message to room
            room_name = f"chat_{room_id}"
            message_data = {
                "id": message.id,
                "room_id": room_id,
                "sender_id": user_id,
                "sender_name": user_name,
                "message": message_text,
                "message_type": message_type,
                "timestamp": message.created_at.isoformat(),
            }

            socketio.emit("new_message", message_data, room=room_name)

            # Track analytics
            try:
                from analytics_service import analytics_service

                analytics_service.track_event(
                    event_type="chat_message",
                    event_category="communication",
                    event_action="send_message",
                    context={"room_id": room_id, "message_type": message_type},
                )
            except Exception as analytics_error:
                app.logger.warning(f"Analytics tracking failed: {analytics_error}")

            app.logger.info(f"Message sent in room {room_id} by user {user_id}")

        except Exception as e:
            app.logger.error(f"Error sending message: {e}")
            socketio.emit("message_error", {"error": "Failed to send message"})

    @socketio.on("typing_start")
    def handle_typing_start(data):
        """Handle user started typing"""
        room_id = data.get("room_id")
        user_id = data.get("user_id")
        user_name = data.get("user_name", "Anonymous")

        if room_id:
            room_name = f"chat_{room_id}"
            socketio.emit(
                "user_typing",
                {
                    "user_id": user_id,
                    "user_name": user_name,
                    "typing": True,
                    "timestamp": datetime.now().isoformat(),
                },
                room=room_name,
                skip_sid=request.sid,
            )  # Don't send to sender

    @socketio.on("typing_stop")
    def handle_typing_stop(data):
        """Handle user stopped typing"""
        room_id = data.get("room_id")
        user_id = data.get("user_id")
        user_name = data.get("user_name", "Anonymous")

        if room_id:
            room_name = f"chat_{room_id}"
            socketio.emit(
                "user_typing",
                {
                    "user_id": user_id,
                    "user_name": user_name,
                    "typing": False,
                    "timestamp": datetime.now().isoformat(),
                },
                room=room_name,
                skip_sid=request.sid,
            )  # Don't send to sender

    @socketio.on("mark_message_read")
    def handle_mark_message_read(data):
        """Handle marking messages as read"""
        room_id = data.get("room_id")
        user_id = data.get("user_id")
        message_ids = data.get("message_ids", [])

        if room_id and message_ids:
            try:
                from extensions import db
                from models import ChatMessage

                # Update read status (you might want to add a read_by field to the model)
                # For now, just track the read event
                room_name = f"chat_{room_id}"
                socketio.emit(
                    "messages_read",
                    {
                        "user_id": user_id,
                        "message_ids": message_ids,
                        "timestamp": datetime.now().isoformat(),
                    },
                    room=room_name,
                    skip_sid=request.sid,
                )

                app.logger.info(
                    f"User {user_id} marked messages as read in room {room_id}"
                )

            except Exception as e:
                app.logger.error(f"Error marking messages as read: {e}")

    # Real-time Request Updates
    @socketio.on("join_requests")
    def handle_join_requests(data):
        """Handle joining requests room for real-time updates"""
        user_type = data.get("user_type", "volunteer")  # admin, volunteer, requester
        join_room("requests")

        if user_type == "admin":
            join_room("admin_requests")
        elif user_type == "volunteer":
            join_room("volunteer_requests")

        socketio.emit(
            "joined_requests",
            {"user_type": user_type, "timestamp": datetime.now().isoformat()},
        )

    @socketio.on("leave_requests")
    def handle_leave_requests(data):
        """Handle leaving requests room"""
        user_type = data.get("user_type", "volunteer")
        leave_room("requests")

        if user_type == "admin":
            leave_room("admin_requests")
        elif user_type == "volunteer":
            leave_room("volunteer_requests")

    @socketio.on("request_status_update")
    def handle_request_status_update(data):
        """Handle request status updates (admin only)"""
        if not session.get("admin_logged_in"):
            return

        request_id = data.get("request_id")
        new_status = data.get("status")
        admin_id = session.get("admin_user_id")

        if request_id and new_status:
            try:
                from extensions import db
                from models import HelpRequest

                request_obj = db.session.get(HelpRequest, request_id)
                if request_obj:
                    old_status = request_obj.status
                    if new_status == "completed":
                        request_obj.mark_completed()
                    else:
                        request_obj.status = new_status
                        if new_status != "completed":
                            request_obj.completed_at = None
                    request_obj.updated_at = datetime.now()
                    db.session.commit()

                    # Broadcast status update
                    update_data = {
                        "request_id": request_id,
                        "old_status": old_status,
                        "new_status": new_status,
                        "updated_by": admin_id,
                        "timestamp": datetime.now().isoformat(),
                    }

                    socketio.emit("request_updated", update_data, room="requests")
                    socketio.emit("request_updated", update_data, room="admin_requests")

                    # Track analytics
                    try:
                        from analytics_service import analytics_service

                        analytics_service.track_event(
                            event_type="request_update",
                            event_category="admin",
                            event_action="status_change",
                            context={
                                "request_id": request_id,
                                "old_status": old_status,
                                "new_status": new_status,
                            },
                        )
                    except Exception as analytics_error:
                        app.logger.warning(
                            f"Analytics tracking failed: {analytics_error}"
                        )

                    app.logger.info(
                        f"Request {request_id} status updated from {old_status} to {new_status}"
                    )

            except Exception as e:
                app.logger.error(f"Error updating request status: {e}")
                db.session.rollback()

    @socketio.on("volunteer_assigned")
    def handle_volunteer_assigned(data):
        """Handle volunteer assignment to request"""
        if not session.get("admin_logged_in"):
            return

        request_id = data.get("request_id")
        volunteer_id = data.get("volunteer_id")
        admin_id = session.get("admin_user_id")

        if request_id and volunteer_id:
            try:
                from extensions import db
                from models import HelpRequest, Volunteer

                request_obj = db.session.get(HelpRequest, request_id)
                volunteer = db.session.get(Volunteer, volunteer_id)

                if request_obj and volunteer:
                    request_obj.assigned_volunteer_id = volunteer_id
                    request_obj.status = "assigned"
                    request_obj.updated_at = datetime.now()
                    db.session.commit()

                    # Broadcast assignment
                    assignment_data = {
                        "request_id": request_id,
                        "volunteer_id": volunteer_id,
                        "volunteer_name": volunteer.name,
                        "assigned_by": admin_id,
                        "timestamp": datetime.now().isoformat(),
                    }

                    socketio.emit(
                        "volunteer_assigned", assignment_data, room="requests"
                    )
                    socketio.emit(
                        "volunteer_assigned", assignment_data, room="volunteer_requests"
                    )

                    app.logger.info(
                        f"Volunteer {volunteer.name} assigned to request {request_id}"
                    )

            except Exception as e:
                app.logger.error(f"Error assigning volunteer: {e}")
                db.session.rollback()

    # Live Volunteer Status Updates
    @socketio.on("volunteer_status_update")
    def handle_volunteer_status_update(data):
        """Handle volunteer status updates (available/busy/offline)"""
        volunteer_id = data.get("volunteer_id")
        status = data.get("status")  # available, busy, offline
        location = data.get("location")  # optional location data

        if volunteer_id and status:
            try:
                from extensions import db
                from models import Volunteer

                volunteer = db.session.get(Volunteer, volunteer_id)
                if volunteer:
                    volunteer.status = status
                    volunteer.last_seen = datetime.now()
                    if location:
                        volunteer.latitude = location.get("lat")
                        volunteer.longitude = location.get("lng")
                    db.session.commit()

                    # Broadcast status update
                    status_data = {
                        "volunteer_id": volunteer_id,
                        "volunteer_name": volunteer.name,
                        "status": status,
                        "location": location,
                        "timestamp": datetime.now().isoformat(),
                    }

                    socketio.emit(
                        "volunteer_status_changed", status_data, room="requests"
                    )
                    socketio.emit(
                        "volunteer_status_changed", status_data, room="admin_requests"
                    )

                    app.logger.info(
                        f"Volunteer {volunteer.name} status updated to {status}"
                    )

            except Exception as e:
                app.logger.error(f"Error updating volunteer status: {e}")

    @socketio.on("request_volunteer_location")
    def handle_request_volunteer_location(data):
        """Request current location from volunteer"""
        volunteer_id = data.get("volunteer_id")

        if volunteer_id:
            # Send location request to specific volunteer
            volunteer_sid = active_users.get(volunteer_id)
            if volunteer_sid:
                socketio.emit(
                    "location_requested",
                    {
                        "requester_id": data.get("requester_id"),
                        "timestamp": datetime.now().isoformat(),
                    },
                    room=volunteer_sid,
                )

    @socketio.on("volunteer_location_update")
    def handle_volunteer_location_update(data):
        """Handle volunteer location updates"""
        volunteer_id = data.get("volunteer_id")
        location = data.get("location")

        if volunteer_id and location:
            try:
                from extensions import db
                from models import Volunteer

                volunteer = db.session.get(Volunteer, volunteer_id)
                if volunteer:
                    volunteer.latitude = location.get("lat")
                    volunteer.longitude = location.get("lng")
                    volunteer.last_location_update = datetime.now()
                    db.session.commit()

                    # Broadcast location update to relevant rooms
                    location_data = {
                        "volunteer_id": volunteer_id,
                        "location": location,
                        "timestamp": datetime.now().isoformat(),
                    }

                    socketio.emit(
                        "volunteer_location_updated", location_data, room="requests"
                    )
                    socketio.emit(
                        "volunteer_location_updated",
                        location_data,
                        room="admin_requests",
                    )

            except Exception as e:
                app.logger.error(f"Error updating volunteer location: {e}")

    # Enhanced Analytics Real-time Features
    @socketio.on("subscribe_analytics")
    def handle_subscribe_analytics(data):
        """Subscribe to specific analytics updates"""
        if not is_realtime_feature_enabled(
            "websocket"
        ) or not is_realtime_feature_enabled("charts"):
            app.logger.debug(
                "subscribe_analytics ignored due to charts feature disabled"
            )
            return
        metrics = data.get("metrics", [])
        user_id = data.get("user_id")

        if user_id:
            join_room(f"analytics_{user_id}")

            # Send initial comprehensive data
            try:
                from analytics_service import analytics_service

                dashboard_data = analytics_service.get_dashboard_analytics()

                # Structure comprehensive initial data
                initial_data = {
                    "trends": {
                        "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
                        "requests": [10, 15, 8, 22, 18, 25],
                        "completed": [8, 12, 6, 18, 15, 20],
                        "volunteers": [5, 7, 4, 12, 9, 14],
                    },
                    "categories": {
                        "labels": ["Medical", "Transport", "Household", "Education"],
                        "data": [15, 8, 12, 6],
                    },
                    "geo": {
                        "labels": ["Sofia", "Plovdiv", "Varna", "Burgas", "Other"],
                        "data": [45, 23, 18, 12, 8],
                    },
                    "requests_today": dashboard_data.get("totals", {}).get(
                        "requests", 0
                    ),
                    "success_rate": 85.5,
                    "avg_response_time": 2.3,
                    "active_volunteers": dashboard_data.get("totals", {}).get(
                        "volunteers", 0
                    ),
                    "timestamp": datetime.now().isoformat(),
                }

                socketio.emit(
                    "analytics_subscribed",
                    {
                        "metrics": metrics,
                        "initial_data": initial_data,
                        "timestamp": datetime.now().isoformat(),
                    },
                    room=request.sid,
                )

            except Exception as e:
                app.logger.error(f"Error sending initial analytics data: {e}")

    @socketio.on("unsubscribe_analytics")
    def handle_unsubscribe_analytics(data):
        """Unsubscribe from analytics updates"""
        if not is_realtime_feature_enabled("websocket"):
            return
        user_id = data.get("user_id")

        if user_id:
            leave_room(f"analytics_{user_id}")
            socketio.emit(
                "analytics_unsubscribed",
                {"timestamp": datetime.now().isoformat()},
                room=request.sid,
            )

    @socketio.on("request_live_metrics")
    def handle_request_live_metrics():
        """Send live metrics update"""
        if not is_realtime_feature_enabled(
            "websocket"
        ) or not is_realtime_feature_enabled("charts"):
            app.logger.debug("Live metrics request ignored; charts feature disabled")
            return
        try:
            from analytics_service import analytics_service

            # Get real-time metrics
            live_data = analytics_service.get_dashboard_analytics()

            # Structure live metrics data
            live_metrics = {
                "requests_today": live_data.get("totals", {}).get("requests", 0),
                "success_rate": 85.5,  # Calculate from actual data
                "avg_response_time": 2.3,  # Calculate from actual data
                "active_volunteers": live_data.get("totals", {}).get("volunteers", 0),
                "server_timestamp": datetime.now().isoformat(),
            }

            socketio.emit("live_metrics_update", live_metrics, room=request.sid)

        except Exception as e:
            app.logger.error(f"Error sending live metrics: {e}")

    # User Presence and Activity
    @socketio.on("user_presence_update")
    def handle_user_presence_update(data):
        """Handle user presence updates"""
        user_id = data.get("user_id")
        presence_status = data.get("status")  # online, away, busy, offline
        user_name = data.get("user_name")

        if user_id:
            if presence_status == "offline":
                if user_id in active_users:
                    del active_users[user_id]
            else:
                active_users[user_id] = request.sid

            # Broadcast presence change
            socketio.emit(
                "user_presence_changed",
                {
                    "user_id": user_id,
                    "user_name": user_name,
                    "status": presence_status,
                    "timestamp": datetime.now().isoformat(),
                },
                room="requests",
            )  # Broadcast to requests room

    @socketio.on("get_online_users")
    def handle_get_online_users():
        """Send list of currently online users"""
        online_users = []
        for user_id, sid in active_users.items():
            # You might want to get user names from database here
            online_users.append({"user_id": user_id, "sid": sid})

        socketio.emit(
            "online_users_list",
            {
                "users": online_users,
                "count": len(online_users),
                "timestamp": datetime.now().isoformat(),
            },
            room=request.sid,
        )


# CSP configuration - TEMPORARILY PERMISSIVE TO OVERRIDE CACHE
csp = {
    "default-src": ["'self'"],
    "script-src": [
        "'self'",
        "'unsafe-inline'",
        "https://cdn.jsdelivr.net",
        "https://cdnjs.cloudflare.com",
        "*",
    ],
    "style-src": [
        "'self'",
        "'unsafe-inline'",
        "https://cdn.jsdelivr.net",
        "https://cdnjs.cloudflare.com",
        "https://fonts.googleapis.com",
        "*",
    ],
    "img-src": ["'self'", "data:", "https://helpchain.live", "*"],
    "font-src": [
        "'self'",
        "https://cdnjs.cloudflare.com",
        "https://cdn.jsdelivr.net",
        "*",
    ],
    "connect-src": ["'self'", "https://cdn.jsdelivr.net", "*"],
    "frame-ancestors": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
}

# Temporarily disable Talisman for testing routes
# talisman = Talisman(
#     app,
#     content_security_policy=csp,  # TEMPORARILY PERMISSIVE TO OVERRIDE BROWSER CACHE
#     content_security_policy_report_uri="https://csp-report.helpchain.live/report",
#     force_https=False,  # Disabled for development testing
#     strict_transport_security=False,  # TEMPORARILY DISABLED FOR TESTING
#     strict_transport_security_preload=True,
#     strict_transport_security_include_subdomains=True,
#     strict_transport_security_max_age=63072000,  # 2 years
#     referrer_policy="strict-origin-when-cross-origin",
#     permissions_policy={
#         "camera": "()",
#         "microphone": "()",
#         "geolocation": "()",
#         "payment": "()",
#         "usb": "()",
#         "magnetometer": "()",
#         "accelerometer": "()",
#         "gyroscope": "()",
#         "ambient-light-sensor": "()",
#         "autoplay": "()",
#         "encrypted-media": "()",
#         "fullscreen": "()",
#         "picture-in-picture": "()",
#     },
#     feature_policy={},  # Deprecated, but keeping for compatibility
# )


# Add CSP headers manually to ensure they are applied
@app.after_request
def add_csp_headers(response):
    """Add Content Security Policy headers to all responses"""
    csp_value = (
        "default-src 'self'; "
        "font-src 'self' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://fonts.gstatic.com; "
        "script-src 'self' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://cdn.socket.io 'unsafe-inline'; "
        "style-src 'self' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net 'unsafe-inline'; "
        "connect-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.socket.io; "
        "img-src 'self' data: https://helpchain.live *; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    response.headers["Content-Security-Policy"] = csp_value
    return response


# csrf = CSRFProtect(app)  # Disabled for development testing

# CORS configuration - STRICT allowlist (no wildcards)
# cors = CORS(
#     app,
#     resources={
#         r"/api/*": {
#             "origins": [
#                 "https://helpchain.live",
#                 "https://www.helpchain.live",
#                 # Add staging if needed: "https://staging.helpchain.live"
#             ],
#             "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
#             "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
#             "supports_credentials": False,  # Never allow credentials for API
#             "max_age": 86400,  # Cache preflight for 24h
#         }
#     },
#     # Disable CORS for non-API routes (default deny)
# )

# Настройваме Jinja да търси шаблони в няколко възможни директории
_template_dirs = [
    os.path.join(os.path.dirname(__file__), "templates"),
    os.path.join(os.path.dirname(__file__), "HelpChain.bg", "backend", "templates"),
    os.path.join(os.path.dirname(__file__), "helpchain-backend", "src", "templates"),
]
_loaders = [FileSystemLoader(d) for d in _template_dirs if os.path.isdir(d)]
# добавяме текущия loader в края (ако има)
if _loaders:
    app.jinja_loader = ChoiceLoader(
        _loaders + ([app.jinja_loader] if getattr(app, "jinja_loader", None) else [])
    )


# Добавяме strftime филтър за Jinja2
@app.template_filter("strftime")
def strftime_filter(date, format="%Y-%m-%d %H:%M:%S"):
    if date is None:
        return ""
    return date.strftime(format)


# Добавяме strptime филтър за Jinja2
@app.template_filter("strptime")
def strptime_filter(date_string, format="%Y-%m-%dT%H:%M:%S.%f"):
    if date_string is None:
        return ""
    from datetime import datetime

    try:
        return datetime.strptime(date_string, format)
    except ValueError:
        return ""


@app.before_request
def log_request():
    try:
        app.logger.info(
            f"Request: {request.method} {request.url} - Path: {request.path}"
        )
        print(f"DEBUG: Request: {request.method} {request.url} - Path: {request.path}")
    except Exception as e:
        print(f"DEBUG: Error in before_request: {e}")


# Error handlers
@app.errorhandler(404)
def page_not_found(error):
    """Handle 404 errors with custom template"""
    app.logger.warning(f"404 error: {request.url} - {error}")

    # Track analytics for 404 errors
    try:
        from analytics_service import analytics_service

        analytics_service.track_event(
            event_type="error",
            event_category="navigation",
            event_action="404_not_found",
            context={
                "url": request.url,
                "method": request.method,
                "user_agent": request.headers.get("User-Agent"),
                "ip": request.remote_addr,
                "referrer": request.headers.get("Referer"),
                "error_message": str(error),
            },
        )
    except Exception as analytics_error:
        app.logger.warning(f"Analytics tracking failed: {analytics_error}")

    if request.is_json or request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "error": "Not Found",
                    "message": "Страницата или ресурсът не е намерен. Моля, проверете адреса.",
                    "status_code": 404,
                }
            ),
            404,
        )
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def internal_server_error(error):
    """Handle 500 errors with custom template and error tracking"""
    app.logger.error(f"500 error: {request.url} - {error}", exc_info=app.debug)

    # Track error in analytics if available
    try:
        from analytics_service import analytics_service

        analytics_service.track_event(
            event_type="error",
            event_category="system",
            event_action="500_error",
            context={
                "url": request.url,
                "method": request.method,
                "user_agent": request.headers.get("User-Agent"),
                "ip": request.remote_addr,
                "error_message": str(error),
            },
        )
    except Exception as analytics_error:
        app.logger.warning(f"Failed to track 500 error: {analytics_error}")

    if request.is_json or request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "error": "Internal Server Error",
                    "message": "Възникна неочаквана грешка. Нашият екип е уведомен и работи по проблема. Моля, опитайте отново по-късно.",
                    "status_code": 500,
                }
            ),
            500,
        )
    return render_template("errors/500.html"), 500


@app.errorhandler(403)
def forbidden(error):
    """Handle 403 errors"""
    app.logger.warning(f"403 error: {request.url} - {error}")

    # Track analytics for forbidden access
    try:
        from analytics_service import analytics_service

        analytics_service.track_event(
            event_type="error",
            event_category="security",
            event_action="403_forbidden",
            context={
                "url": request.url,
                "method": request.method,
                "user_agent": request.headers.get("User-Agent"),
                "ip": request.remote_addr,
                "error_message": str(error),
            },
        )
    except Exception as analytics_error:
        app.logger.warning(f"Analytics tracking failed: {analytics_error}")

    if request.is_json or request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "error": "Forbidden",
                    "message": "You don't have permission to access this resource",
                    "status_code": 403,
                }
            ),
            403,
        )
    flash("Нямате права за достъп до тази страница.", "error")
    return redirect(url_for("index"))


@app.errorhandler(422)
def unprocessable_entity(error):
    """Handle 422 validation errors"""
    app.logger.warning(f"422 error: {request.url} - Validation failed")

    # Track analytics for validation errors
    try:
        from analytics_service import analytics_service

        analytics_service.track_event(
            event_type="error",
            event_category="validation",
            event_action="422_validation_error",
            context={
                "url": request.url,
                "method": request.method,
                "user_agent": request.headers.get("User-Agent"),
                "ip": request.remote_addr,
                "error_message": str(error),
            },
        )
    except Exception as analytics_error:
        app.logger.warning(f"Analytics tracking failed: {analytics_error}")

    if request.is_json or request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "error": "Unprocessable Entity",
                    "message": "Данните са невалидни или непълни. Моля, проверете въведената информация.",
                    "status_code": 422,
                }
            ),
            422,
        )
    flash("Данните са невалидни. Моля, проверете формата и опитайте отново.", "error")
    return redirect(request.referrer or url_for("index"))


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file upload size limits"""
    app.logger.warning(f"413 error: {request.url} - File too large")

    # Track analytics for file size errors
    try:
        from analytics_service import analytics_service

        analytics_service.track_event(
            event_type="error",
            event_category="upload",
            event_action="413_file_too_large",
            context={
                "url": request.url,
                "method": request.method,
                "user_agent": request.headers.get("User-Agent"),
                "ip": request.remote_addr,
                "content_length": request.headers.get("Content-Length"),
                "error_message": str(error),
            },
        )
    except Exception as analytics_error:
        app.logger.warning(f"Analytics tracking failed: {analytics_error}")

    if request.is_json or request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "error": "Request Entity Too Large",
                    "message": "Файлът е твърде голям. Максималният размер е 5MB.",
                    "status_code": 413,
                }
            ),
            413,
        )
    flash("Файлът е твърде голям. Максималният размер е 5MB.", "error")
    return redirect(request.referrer or url_for("index"))


@app.errorhandler(400)
def bad_request(error):
    """Handle 400 Bad Request errors"""
    app.logger.warning(f"400 error: {request.url} - {error}")

    # Track analytics for bad requests
    try:
        from analytics_service import analytics_service

        analytics_service.track_event(
            event_type="error",
            event_category="client",
            event_action="400_bad_request",
            context={
                "url": request.url,
                "method": request.method,
                "user_agent": request.headers.get("User-Agent"),
                "ip": request.remote_addr,
                "error_message": str(error),
            },
        )
    except Exception as analytics_error:
        app.logger.warning(f"Analytics tracking failed: {analytics_error}")

    if request.is_json or request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "error": "Bad Request",
                    "message": "Невалидна заявка. Моля, проверете данните и опитайте отново.",
                    "status_code": 400,
                }
            ),
            400,
        )
    return render_template("errors/400.html"), 400


@app.errorhandler(401)
def unauthorized(error):
    """Handle 401 Unauthorized errors"""
    app.logger.warning(f"401 error: {request.url} - {error}")

    # Track analytics for unauthorized access
    try:
        from analytics_service import analytics_service

        analytics_service.track_event(
            event_type="error",
            event_category="security",
            event_action="401_unauthorized",
            context={
                "url": request.url,
                "method": request.method,
                "user_agent": request.headers.get("User-Agent"),
                "ip": request.remote_addr,
                "error_message": str(error),
            },
        )
    except Exception as analytics_error:
        app.logger.warning(f"Analytics tracking failed: {analytics_error}")

    if request.is_json or request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "error": "Unauthorized",
                    "message": "Нямате права за достъп до този ресурс. Моля, влезте в системата.",
                    "status_code": 401,
                }
            ),
            401,
        )
    return render_template("errors/401.html"), 401


@app.errorhandler(429)
def too_many_requests(error):
    """Handle 429 Too Many Requests errors (rate limiting)"""
    app.logger.warning(f"429 error: {request.url} - Rate limit exceeded")

    # Track analytics for rate limiting
    try:
        from analytics_service import analytics_service

        analytics_service.track_event(
            event_type="error",
            event_category="security",
            event_action="429_rate_limited",
            context={
                "url": request.url,
                "method": request.method,
                "user_agent": request.headers.get("User-Agent"),
                "ip": request.remote_addr,
                "error_message": str(error),
            },
        )
    except Exception as analytics_error:
        app.logger.warning(f"Analytics tracking failed: {analytics_error}")

    if request.is_json or request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "error": "Too Many Requests",
                    "message": "Твърде много заявки. Моля, изчакайте малко преди да опитате отново.",
                    "status_code": 429,
                    "retry_after": 60,  # Suggest retry after 60 seconds
                }
            ),
            429,
        )
    return render_template("errors/429.html"), 429


# Database-specific error handlers
@app.errorhandler(OperationalError)
def handle_database_error(error):
    """Handle database operational errors (connection issues, etc.)"""
    app.logger.error(f"Database error: {request.url} - {error}", exc_info=app.debug)

    # Track analytics for database errors
    try:
        from analytics_service import analytics_service

        analytics_service.track_event(
            event_type="error",
            event_category="database",
            event_action="operational_error",
            context={
                "url": request.url,
                "method": request.method,
                "user_agent": request.headers.get("User-Agent"),
                "ip": request.remote_addr,
                "error_message": str(error),
            },
        )
    except Exception as analytics_error:
        app.logger.warning(f"Analytics tracking failed: {analytics_error}")

    if request.is_json or request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "error": "Database Error",
                    "message": "Възникна проблем с базата данни. Нашият екип е уведомен и работи по проблема.",
                    "status_code": 500,
                }
            ),
            500,
        )
    flash("Възникна техническа грешка. Моля, опитайте отново по-късно.", "error")
    return redirect(url_for("index"))


# Validation error handler
@app.errorhandler(ValueError)
def handle_validation_error(error):
    """Handle validation errors (ValueError, etc.)"""
    app.logger.warning(f"Validation error: {request.url} - {error}")

    # Track analytics for validation errors
    try:
        from analytics_service import analytics_service

        analytics_service.track_event(
            event_type="error",
            event_category="validation",
            event_action="value_error",
            context={
                "url": request.url,
                "method": request.method,
                "user_agent": request.headers.get("User-Agent"),
                "ip": request.remote_addr,
                "error_message": str(error),
            },
        )
    except Exception as analytics_error:
        app.logger.warning(f"Analytics tracking failed: {analytics_error}")

    if request.is_json or request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "error": "Validation Error",
                    "message": "Данните са невалидни. Моля, проверете въведената информация.",
                    "status_code": 400,
                }
            ),
            400,
        )
    flash("Данните са невалидни. Моля, проверете формата и опитайте отново.", "error")
    return redirect(request.referrer or url_for("index"))


# General exception handler for unhandled errors
@app.errorhandler(Exception)
def handle_unexpected_error(error):
    """Handle any unhandled exceptions"""
    # Show full tracebacks in console only in debug mode
    app.logger.error(f"Unexpected error: {request.url} - {error}", exc_info=app.debug)

    # Track analytics for unexpected errors
    try:
        from analytics_service import analytics_service

        analytics_service.track_event(
            event_type="error",
            event_category="system",
            event_action="unexpected_error",
            context={
                "url": request.url,
                "method": request.method,
                "user_agent": request.headers.get("User-Agent"),
                "ip": request.remote_addr,
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
        )
    except Exception as analytics_error:
        app.logger.warning(f"Analytics tracking failed: {analytics_error}")

    # Don't expose internal error details to users
    if request.is_json or request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "error": "Internal Server Error",
                    "message": "Възникна неочаквана грешка. Нашият екип е уведомен.",
                    "status_code": 500,
                }
            ),
            500,
        )
    return render_template("errors/500.html"), 500


@app.route("/")
def index():
    # безопасно извличаме агрегати — ако моделът липсва или схемата
    # не е съвместима, връщаме fallback
    db = get_db()
    try:
        volunteers_count = (
            db.session.query(Volunteer).count() if "Volunteer" in globals() else 0
        )
    except OperationalError:
        volunteers_count = 0
    except Exception:
        volunteers_count = 0

    try:
        HelpRequestModel = globals().get("HelpRequest")
        if HelpRequestModel is not None:
            requests_count = HelpRequestModel.query.count()
            open_requests = HelpRequestModel.query.filter(
                HelpRequestModel.status != "completed"
            ).count()
        else:
            requests_count = 0
            open_requests = 0
    except OperationalError:
        requests_count = 0
        open_requests = 0
    except Exception:
        requests_count = 0
        open_requests = 0

    if app.jinja_loader:
        return render_template(
            "index.html",
            volunteers_count=volunteers_count,
            requests_count=requests_count,
            open_requests=open_requests,
        )
    return (
        jsonify(
            {
                "volunteers_count": volunteers_count,
                "requests_count": requests_count,
                "open_requests": open_requests,
            }
        ),
        200,
    )


@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    logger.info("Admin login route called")
    logger.debug(
        f"Request method: {request.method}, EMAIL_2FA_ENABLED = {EMAIL_2FA_ENABLED}"
    )
    # DEBUG: Log current session state
    logger.info(f"admin_login called - session keys: {list(session.keys())}")
    logger.info(f"Current SECRET_KEY: {app.config.get('SECRET_KEY', 'NOT_SET')}")
    logger.info(
        f"Session cookie from request: {request.cookies.get('session', 'NO_COOKIE')}"
    )
    logger.info(f"Session object id: {id(session)}")
    error = None
    if request.method == "POST":
        logger.info("Processing admin login POST request")
        username = request.form.get("username")
        password = request.form.get("password")

        logger.debug(f"Login attempt for username: {username}")

        # Initialize default admin if needed
        admin_user = initialize_default_admin()
        if not admin_user:
            logger.error("Failed to initialize default admin user")
            error = "Грешка при инициализация на администраторски акаунт!"
        else:
            # Check credentials
            if (
                admin_user
                and username == admin_user.username
                and admin_user.check_password(password)
            ):
                logger.info(f"Admin login successful for {username}")
                # Check if 2FA is enabled
                if admin_user.two_factor_enabled:
                    logger.info("2FA is enabled, redirecting to 2FA verification")
                    session["pending_2fa"] = True
                    session["pending_admin_id"] = admin_user.id
                    return redirect(url_for("admin_2fa"))
                else:
                    logger.info("No 2FA required, redirecting to dashboard")
                    # Clear any volunteer session to prevent conflicts
                    session.pop("volunteer_logged_in", None)
                    session.pop("volunteer_id", None)
                    session.pop("volunteer_name", None)
                    # Set user session
                    session["admin_logged_in"] = True
                    session["admin_user_id"] = admin_user.id
                    session["admin_username"] = admin_user.username
                    session["user_id"] = (
                        admin_user.id
                    )  # For permission system compatibility
                    session.permanent = True  # Make session persistent
                    logger.info(
                        f"Session set: admin_logged_in={session.get('admin_logged_in')}, "
                        f"admin_user_id={session.get('admin_user_id')}"
                    )
                    return redirect(url_for("admin_dashboard"))
            else:
                logger.warning(
                    f"Failed login attempt for user: {username}, IP: {request.remote_addr}"
                )
                error = "Грешно потребителско име или парола!"
                # Log failed login attempt
                app.logger.warning(
                    f"Failed login attempt for user: {username}, IP: {request.remote_addr}"
                )
    return render_template("admin_login.html", error=error)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login_page():
    """Alias for admin_login to match test expectations"""
    return admin_login()


@app.route("/admin", methods=["GET"])
def admin_root():
    """Provide a stable entry point for the admin area used in tests."""
    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("admin_login"))


@app.route("/logout", methods=["GET", "POST"])
def logout():
    return admin_logout()


@app.route("/admin_logout", methods=["GET", "POST"])
def admin_logout():
    session.pop("admin_logged_in", None)
    session.pop("admin_user_id", None)
    session.pop("admin_username", None)
    session.pop("user_id", None)  # Clear permission system user_id
    flash("Излезе от админ панела.", "info")
    return redirect(url_for("admin_login"))


@app.route("/admin/api/requests", methods=["GET"])
@require_admin_login
def admin_requests_api():
    """Return help requests for the admin dashboard with advanced filters."""
    db_obj = get_db()
    session = db_obj.session
    query = session.query(HelpRequest)

    status_values = request.args.getlist("status")
    if not status_values:
        status_param = request.args.get("status")
        if status_param:
            status_values = status_param.split(",")

    statuses = [value.strip().lower() for value in status_values if value.strip()]
    if statuses:
        query = query.filter(func.lower(HelpRequest.status).in_(statuses))

    request_types = request.args.getlist("request_type")
    if not request_types:
        request_type_param = request.args.get("request_type")
        if request_type_param:
            request_types = request_type_param.split(",")

    clean_request_types = [value.strip() for value in request_types if value.strip()]
    if clean_request_types:
        query = query.filter(
            func.lower(HelpRequest.title).in_(
                [value.lower() for value in clean_request_types]
            )
        )

    city_param = request.args.get("city")
    if city_param:
        city_like = f"%{city_param.strip().lower()}%"
        query = query.filter(func.lower(HelpRequest.city).like(city_like))

    location_param = request.args.get("location")
    if location_param:
        location_like = f"%{location_param.strip().lower()}%"
        query = query.filter(func.lower(HelpRequest.location_text).like(location_like))

    volunteer_joined = False
    volunteer_id_param = request.args.get("volunteer_id")
    volunteer_name_param = request.args.get("volunteer_name")

    if volunteer_id_param or volunteer_name_param:
        query = query.join(Volunteer, HelpRequest.assigned_volunteer)
        volunteer_joined = True

        if volunteer_id_param:
            try:
                volunteer_id = int(volunteer_id_param)
                query = query.filter(HelpRequest.assigned_volunteer_id == volunteer_id)
            except ValueError:
                pass

        if volunteer_name_param:
            volunteer_like = f"%{volunteer_name_param.strip().lower()}%"
            query = query.filter(func.lower(Volunteer.name).like(volunteer_like))

    search_param = request.args.get("search")
    if search_param:
        search_like = f"%{search_param.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(HelpRequest.name).like(search_like),
                func.lower(HelpRequest.email).like(search_like),
                func.lower(HelpRequest.message).like(search_like),
                func.lower(HelpRequest.title).like(search_like),
            )
        )

    date_field = request.args.get("date_field", "created").lower()
    date_column = HelpRequest.created_at
    if date_field in {"completed", "completion"}:
        date_column = HelpRequest.completed_at
        query = query.filter(HelpRequest.completed_at.isnot(None))

    start_date = _parse_date_param(request.args.get("start_date"))
    end_date = _parse_date_param(request.args.get("end_date"), end_of_day=True)

    if start_date is not None:
        query = query.filter(date_column >= start_date)
    if end_date is not None:
        query = query.filter(date_column <= end_date)

    if not volunteer_joined:
        query = query.options(joinedload(HelpRequest.assigned_volunteer))

    total_query = query.order_by(None)
    total_count = total_query.count()

    status_rows = (
        total_query.with_entities(
            func.lower(HelpRequest.status).label("status"),
            func.count(HelpRequest.id),
        )
        .group_by("status")
        .all()
    )
    status_counts = {row.status or "unknown": row[1] for row in status_rows}
    status_counts["total"] = total_count

    page = max(int(request.args.get("page", 1)), 1)
    per_page = request.args.get("per_page", request.args.get("limit", 25))
    try:
        per_page = int(per_page)
    except (ValueError, TypeError):
        per_page = 25
    per_page = max(1, min(per_page, 100))

    sort_param = request.args.get("sort", "created_desc").lower()

    if sort_param == "created_asc":
        query = query.order_by(HelpRequest.created_at.asc())
    elif sort_param == "completed_desc":
        query = query.order_by(HelpRequest.completed_at.desc())
    elif sort_param == "completed_asc":
        query = query.order_by(HelpRequest.completed_at.asc())
    elif sort_param == "name_asc":
        query = query.order_by(func.lower(HelpRequest.name).asc())
    elif sort_param == "name_desc":
        query = query.order_by(func.lower(HelpRequest.name).desc())
    else:  # created_desc
        query = query.order_by(HelpRequest.created_at.desc())

    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    results = query.all()

    items = []
    for req in results:
        volunteer = (
            req.assigned_volunteer if hasattr(req, "assigned_volunteer") else None
        )
        items.append(
            {
                "id": req.id,
                "name": req.name,
                "status": req.status,
                "priority": (
                    req.priority.value
                    if hasattr(req.priority, "value")
                    else req.priority
                ),
                "request_type": req.request_type,
                "city": req.city,
                "location": req.location_text,
                "volunteer": {
                    "id": volunteer.id if volunteer else None,
                    "name": volunteer.name if volunteer else None,
                    "email": volunteer.email if volunteer else None,
                },
                "created_at": _format_datetime_for_response(req.created_at),
                "completed_at": _format_datetime_for_response(req.completed_at),
            }
        )

    return jsonify(
        {
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total_count,
                "pages": (total_count + per_page - 1) // per_page,
            },
            "counts": status_counts,
            "items": items,
        }
    )


@app.route("/admin/dashboard", endpoint="admin_dashboard")
@require_admin_login
def admin_dashboard():
    # DEBUG: Log session state
    app.logger.info(f"admin_dashboard called - session keys: {list(session.keys())}")
    app.logger.info(f"admin_logged_in: {session.get('admin_logged_in')}")
    app.logger.info(f"admin_user_id: {session.get('admin_user_id')}")
    app.logger.info(f"admin_username: {session.get('admin_username')}")
    app.logger.info(
        f"Session cookie from request: {request.cookies.get('session', 'NO_COOKIE')}"
    )
    app.logger.info(f"Session object id: {id(session)}")
    app.logger.info(f"Current SECRET_KEY: {app.config.get('SECRET_KEY', 'NOT_SET')}")

    # Get filter parameter
    filter_param = request.args.get("filter", "all")

    db = get_db()
    # Get real statistics from database
    try:
        # Check if HelpRequest model is available
        total_requests = db.session.query(HelpRequest).count()
        pending_requests = (
            db.session.query(HelpRequest)
            .filter(HelpRequest.status == "pending")
            .count()
        )
        completed_requests = (
            db.session.query(HelpRequest)
            .filter(HelpRequest.status == "completed")
            .count()
        )
        total_volunteers = db.session.query(Volunteer).count()
    except Exception as e:
        app.logger.error(f"Error fetching dashboard stats: {e}")
        total_requests = 0
        pending_requests = 0
        completed_requests = 0
        total_volunteers = 0

    # Get filtered requests based on filter parameter
    try:
        if filter_param == "pending":
            requests_query = db.session.query(HelpRequest).filter(
                HelpRequest.status == "pending"
            )
        elif filter_param == "completed":
            requests_query = db.session.query(HelpRequest).filter(
                HelpRequest.status == "completed"
            )
        else:  # "all" or default
            requests_query = db.session.query(HelpRequest)

        requests_query = requests_query.options(
            joinedload(HelpRequest.assigned_volunteer)
        )

        # Limit to recent requests for dashboard display
        requests = (
            requests_query.order_by(HelpRequest.created_at.desc()).limit(10).all()
        )

        # Convert to the expected format for template
        requests_data = []
        for req in requests:
            requests_data.append(
                {
                    "id": req.id,
                    "name": getattr(req, "name", "Неизвестно име"),
                    "status": req.status,
                    "request_type": req.request_type,
                    "city": req.city,
                    "location": getattr(req, "location_text", None),
                    "volunteer_name": getattr(req.assigned_volunteer, "name", None),
                    "created_at": (
                        req.created_at.strftime("%Y-%m-%d %H:%M")
                        if req.created_at
                        else "Няма дата"
                    ),
                    "completed_at": (
                        req.completed_at.strftime("%Y-%m-%d %H:%M")
                        if req.completed_at
                        else None
                    ),
                }
            )

        requests = {"items": requests_data}

    except Exception as e:
        app.logger.error(f"Error fetching filtered requests: {e}")
        requests = {
            "items": [
                {"id": 1, "name": "Мария", "status": "Активен"},
                {"id": 2, "name": "Георги", "status": "Завършен"},
            ]
        }

    logs_dict = {
        1: [{"status": "Активен", "changed_at": "2025-07-22"}],
        2: [{"status": "Завършен", "changed_at": "2025-07-21"}],
    }

    stats = {
        "total_requests": total_requests,
        "pending_requests": pending_requests,
        "completed_requests": completed_requests,
        "total_volunteers": total_volunteers,
    }

    # Get current admin user for template
    current_user = None
    if session.get("admin_user_id"):
        current_user = db.session.get(AdminUser, session.get("admin_user_id"))

    realtime_settings = load_realtime_settings()

    return render_template(
        "admin_dashboard.html",
        requests=requests,
        logs_dict=logs_dict,
        stats=stats,
        current_user=current_user,
        current_filter=filter_param,
        realtime_settings=realtime_settings,
    )


@app.route("/admin/settings/realtime", methods=["GET", "POST"])
@require_admin_login
def admin_realtime_settings():
    """Return or update realtime feature settings for the admin dashboard."""
    if request.method == "GET":
        return jsonify({"settings": load_realtime_settings()})

    payload = request.get_json(silent=True) or {}
    updated_settings = load_realtime_settings()

    for key in REALTIME_SETTINGS_DEFAULTS:
        updated_settings[key] = bool(payload.get(key, updated_settings[key]))

    try:
        save_realtime_settings(updated_settings)
    except OSError as error:
        app.logger.error("Failed to persist realtime settings: %s", error)
        return (
            jsonify({"error": "Unable to save realtime settings"}),
            500,
        )

    return jsonify({"success": True, "settings": updated_settings})


# Request management routes
@app.route("/admin/request/<int:request_id>/approve", methods=["POST"])
@require_admin_login
def admin_approve_request(request_id):
    """Approve a help request"""
    try:
        db = get_db()
        request_obj = db.session.query(HelpRequest).get_or_404(request_id)

        if request_obj.status != "pending":
            return (
                jsonify({"success": False, "message": "Заявката вече е обработена"}),
                400,
            )

        request_obj.status = "approved"
        db.session.commit()

        # Track analytics
        try:
            from analytics_service import analytics_service

            analytics_service.track_event(
                event_type="request_action",
                event_category="admin",
                event_action="approve_request",
                context={"request_id": request_id},
            )
        except Exception as analytics_error:
            app.logger.warning(f"Analytics tracking failed: {analytics_error}")

        return jsonify({"success": True, "message": "Заявката е одобрена успешно"})

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error approving request {request_id}: {e}")
        return (
            jsonify({"success": False, "message": "Грешка при одобряване на заявката"}),
            500,
        )


@app.route("/admin/request/<int:request_id>/reject", methods=["POST"])
@require_admin_login
def admin_reject_request(request_id):
    """Reject a help request"""
    try:
        db = get_db()
        data = request.get_json() or {}
        reason = data.get("reason", "").strip()

        request_obj = db.session.query(HelpRequest).get_or_404(request_id)

        if request_obj.status != "pending":
            return (
                jsonify({"success": False, "message": "Заявката вече е обработена"}),
                400,
            )

        request_obj.status = "rejected"
        if reason:
            # Store rejection reason (you might want to add a field to the model)
            request_obj.rejection_reason = reason

        db.session.commit()

        # Track analytics
        try:
            from analytics_service import analytics_service

            analytics_service.track_event(
                event_type="request_action",
                event_category="admin",
                event_action="reject_request",
                context={"request_id": request_id, "reason": reason},
            )
        except Exception as analytics_error:
            app.logger.warning(f"Analytics tracking failed: {analytics_error}")

        return jsonify({"success": True, "message": "Заявката е отхвърлена успешно"})

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error rejecting request {request_id}: {e}")
        return (
            jsonify({"success": False, "message": "Грешка при отхвърляне на заявката"}),
            500,
        )


@app.route("/admin/request/<int:request_id>/assign", methods=["POST"])
@require_admin_login
def admin_assign_volunteer(request_id):
    """Assign a volunteer to a help request"""
    try:
        db = get_db()
        data = request.get_json() or {}
        volunteer_id = data.get("volunteer_id")

        if not volunteer_id:
            return (
                jsonify({"success": False, "message": "Не е посочен доброволец"}),
                400,
            )

        request_obj = db.session.query(HelpRequest).get_or_404(request_id)
        volunteer = db.session.query(Volunteer).get_or_404(volunteer_id)

        if request_obj.status != "approved":
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Заявката трябва да бъде одобрена преди присвояване",
                    }
                ),
                400,
            )

        # Here you would typically create a task from the request
        # For now, just update the request status
        request_obj.status = "assigned"
        request_obj.assigned_volunteer_id = volunteer.id
        db.session.commit()

        # Track analytics
        try:
            from analytics_service import analytics_service

            analytics_service.track_event(
                event_type="request_action",
                event_category="admin",
                event_action="assign_volunteer",
                context={"request_id": request_id, "volunteer_id": volunteer_id},
            )
        except Exception as analytics_error:
            app.logger.warning(f"Analytics tracking failed: {analytics_error}")

        return jsonify(
            {
                "success": True,
                "message": f"Доброволецът {volunteer.name} е присвоен успешно",
            }
        )

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error assigning volunteer to request {request_id}: {e}")
        return (
            jsonify(
                {"success": False, "message": "Грешка при присвояване на доброволец"}
            ),
            500,
        )


@app.route("/admin/request/<int:request_id>/delete", methods=["POST"])
@require_admin_login
def admin_delete_request(request_id):
    """Delete a help request"""
    try:
        db = get_db()
        request_obj = db.session.query(HelpRequest).get_or_404(request_id)

        # Optional: Check if request can be deleted (not assigned, etc.)
        if request_obj.status == "assigned":
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Не може да изтриете присвоена заявка",
                    }
                ),
                400,
            )

        db.session.delete(request_obj)
        db.session.commit()

        # Track analytics
        try:
            from analytics_service import analytics_service

            analytics_service.track_event(
                event_type="request_action",
                event_category="admin",
                event_action="delete_request",
                context={"request_id": request_id},
            )
        except Exception as analytics_error:
            app.logger.warning(f"Analytics tracking failed: {analytics_error}")

        return jsonify({"success": True, "message": "Заявката е изтрита успешно"})

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting request {request_id}: {e}")
        return (
            jsonify({"success": False, "message": "Грешка при изтриване на заявката"}),
            500,
        )


@app.route("/admin/request/<int:request_id>", methods=["GET"])
@require_admin_login
def admin_request_details(request_id):
    """View details of a help request"""
    try:
        db = get_db()
        request_obj = db.session.query(HelpRequest).get_or_404(request_id)

        # Get current admin user
        current_user = None
        if session.get("admin_user_id"):
            current_user = db.session.get(AdminUser, session.get("admin_user_id"))

        # Get available volunteers for assignment (if request is approved)
        available_volunteers = []
        if request_obj.status == "approved":
            available_volunteers = (
                db.session.query(Volunteer).filter_by(is_active=True).all()
            )

        return render_template(
            "admin_request_details.html",
            request=request_obj,
            current_user=current_user,
            available_volunteers=available_volunteers,
        )

    except Exception as e:
        app.logger.error(f"Error loading request details {request_id}: {e}")
        flash("Грешка при зареждане на детайлите на заявката", "error")
        return redirect(url_for("admin_dashboard"))


@app.route("/admin/request/<int:request_id>/edit", methods=["GET", "POST"])
@require_admin_login
def admin_edit_request(request_id):
    """Edit a help request"""
    try:
        db = get_db()
        request_obj = db.session.query(HelpRequest).get_or_404(request_id)

        if request.method == "POST":
            # Update request fields
            request_obj.name = request.form.get("name", request_obj.name)
            request_obj.email = request.form.get("email", request_obj.email)
            request_obj.message = request.form.get("message", request_obj.message)
            request_obj.title = request.form.get("category", request_obj.title)
            request_obj.location_text = request.form.get(
                "location", request_obj.location_text
            )

            db.session.commit()

            flash("Заявката е обновена успешно!", "success")
            return redirect(url_for("admin_request_details", request_id=request_id))

        # Get current admin user
        current_user = None
        if session.get("admin_user_id"):
            current_user = db.session.get(AdminUser, session.get("admin_user_id"))

        return render_template(
            "admin_edit_request.html", request=request_obj, current_user=current_user
        )

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error editing request {request_id}: {e}")
        flash("Грешка при редактиране на заявката", "error")
        return redirect(url_for("admin_request_details", request_id=request_id))


@app.route("/profile", methods=["GET", "POST"], endpoint="profile")
def admin_profile():
    # Check if admin is logged in manually
    if not session.get("admin_logged_in"):
        flash("Моля, влезте като администратор.", "error")
        return redirect(url_for("admin_login"))

    # Get current admin user
    db = get_db()
    admin_user = None
    if session.get("admin_user_id"):
        admin_user = db.session.get(AdminUser, session.get("admin_user_id"))

    if not admin_user:
        flash("Не сте логнат като администратор.", "error")
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()

        if not username or not email:
            flash("Всички полета са задължителни.", "error")
            return render_template("admin_profile.html", current_user=admin_user)

        # Check if username is already taken by another admin
        existing_admin = (
            db.session.query(AdminUser)
            .filter(AdminUser.username == username, AdminUser.id != admin_user.id)
            .first()
        )

        if existing_admin:
            flash("Потребителското име вече е заето.", "error")
            return render_template("admin_profile.html", current_user=admin_user)

        # Check if email is already taken by another admin
        existing_email = (
            db.session.query(AdminUser)
            .filter(AdminUser.email == email, AdminUser.id != admin_user.id)
            .first()
        )

        if existing_email:
            flash("Имейлът вече е зает.", "error")
            return render_template("admin_profile.html", current_user=admin_user)

        # Update admin user
        admin_user.username = username
        admin_user.email = email
        db.session.commit()

        flash("Профилът е обновен успешно.", "success")
        return redirect(url_for("admin_profile"))

    return render_template("admin_profile.html", current_user=admin_user)


@app.route("/admin_settings", methods=["GET", "POST"], endpoint="admin_settings")
@require_admin_login
def admin_settings():
    # Get current admin user
    db = get_db()
    admin_user = None
    if session.get("admin_user_id"):
        admin_user = db.session.get(AdminUser, session.get("admin_user_id"))

    if not admin_user:
        flash("Не сте логнат като администратор.", "error")
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        # Handle settings updates (placeholder for now)
        flash("Настройките са запазени успешно.", "success")
        return redirect(url_for("admin_settings"))

    return render_template("admin_settings.html", current_user=admin_user)


@app.route(
    "/notification_dashboard", methods=["GET"], endpoint="notification_dashboard"
)
@require_admin_login
def notification_dashboard():
    # Get current admin user
    db = get_db()
    admin_user = None
    if session.get("admin_user_id"):
        admin_user = db.session.get(AdminUser, session.get("admin_user_id"))

    if not admin_user:
        flash("Не сте логнат като администратор.", "error")
        return redirect(url_for("admin_login"))

    # Placeholder for notification dashboard
    notifications = [
        {
            "id": 1,
            "type": "new_volunteer",
            "message": "Нов доброволец се регистрира",
            "timestamp": "2024-01-15 10:30",
        },
        {
            "id": 2,
            "type": "new_request",
            "message": "Нова заявка за помощ",
            "timestamp": "2024-01-15 09:15",
        },
    ]

    return render_template(
        "notification_dashboard.html",
        current_user=admin_user,
        notifications=notifications,
    )


@app.route("/export_data", methods=["GET"], endpoint="export_data")
@require_admin_login
def export_data():
    # Get current admin user
    db = get_db()
    admin_user = None
    if session.get("admin_user_id"):
        admin_user = db.session.get(AdminUser, session.get("admin_user_id"))

    if not admin_user:
        flash("Не сте логнат като администратор.", "error")
        return redirect(url_for("admin_login"))

    return render_template("export_data.html", current_user=admin_user)


@app.route("/admin/email_2fa", methods=["GET", "POST"])
def admin_email_2fa():
    if not session.get("pending_email_2fa"):
        return redirect(url_for("admin_login"))

    # Check if code has expired
    if datetime.now().timestamp() > session.get("email_2fa_expires", 0):
        session.pop("pending_email_2fa", None)
        session.pop("email_2fa_code", None)
        session.pop("email_2fa_expires", None)
        flash("Кодът за верификация е изтекъл. Моля, опитайте отново.", "error")
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        entered_code = request.form.get("code", "").strip()

        # Check code
        if entered_code == session.get("email_2fa_code"):
            # Code is correct, complete login
            db = get_db()
            admin_user = initialize_default_admin()
            session["user_id"] = admin_user.id
            session["username"] = admin_user.username
            session.pop("pending_email_2fa", None)
            session.pop("email_2fa_code", None)
            session.pop("email_2fa_expires", None)
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Невалиден код за верификация.", "error")

    return render_template("admin_email_2fa.html")


@app.route("/admin/2fa", methods=["GET", "POST"])
def admin_2fa():
    if not session.get("pending_2fa"):
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        token = request.form.get("token", "").strip()

        # Get admin user
        admin_id = session.get("pending_admin_id")
        if not admin_id:
            flash("Сесията е изтекла. Моля, логнете се отново.", "error")
            return redirect(url_for("admin_login"))

        db = get_db()
        admin_user = db.session.query(AdminUser).get(admin_id)
        if not admin_user:
            flash("Потребителят не е намерен.", "error")
            return redirect(url_for("admin_login"))

        # Verify TOTP token
        if admin_user.verify_totp(token):
            # 2FA successful, complete login
            session["admin_logged_in"] = True
            session["admin_user_id"] = admin_user.id
            session["admin_username"] = admin_user.username
            session.pop("pending_2fa", None)
            session.pop("pending_admin_id", None)
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Невалиден код за верификация.", "error")

    return render_template("admin_2fa.html")


@app.route("/admin/2fa/setup", methods=["GET", "POST"])
@require_admin_login
def admin_2fa_setup():
    # Get current admin user
    db = get_db()
    admin_user = None
    if session.get("admin_user_id"):
        admin_user = db.session.get(AdminUser, session.get("admin_user_id"))

    if not admin_user:
        flash("Не сте логнат като администратор.", "error")
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        token = request.form.get("token")
        if admin_user.verify_totp(token):
            admin_user.enable_2fa()
            db.session.commit()
            flash("2FA е активиран успешно!", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Невалиден код.", "error")

    uri = admin_user.get_totp_uri()
    return render_template("admin_2fa_setup.html", totp_uri=uri)


@app.route("/admin_volunteers", methods=["GET", "POST"])
@require_admin_login
def admin_volunteers():
    db = get_db()
    # Get filter parameters
    search = request.args.get("search", "")
    location_filter = request.args.get("location", "")
    sort_by = request.args.get("sort", "name")
    sort_order = request.args.get("order", "asc")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 25))

    try:
        # Build query
        query = db.session.query(Volunteer)

        # Apply filters
        if search:
            query = query.filter(
                (Volunteer.name.ilike(f"%{search}%"))
                | (Volunteer.email.ilike(f"%{search}%"))
                | (Volunteer.phone.ilike(f"%{search}%"))
            )

        if location_filter:
            query = query.filter(Volunteer.location.ilike(f"%{location_filter}%"))

        # Apply sorting
        if sort_by == "name":
            query = query.order_by(
                Volunteer.name.asc() if sort_order == "asc" else Volunteer.name.desc()
            )
        elif sort_by == "location":
            query = query.order_by(
                Volunteer.location.asc()
                if sort_order == "asc"
                else Volunteer.location.desc()
            )
        elif sort_by == "created_at":
            query = query.order_by(
                Volunteer.created_at.asc()
                if sort_order == "asc"
                else Volunteer.created_at.desc()
            )
        else:
            query = query.order_by(Volunteer.id.asc())

        # Apply pagination using SQLAlchemy's paginate method for better reliability
        try:
            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            volunteers = pagination.items
            total_volunteers = pagination.total
            total_pages = pagination.pages
        except Exception as e:
            # Fallback to manual pagination if paginate fails
            app.logger.warning(f"Pagination failed, using manual pagination: {e}")
            total_volunteers = query.count()
            volunteers = query.offset((page - 1) * per_page).limit(per_page).all()
            total_pages = (total_volunteers + per_page - 1) // per_page

            # Create a simple pagination object to match template expectations
            class SimplePagination:
                def __init__(self, page, per_page, total, items):
                    self.page = page
                    self.per_page = per_page
                    self.total = total
                    self.pages = (total + per_page - 1) // per_page
                    self.items = items

                @property
                def has_prev(self):
                    return self.page > 1

                @property
                def has_next(self):
                    return self.page < self.pages

                @property
                def prev_num(self):
                    return self.page - 1 if self.has_prev else None

                @property
                def next_num(self):
                    return self.page + 1 if self.has_next else None

            pagination = SimplePagination(page, per_page, total_volunteers, volunteers)

        app.logger.info(
            f"Admin volunteers query successful: {len(volunteers)} volunteers "
            f"returned, page {page}/{total_pages}"
        )

    except Exception as e:
        app.logger.error(f"Error in admin_volunteers: {e}", exc_info=app.debug)
        flash("Възникна грешка при зареждането на доброволците", "error")
        # Return empty results on error
        volunteers = []
        total_volunteers = 0
        total_pages = 1
        page = 1

        # Create a simple pagination object for error case
        class SimplePagination:
            def __init__(self):
                self.page = 1
                self.per_page = per_page
                self.total = 0
                self.pages = 1
                self.items = []

            @property
            def has_prev(self):
                return False

            @property
            def has_next(self):
                return False

            @property
            def prev_num(self):
                return None

            @property
            def next_num(self):
                return None

        pagination = SimplePagination()

    return render_template(
        "admin_volunteers.html",
        volunteers=volunteers,
        search=search,
        location_filter=location_filter,
        sort_by=sort_by,
        sort_order=sort_order,
        pagination=pagination,
    )


@app.route("/admin_volunteers/add", methods=["GET", "POST"])
@require_admin_login
def add_volunteer():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        location = request.form.get("location", "").strip()

        # Validate required fields
        errors = []
        if not name:
            errors.append("Името е задължително")
        if not email:
            errors.append("Имейлът е задължителен")
        if not phone:
            errors.append("Телефонът е задължителен")
        if not location:
            errors.append("Локацията е задължителна")

        # Basic email validation
        if email and "@" not in email:
            errors.append("Невалиден имейл адрес")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("add_volunteer.html")

        # Check if email already exists
        existing_volunteer = Volunteer.query.filter_by(email=email).first()
        if existing_volunteer:
            flash("Доброволец с този имейл вече съществува!", "error")
            return render_template("add_volunteer.html")

        try:
            volunteer = Volunteer(
                name=name.strip(),
                email=email.strip(),
                phone=phone.strip() if phone else None,
                location=location.strip() if location else None,
            )
            db.session.add(volunteer)
            db.session.commit()
            flash("Доброволецът е добавен успешно!", "success")
            return redirect(url_for("admin_volunteers"))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error adding volunteer: {e}")
            flash("Грешка при добавяне на доброволец. Опитайте отново.", "error")
            return render_template("add_volunteer.html")

    return render_template("add_volunteer.html")


@app.route("/submit_request", methods=["GET", "POST"])
@limiter.limit("20 per minute; 200 per day")
def submit_request():
    db = get_db()
    if request.method == "POST":
        # Enhanced input validation and sanitization
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        category = request.form.get("category", "").strip()
        location = request.form.get("location", "").strip()
        problem = request.form.get("problem", "").strip()
        captcha = request.form.get("captcha", "").strip()

        # Validate required fields
        errors = []
        if not name or len(name) < 2:
            errors.append("Името трябва да бъде поне 2 символа")
        if not email or "@" not in email:
            errors.append("Въведете валиден имейл адрес")
        if not category:
            errors.append("Изберете категория")
        if not location:
            errors.append("Въведете локация")
        if not problem or len(problem) < 10:
            errors.append("Опишете проблема си по-подробно (минимум 10 символа)")
        if captcha != "7G5K":
            errors.append("Грешен код за защита")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("submit_request.html")

        # Additional security checks
        if len(name) > 100:
            flash("Името е твърде дълго", "error")
            return render_template("submit_request.html")
        if len(email) > 100:
            flash("Имейлът е твърде дълг", "error")
            return render_template("submit_request.html")
        if len(location) > 100:
            flash("Локацията е твърде дълга", "error")
            return render_template("submit_request.html")
        if len(problem) > 2000:
            flash("Описанието е твърде дълго (максимум 2000 символа)", "error")
            return render_template("submit_request.html")

        # Check for suspicious content
        suspicious_patterns = ["<script", "javascript:", "onload=", "onclick="]
        combined_input = (name + email + location + problem).lower()
        if any(pattern in combined_input for pattern in suspicious_patterns):
            flash("Открито е подозрително съдържание във формата", "error")
            return render_template("submit_request.html")

        file = request.files.get("file")

        filename = None
        if file and file.filename:
            if not allowed_file(file.filename):
                flash("Позволени са само изображения и PDF файлове!", "error")
                return render_template("submit_request.html")

            # Enhanced file validation
            allowed_mimes = {"image/png", "image/jpg", "image/jpeg", "application/pdf"}
            if file.mimetype not in allowed_mimes:
                flash("Невалиден тип файл!", "error")
                return render_template("submit_request.html")

            # Check file size (additional to MAX_CONTENT_LENGTH)
            file.seek(0, 2)  # Seek to end
            file_size = file.tell()
            file.seek(0)  # Reset to beginning
            if file_size > 5 * 1024 * 1024:  # 5MB
                flash("Файлът е твърде голям (макс. 5MB)!", "error")
                return render_template("submit_request.html")

            # Basic antivirus check (placeholder - integrate with real AV service)
            # TODO: Integrate with ClamAV or similar service
            # For now, just check for suspicious file signatures
            dangerous_signatures = [
                b"<script",
                b"<?php",
                b"<%",
                b"eval(",
                b"javascript:",
            ]
            file_content_start = file.read(1024)
            file.seek(0)  # Reset
            if any(sig in file_content_start.lower() for sig in dangerous_signatures):
                flash("Файлът съдържа подозрително съдържание!", "error")
                return render_template("submit_request.html")

            filename = secure_filename(file.filename)
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)

        # Log sanitized request data
        request_data = {
            "name": name,
            "email": email[:3] + "***",  # Sanitize PII
            "category": category,
            "location": location,
            "problem": (
                problem[:50] + "..." if len(problem) > 50 else problem
            ),  # Truncate
            "filename": filename,
        }
        app.logger.info("submit_request received: %s", request_data)

        # TODO: Save to database instead of just logging
        try:
            help_request = HelpRequest(
                name=name,
                email=email,
                message=problem,
                description=problem,
                status="pending",
                source_channel="web_form",
            )
            if category:
                help_request.request_type = category
            if location:
                help_request.location = location
                # Extract city heuristically from the location string for filtering
                city_candidate = location.split(",")[0].strip()
                help_request.city = city_candidate or None
            if filename:
                # TODO: Save file reference
                pass

            db.session.add(help_request)
            db.session.commit()
            app.logger.info(
                "Help request saved to database with ID: %s", help_request.id
            )
        except Exception as e:
            db.session.rollback()
            app.logger.error("Error saving help request to database: %s", str(e))
            flash("Грешка при запазване на заявката. Моля, опитайте отново.", "error")
            return render_template("submit_request.html")

        return render_template("submit_success.html")
    return render_template("submit_request.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/volunteer_register", methods=["GET", "POST"])
@limiter.limit("10 per minute; 50 per day")
def volunteer_register():
    db = get_db()
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        location = request.form.get("location")

        # Валидация на задължителни полета
        if not name or not name.strip():
            flash("Моля, въведете име.", "error")
            return redirect(url_for("volunteer_register"))

        if not email or not email.strip():
            flash("Моля, въведете имейл.", "error")
            return redirect(url_for("volunteer_register"))

        # Основна валидация на имейл формат
        import re

        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            flash("Моля, въведете валиден имейл адрес.", "error")
            return redirect(url_for("volunteer_register"))

        # Провери дали имейлът вече съществува
        existing_volunteer = Volunteer.query.filter_by(email=email).first()
        if existing_volunteer:
            flash("Този имейл вече е регистриран като доброволец.", "error")
            return redirect(url_for("volunteer_register"))

        try:
            volunteer = Volunteer(
                name=name.strip(),
                email=email.strip(),
                phone=phone.strip() if phone else None,
                location=location.strip() if location else None,
            )
            db.session.add(volunteer)
            db.session.commit()
            logger.info(
                "Volunteer added successfully: %s",
                {"name": name, "email": email[:3] + "***", "location": location},
            )
        except Exception as e:
            logger.error("Database error adding volunteer: %s", str(e))
            return f"Database error: {e}", 500

        # Изпрати имейл нотификация за нов доброволец
        try:
            logger.debug(
                "Mail config - SERVER: %s, PORT: %s, USERNAME: %s, PASSWORD: %s",
                app.config.get("MAIL_SERVER"),
                app.config.get("MAIL_PORT"),
                app.config.get("MAIL_USERNAME"),
                "***" if app.config.get("MAIL_PASSWORD") else "None",
            )

            _dispatch_email(
                subject="Нов доброволец в HelpChain",
                recipients=["contact@helpchain.live"],
                body=f"""Нов доброволец се е регистрирал:

Име: {name}
Имейл: {email}
Телефон: {phone}
Локация: {location}

Моля, свържете се с доброволеца за допълнителна информация.
""",
                sender=app.config["MAIL_DEFAULT_SENDER"],
            )
            logger.info("Volunteer registration email sent successfully")
        except Exception as e:
            logger.error("Failed to send volunteer registration email: %s", str(e))
            # Fallback: записваме в файл
            try:
                with open("sent_emails.txt", "a", encoding="utf-8") as f:
                    f.write(
                        "Subject: Нов доброволец в HelpChain\n"
                        f"To: contact@helpchain.live\nFrom: {app.config['MAIL_DEFAULT_SENDER']}\n\n"
                        "Нов доброволец се е регистрирал:\n\n"
                        f"Име: {name}\nИмейл: {email}\nТелефон: {phone}\nЛокация: {location}\n\n"
                        "Моля, свържете се с доброволеца за допълнителна информация.\n\n"
                        f"{'=' * 50}\n"
                    )
                logger.info("Volunteer registration email saved to file as fallback")
            except Exception as file_e:
                logger.error("Failed to save email to file: %s", str(file_e))

        app.logger.info(
            "Volunteer registered successfully: %s",
            {
                "name": name,
                "email": email[:3] + "***",
                "phone": phone[:3] + "***",
                "location": location,
            },
        )

        flash("Успешна регистрация! Ще се свържем с вас при нужда.")
        return redirect(url_for("volunteer_register"))
    return render_template("volunteer_register.html")


@app.route("/volunteer_login", methods=["GET", "POST"])
def volunteer_login():
    # Check if already logged in as volunteer
    if session.get("volunteer_logged_in"):
        flash("Вече сте логнати като доброволец.", "info")
        return redirect(url_for("volunteer_dashboard"))

    # Allow admins to also login as volunteers - remove the admin check that was causing confusion
    # if session.get("admin_logged_in"):
    #     flash("Администраторите нямат достъп до доброволческия панел.", "warning")
    #     return redirect(url_for("admin_dashboard"))

    error = None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        app.logger.info(f"POST request received. Email: '{email}'")
        app.logger.info(f"Request form data: {dict(request.form)}")

        # Check if volunteer exists with this email
        try:
            logger.warning("Login attempt for email: %s", email)
            app.logger.warning(f"Login attempt for email: {email}")
            volunteer = Volunteer.query.filter_by(email=email).first()
            logger.warning("Volunteer found: %s", volunteer is not None)
            app.logger.info(f"Volunteer found: {volunteer is not None}")
            if volunteer:
                app.logger.info(
                    f"Volunteer details: ID={volunteer.id}, Name={volunteer.name}, "
                    f"Email={volunteer.email}"
                )

                otp_bypassed = (
                    DISABLE_VOLUNTEER_OTP
                    or email.lower() in VOLUNTEER_OTP_BYPASS_EMAILS
                )

                if otp_bypassed:
                    app.logger.info(
                        "Volunteer OTP disabled; granting access without code"
                    )
                    _activate_volunteer_session(volunteer)
                    session.pop("pending_volunteer_login", None)
                    flash("Успешен вход като доброволец.", "success")
                    return redirect(url_for("volunteer_dashboard"))

                # Generate 6-digit access code
                access_code = str(secrets.randbelow(900000) + 100000)
                app.logger.info(f"Generated access code: {access_code}")

                # Store in session with expiration (15 minutes)
                session["pending_volunteer_login"] = {
                    "email": email,
                    "volunteer_id": volunteer.id,
                    "access_code": access_code,
                    "expires": datetime.now().timestamp() + 900,  # 15 minutes
                }

                # Send email with access code
                try:
                    email_body = f"""Здравейте {volunteer.name},

Получен е опит за вход в доброволческия панел на HelpChain.

Код за достъп: {access_code}

Кодът е валиден за 15 минути.

Ако това не сте вие, моля игнорирайте това съобщение.

С уважение,
HelpChain системата
"""

                    _dispatch_email(
                        subject="HelpChain - Код за достъп",
                        recipients=[email],
                        body=email_body,
                    )
                    logger.warning("Access code sent to %s", email)
                    app.logger.info(f"Access code sent to {email}")
                except Exception as e:
                    app.logger.error(f"Failed to send access code email: {e}")
                    # Fallback: save to file for development
                    try:
                        with open("sent_emails.txt", "a", encoding="utf-8") as f:
                            fallback_content = (
                                "Subject: HelpChain - Код за достъп\n"
                                f"To: {email}\nFrom: {app.config['MAIL_DEFAULT_SENDER']}\n\n"
                                f"Здравейте {volunteer.name},\n\n"
                                "Получен е опит за вход в доброволческия панел на HelpChain.\n\n"
                                f"Вашият код за достъп: {access_code}\n\n"
                                "Кодът е валиден за 15 минути.\n\n"
                                "Ако това не сте вие, моля игнорирайте това съобщение.\n\n"
                                "С уважение,\nHelpChain системата\n\n"
                                f"{'=' * 50}\n"
                            )
                            f.write(fallback_content)
                        app.logger.info("Access code saved to file as fallback")
                    except Exception as file_e:
                        app.logger.error(f"Failed to save email to file: {file_e}")
                        return (
                            jsonify(
                                {
                                    "success": False,
                                    "message": "Грешка при изпращане на имейл.",
                                }
                            ),
                            500,
                        )

                # Redirect to verification page
                app.logger.info("Redirecting to volunteer_verify_code")
                return redirect(url_for("volunteer_verify_code"))
            else:
                error = "Няма регистриран доброволец с този имейл!"
                app.logger.warning(f"No volunteer found with email: {email}")
        except Exception as e:
            error = f"Database error: {e}"
            app.logger.error(
                f"Database error during volunteer login: {e}", exc_info=app.debug
            )
    return render_template("volunteer_login.html", error=error)


def _activate_volunteer_session(volunteer):
    """Establish volunteer session and clear conflicting admin state."""
    if volunteer is None:
        raise ValueError("Volunteer instance is required")

    # Clear any admin session to prevent conflicts
    session.pop("admin_logged_in", None)
    session.pop("admin_user_id", None)
    session.pop("admin_username", None)

    session.permanent = True
    session["volunteer_logged_in"] = True
    session["volunteer_id"] = volunteer.id
    session["volunteer_name"] = volunteer.name
    session.modified = True

    app.logger.info(
        "Volunteer session activated",
        extra={
            "volunteer_id": volunteer.id,
            "volunteer_name": volunteer.name,
        },
    )


@app.route("/volunteer_verify_code", methods=["GET", "POST"])
def volunteer_verify_code():
    # Check if there's a pending login
    pending = session.get("pending_volunteer_login")
    if not pending:
        flash("Няма чакащ процес на вход. Моля, започнете отново.", "error")
        return redirect(url_for("volunteer_login"))

    pending_email = (pending.get("email") or "").lower()

    # Check if code has expired
    if datetime.now().timestamp() > pending.get("expires", 0):
        session.pop("pending_volunteer_login", None)
        flash("Кодът за достъп е изтекъл. Моля, опитайте отново.", "error")
        return redirect(url_for("volunteer_login"))

    if DISABLE_VOLUNTEER_OTP or pending_email in VOLUNTEER_OTP_BYPASS_EMAILS:
        volunteer = _load_volunteer_by_id(pending["volunteer_id"])
        if volunteer:
            _activate_volunteer_session(volunteer)
            session.pop("pending_volunteer_login", None)
            flash("Успешен вход като доброволец.", "success")
            return redirect(url_for("volunteer_dashboard"))
        flash("Доброволецът не е намерен.", "error")
        session.pop("pending_volunteer_login", None)
        return redirect(url_for("volunteer_login"))

    # DEBUG: Print the code to console
    print(f"DEBUG: Volunteer verification code is: {pending.get('access_code')}")

    error = None
    if request.method == "POST":
        entered_code = request.form.get("code", "").strip()

        # TEMPORARY: Allow test code for development
        if entered_code == "test123":
            # Test code accepted, complete login
            volunteer = _load_volunteer_by_id(pending["volunteer_id"])
            if volunteer:
                _activate_volunteer_session(volunteer)
                session.pop("pending_volunteer_login", None)
                app.logger.info(f"Volunteer {volunteer.name} logged in with test code")
                return redirect(url_for("volunteer_dashboard"))
            error = "Доброволецът не е намерен."
            session.pop("pending_volunteer_login", None)
        elif entered_code == pending.get("access_code"):
            # Code is correct, complete login
            volunteer = _load_volunteer_by_id(pending["volunteer_id"])
            if volunteer:
                _activate_volunteer_session(volunteer)
                session.pop("pending_volunteer_login", None)
                app.logger.info(f"Volunteer {volunteer.name} logged in successfully")
                return redirect(url_for("volunteer_dashboard"))
            else:
                error = "Доброволецът не е намерен."
                session.pop("pending_volunteer_login", None)
        else:
            error = "Невалиден код за достъп."

    return render_template("volunteer_verify_code.html", error=error)


@app.route("/volunteer_logout")
def volunteer_logout():
    """Logout volunteer and clear session"""
    session.pop("volunteer_logged_in", None)
    session.pop("volunteer_id", None)
    session.pop("volunteer_name", None)
    flash("Излязохте успешно от системата.", "info")
    return redirect(url_for("index"))


@app.route("/resend_volunteer_code", methods=["POST"])
def resend_volunteer_code():
    db = get_db()
    """Resend verification code to volunteer email"""
    try:
        # Check if there's a pending login
        pending = session.get("pending_volunteer_login")
        if not pending:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Няма чакащ процес на вход. Моля, започнете отново.",
                    }
                ),
                400,
            )

        pending_email = (pending.get("email") or "").lower()

        if DISABLE_VOLUNTEER_OTP or pending_email in VOLUNTEER_OTP_BYPASS_EMAILS:
            return (
                jsonify(
                    {
                        "success": True,
                        "message": "В тази среда не се изисква код за достъп.",
                    }
                ),
                200,
            )

        # Check if code has expired
        if datetime.now().timestamp() > pending.get("expires", 0):
            session.pop("pending_volunteer_login", None)
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Кодът за достъп е изтекъл. Моля, опитайте отново.",
                    }
                ),
                400,
            )

        # Get volunteer
        volunteer = _load_volunteer_by_id(pending["volunteer_id"])
        if not volunteer:
            return (
                jsonify({"success": False, "message": "Доброволецът не е намерен"}),
                404,
            )

        # Generate new access code
        access_code = str(secrets.randbelow(900000) + 100000)

        # Update session with new code and extended expiration
        session["pending_volunteer_login"]["access_code"] = access_code
        session["pending_volunteer_login"]["expires"] = (
            datetime.now().timestamp() + 900
        )  # 15 minutes

        # Send email with new access code
        try:
            email_body = f"""Здравейте {volunteer.name},

Получен е нов опит за вход в доброволческия панел на HelpChain.

Вашият нов код за достъп: {access_code}

Кодът е валиден за 15 минути.

Ако това не сте вие, моля игнорирайте това съобщение.

С уважение,
HelpChain системата
"""

            _dispatch_email(
                subject="HelpChain - Нов код за достъп",
                recipients=[volunteer.email],
                body=email_body,
            )

            return jsonify(
                {"success": True, "message": "Нов код е изпратен на вашия имейл."}
            )

        except Exception as e:
            app.logger.error(f"Error resending volunteer code: {e}")
            try:
                with open("sent_emails.txt", "a", encoding="utf-8") as f:
                    f.write(
                        "Subject: HelpChain - Нов код за достъп\n"
                        f"To: {volunteer.email}\nFrom: {app.config['MAIL_DEFAULT_SENDER']}\n\n"
                        f"Здравейте {volunteer.name},\n\n"
                        "Получен е нов опит за вход в доброволческия панел на HelpChain.\n\n"
                        f"Вашият нов код за достъп: {access_code}\n\n"
                        "Кодът е валиден за 15 минути.\n\n"
                        "Ако това не сте вие, моля игнорирайте това съобщение.\n\n"
                        "С уважение,\nHelpChain системата\n\n"
                        f"{'=' * 50}\n"
                    )
                app.logger.info(
                    "New access code saved to file as fallback after failure"
                )
                return jsonify(
                    {
                        "success": True,
                        "message": "Кодът е записан локално (sent_emails.txt).",
                    }
                )
            except Exception as file_e:
                app.logger.error(f"Failed to save email to file: {file_e}")
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Възникна грешка при изпращане на кода.",
                        }
                    ),
                    500,
                )

    except Exception as e:
        app.logger.error(f"Unexpected error in resend_volunteer_code: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Възникна системна грешка. Моля, опитайте отново.",
                }
            ),
            500,
        )


@app.route("/volunteer_dashboard")
def volunteer_dashboard():
    """Enhanced volunteer dashboard with performance optimizations and better error handling"""
    try:
        app.logger.info("Starting volunteer_dashboard function")

        # Check authentication with detailed logging
        if not session.get("volunteer_logged_in"):
            app.logger.warning("Unauthorized access attempt to volunteer dashboard")
            flash("Моля, влезте като доброволец.", "warning")
            return redirect(url_for("volunteer_login"))

        volunteer_id = session.get("volunteer_id")
        if not volunteer_id:
            app.logger.warning("Missing volunteer_id in session")
            session.clear()
            flash("Сесията е изтекла. Моля, влезте отново.", "error")
            return redirect(url_for("volunteer_login"))

        volunteer = _load_volunteer_by_id(volunteer_id)

        if not volunteer:
            app.logger.warning(f"Volunteer with ID {volunteer_id} not found")
            session.clear()
            flash("Доброволецът не е намерен", "error")
            return redirect(url_for("volunteer_login"))

        app.logger.info(f"Volunteer found: {volunteer.name} (id: {volunteer.id})")

        # Get statistics with safe database operations
        stats = _get_volunteer_stats_safe(volunteer_id)
        active_tasks = _get_active_tasks_safe(volunteer_id)
        gamification = _get_gamification_data_safe(volunteer)
        available_tasks_count = _get_available_task_count()

        # Count urgent tasks nearby (simplified - all urgent pending requests)
        try:
            urgent_tasks_raw = (
                db.session.query(db.func.count(HelpRequest.id))
                .filter(
                    HelpRequest.status == "pending", HelpRequest.priority == "urgent"
                )
                .scalar()
            )
        except Exception as exc:
            app.logger.debug("Urgent task lookup failed: %s", exc)
            urgent_tasks_raw = 0

        urgent_tasks = _coerce_to_int(urgent_tasks_raw)

        app.logger.info("Rendering template with volunteer data")
        return render_template(
            "volunteer_dashboard.html",
            current_user=volunteer,
            stats=stats,
            active_tasks=active_tasks,
            gamification=gamification,
            available_tasks=available_tasks_count,
            urgent_tasks=urgent_tasks,
        )

    except Exception as e:
        db.session.rollback()
        app.logger.error(
            f"Critical error in volunteer dashboard: {e}", exc_info=app.debug
        )
        flash(
            "Възникна грешка при зареждането на панела. Моля, опитайте отново.", "error"
        )
        return redirect(url_for("index"))


def _require_volunteer_session():
    """Ensure the current request has an authenticated volunteer session."""
    if not session.get("volunteer_logged_in"):
        flash("Моля, влезте като доброволец.", "warning")
        return None, redirect(url_for("volunteer_login"))

    volunteer_id = session.get("volunteer_id")
    try:
        volunteer_id = int(volunteer_id)
    except (TypeError, ValueError):
        session.clear()
        flash("Сесията е изтекла. Моля, влезте отново.", "error")
        return None, redirect(url_for("volunteer_login"))

    return volunteer_id, None


def _load_volunteer_by_id(volunteer_id):
    """Fetch volunteer by ID using both SQLAlchemy 2.x and legacy patterns."""
    volunteer = None

    try:
        volunteer = db.session.get(Volunteer, volunteer_id)
    except Exception as exc:  # pragma: no cover - defensive for older SQLAlchemy
        app.logger.debug("db.session.get unavailable: %s", exc)

    if volunteer is None:
        query_attr = getattr(Volunteer, "query", None)

        if isinstance(query_attr, Mock):
            try:
                volunteer = query_attr.get(volunteer_id)
            except Exception as exc:
                app.logger.debug("Volunteer mock lookup failed: %s", exc)
                volunteer = None
        elif query_attr is not None:
            try:
                stmt = select(Volunteer).where(Volunteer.id == volunteer_id)
                volunteer = db.session.execute(stmt).scalar_one_or_none()
            except Exception as exc:
                app.logger.warning("Volunteer lookup failed: %s", exc)
                volunteer = None

    if isinstance(volunteer, Mock):
        volunteer_id_attr = getattr(volunteer, "id", None)
        if isinstance(volunteer_id_attr, Mock) or volunteer_id_attr is None:
            return None
        return volunteer

    return volunteer


def _coerce_to_int(value, default=0):
    """Best-effort conversion of possibly mocked values to integers."""
    if isinstance(value, Mock):
        return default
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _resolve_volunteer_for_display(volunteer_id):
    """Return a volunteer object or a lightweight placeholder for templates."""
    volunteer = _load_volunteer_by_id(volunteer_id)
    if volunteer:
        return volunteer

    placeholder_name = session.get("volunteer_name") or f"Доброволец #{volunteer_id}"
    return SimpleNamespace(
        id=volunteer_id,
        name=placeholder_name,
        email=session.get("volunteer_email"),
        phone=session.get("volunteer_phone"),
        location=session.get("volunteer_location"),
        points=0,
        level=1,
        experience=0,
        total_tasks_completed=0,
        streak_days=0,
        rating=0.0,
        rating_count=0,
    )


def _get_available_tasks(limit=10):
    """Return a lightweight list of currently available volunteer tasks."""
    try:
        from models_with_analytics import Task

        query = (
            db.session.query(
                Task.id,
                Task.title,
                Task.description,
                Task.location_text,
                Task.priority,
                Task.created_at,
            )
            .filter(Task.status.in_(["open", "pending"]))
            .order_by(Task.created_at.desc())
            .limit(limit)
        )

        tasks = []
        for task in query:
            tasks.append(
                {
                    "id": getattr(task, "id", None),
                    "title": getattr(task, "title", ""),
                    "description": getattr(task, "description", ""),
                    "location": getattr(task, "location_text", ""),
                    "priority": getattr(task, "priority", "normal"),
                    "created_at": getattr(task, "created_at", None),
                }
            )
        return tasks
    except Exception as exc:
        app.logger.debug("Failed to load available tasks: %s", exc)
        return []


@app.route("/my_tasks")
def volunteer_my_tasks():
    """Display tasks currently assigned to the volunteer."""
    volunteer_id, redirect_response = _require_volunteer_session()
    if redirect_response:
        return redirect_response

    volunteer = _resolve_volunteer_for_display(volunteer_id)
    tasks = _get_active_tasks_safe(volunteer_id)
    return render_template(
        "my_tasks.html",
        volunteer=volunteer,
        active_tasks=tasks,
    )


@app.route("/available_tasks")
def volunteer_available_tasks():
    """Display currently available volunteer tasks."""
    volunteer_id, redirect_response = _require_volunteer_session()
    if redirect_response:
        return redirect_response

    volunteer = _resolve_volunteer_for_display(volunteer_id)
    tasks = _get_available_tasks()
    return render_template(
        "available_tasks.html",
        volunteer=volunteer,
        available_tasks=tasks,
    )


@app.route("/volunteer_profile", methods=["GET", "POST"])
def volunteer_profile():
    """Allow volunteers to view and update their profile."""
    volunteer_id, redirect_response = _require_volunteer_session()
    if redirect_response:
        return redirect_response

    volunteer = _resolve_volunteer_for_display(volunteer_id)

    if request.method == "POST":
        updated = False
        for field in ("name", "email", "phone", "location"):
            if field in request.form:
                value = request.form.get(field, "").strip()
                setattr(volunteer, field, value or None)
                updated = True

        if updated:
            try:
                db.session.commit()
                flash("Профилът е обновен успешно.", "success")
            except Exception as exc:
                db.session.rollback()
                app.logger.error("Failed to update volunteer profile: %s", exc)
                flash("Възникна грешка при обновяването на профила.", "error")
        else:
            flash("Няма подадени промени за запазване.", "info")

        return redirect(url_for("volunteer_profile"))

    return render_template("volunteer_profile.html", volunteer=volunteer)


@app.route("/volunteer_chat")
def volunteer_chat():
    """Protected chat area for volunteers."""
    volunteer_id, redirect_response = _require_volunteer_session()
    if redirect_response:
        return redirect_response

    volunteer = _resolve_volunteer_for_display(volunteer_id)

    return render_template("volunteer_chat.html", volunteer=volunteer)


@app.route("/volunteer_reports")
def volunteer_reports():
    """Show volunteer performance reports and statistics."""
    volunteer_id, redirect_response = _require_volunteer_session()
    if redirect_response:
        return redirect_response

    volunteer = _resolve_volunteer_for_display(volunteer_id)
    stats = _get_volunteer_stats_safe(volunteer_id)
    return render_template(
        "volunteer_reports.html",
        volunteer=volunteer,
        stats=stats,
    )


@app.route("/volunteer_settings", methods=["GET", "POST"])
def volunteer_settings():
    """Display and update volunteer preference settings."""
    volunteer_id, redirect_response = _require_volunteer_session()
    if redirect_response:
        return redirect_response

    volunteer = _resolve_volunteer_for_display(volunteer_id)

    default_settings = {
        "notification_email": True,
        "notification_sms": False,
        "language": "bg",
        "timezone": "Europe/Sofia",
    }
    current_settings = session.get("volunteer_settings", default_settings.copy())

    if request.method == "POST":
        updated_settings = current_settings.copy()
        updated_settings["notification_email"] = request.form.get(
            "notification_email"
        ) in {"1", "true", "on", "yes"}
        updated_settings["notification_sms"] = request.form.get("notification_sms") in {
            "1",
            "true",
            "on",
            "yes",
        }
        updated_settings["language"] = request.form.get(
            "language", current_settings.get("language", "bg")
        )
        updated_settings["timezone"] = request.form.get(
            "timezone", current_settings.get("timezone", "Europe/Sofia")
        )

        session["volunteer_settings"] = updated_settings
        session.modified = True
        flash("Настройките са обновени успешно.", "success")
        return redirect(url_for("volunteer_settings"))

    return render_template(
        "volunteer_settings.html",
        settings=current_settings,
        volunteer=volunteer,
    )


def _get_volunteer_stats_safe(volunteer_id):
    """Safely get volunteer statistics with fallback values"""
    try:
        from models_with_analytics import Task, TaskPerformance

        task_stats = (
            db.session.query(
                db.func.sum(case((Task.status == "completed", 1), else_=0)).label(
                    "completed"
                ),
                db.func.sum(
                    case(
                        (Task.status.in_(["assigned", "in_progress"]), 1),
                        else_=0,
                    )
                ).label("active"),
            )
            .filter(Task.assigned_to == volunteer_id)
            .first()
        )

        completed_tasks = int(task_stats.completed or 0) if task_stats else 0
        active_tasks_count = int(task_stats.active or 0) if task_stats else 0

        performance_stats = (
            db.session.query(
                db.func.avg(TaskPerformance.quality_rating).label("avg_rating"),
                db.func.count(TaskPerformance.id).label("reviews"),
            )
            .filter(TaskPerformance.volunteer_id == volunteer_id)
            .first()
        )

        avg_rating_result = performance_stats.avg_rating if performance_stats else None
        rating = round(avg_rating_result, 1) if avg_rating_result else 0.0
        reviews_count = int(performance_stats.reviews or 0) if performance_stats else 0

        # People helped count (same as completed tasks)
        people_helped = completed_tasks

        return {
            "completed_tasks": completed_tasks,
            "active_tasks": active_tasks_count,
            "rating": rating,
            "people_helped": people_helped,
            "reviews": reviews_count,
        }

    except Exception as e:
        app.logger.error(f"Error fetching volunteer stats for ID {volunteer_id}: {e}")
        return {
            "completed_tasks": 0,
            "active_tasks": 0,
            "rating": 0.0,
            "people_helped": 0,
            "reviews": 0,
        }


def _get_active_tasks_safe(volunteer_id):
    """Safely get active tasks for volunteer"""
    try:
        from models_with_analytics import Task

        active_tasks_query = (
            db.session.query(
                Task.id,
                Task.title,
                Task.location_text,
                Task.created_at,
                Task.deadline,
                Task.description,
                Task.priority,
                Task.status,
            )
            .filter(Task.assigned_to == volunteer_id)
            .filter(Task.status.in_(["assigned", "in_progress"]))
            .order_by(Task.created_at.desc())
            .limit(5)
        )

        active_tasks = []
        for (
            task_id,
            title,
            location_text,
            created_at,
            deadline,
            description,
            priority,
            status,
        ) in active_tasks_query:
            progress = 10 if status == "assigned" else 50

            time_remaining = "Няма краен срок"
            if deadline:
                try:
                    now = _utcnow()
                    if deadline > now:
                        days_remaining = (deadline - now).days
                        if days_remaining == 0:
                            time_remaining = "Днес"
                        elif days_remaining == 1:
                            time_remaining = "1 ден"
                        elif days_remaining < 7:
                            time_remaining = f"{days_remaining} дни"
                        else:
                            time_remaining = f"{days_remaining // 7} седмици"
                    else:
                        time_remaining = "Просрочена"
                except Exception:
                    time_remaining = "Невалидна дата"

            active_tasks.append(
                {
                    "id": task_id,
                    "title": title,
                    "location": location_text or "Не е посочена локация",
                    "date": (
                        created_at.strftime("%Y-%m-%d") if created_at else "Няма дата"
                    ),
                    "time_remaining": time_remaining,
                    "description": description or "Няма описание",
                    "priority": priority or "medium",
                    "progress": progress,
                }
            )

        return active_tasks

    except Exception as e:
        app.logger.error(
            f"Error fetching active tasks for volunteer {volunteer_id}: {e}"
        )
        return []


def _get_gamification_data_safe(volunteer):
    """Safely get gamification data"""
    try:
        return {
            "points": volunteer.points,
            "level": volunteer.level,
            "experience": volunteer.experience,
            "level_progress": (
                volunteer.get_level_progress()
                if hasattr(volunteer, "get_level_progress")
                else 0
            ),
            "next_level_exp": (
                (volunteer.level * 100) if hasattr(volunteer, "level") else 100
            ),
        }
    except Exception as e:
        app.logger.error(
            f"Error getting gamification data for volunteer {volunteer.id}: {e}"
        )
        return {
            "points": 0,
            "level": 1,
            "experience": 0,
            "level_progress": 0,
            "next_level_exp": 100,
        }


def _get_available_task_count():
    """Return count of currently available (open) tasks."""
    try:
        return (
            db.session.query(db.func.count(Task.id))
            .filter(Task.status == "open")
            .scalar()
            or 0
        )
    except Exception as exc:
        app.logger.warning("Error counting available tasks: %s", exc)
        return 0


def _haversine_distance_km(lat1, lon1, lat2, lon2):
    """Calculate the distance in kilometers between two lat/lon pairs."""
    radius_km = 6371.0

    phi1, phi2 = radians(lat1), radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)

    a = sin(delta_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return radius_km * c


@app.route("/chatbot", methods=["GET"])
def chatbot():
    """AI Chatbot interface for users"""
    return render_template("chatbot.html")


@app.route("/api/volunteer/dashboard", methods=["GET"])
def api_volunteer_dashboard():
    db = get_db()
    """API endpoint for volunteer dashboard data"""
    if not session.get("volunteer_logged_in"):
        return jsonify({"error": "Authentication required"}), 401

    try:
        volunteer_id = session.get("volunteer_id")
        volunteer = db.session.query(Volunteer).get(volunteer_id)

        if not volunteer:
            return jsonify({"error": "Volunteer not found"}), 404

        # Get basic stats
        stats = {
            "points": volunteer.points,
            "level": volunteer.level,
            "experience": volunteer.experience,
            "total_tasks_completed": volunteer.total_tasks_completed,
            "streak_days": volunteer.streak_days,
        }

        # Get recent achievements (placeholder)
        recent_achievements = []

        # Get active tasks (placeholder)
        active_tasks = []

        return jsonify(
            {
                "volunteer": {
                    "id": volunteer.id,
                    "name": volunteer.name,
                    "email": volunteer.email,
                    "phone": volunteer.phone,
                },
                "stats": stats,
                "recent_achievements": recent_achievements,
                "active_tasks": active_tasks,
            }
        )

    except Exception as e:
        app.logger.error(f"Error getting volunteer dashboard: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/volunteers/nearby", methods=["GET"])
def api_volunteers_nearby():
    """Return volunteers near a geographic point within a given radius."""
    try:
        latitude = float(request.args.get("lat"))
        longitude = float(request.args.get("lng"))
        radius_km = float(request.args.get("radius", 25))
        if radius_km <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid location parameters"}), 400

    try:
        volunteers_query = (
            db.session.query(
                Volunteer.id,
                Volunteer.name,
                Volunteer.email,
                Volunteer.phone,
                Volunteer.skills,
                Volunteer.location,
                Volunteer.latitude,
                Volunteer.longitude,
            )
            .filter(Volunteer.latitude.isnot(None))
            .filter(Volunteer.longitude.isnot(None))
            .filter(Volunteer.is_active.is_(True))
            .limit(200)
        )

        results = []
        for volunteer in volunteers_query:
            try:
                candidate_lat = float(getattr(volunteer, "latitude", 0))
                candidate_lng = float(getattr(volunteer, "longitude", 0))
            except (TypeError, ValueError):
                continue

            distance = _haversine_distance_km(
                latitude,
                longitude,
                candidate_lat,
                candidate_lng,
            )

            if distance <= radius_km:
                results.append(
                    {
                        "id": getattr(volunteer, "id", None),
                        "name": getattr(volunteer, "name", ""),
                        "email": getattr(volunteer, "email", None),
                        "phone": getattr(volunteer, "phone", None),
                        "skills": getattr(volunteer, "skills", None),
                        "location": getattr(volunteer, "location", None),
                        "latitude": candidate_lat,
                        "longitude": candidate_lng,
                        "distance_km": round(distance, 2),
                    }
                )

        results.sort(key=lambda item: item["distance_km"])

        return jsonify(
            {
                "volunteers": results,
                "count": len(results),
                "radius_km": radius_km,
                "search_location": request.args.get(
                    "location", f"{latitude:.4f}, {longitude:.4f}"
                ),
            }
        )
    except Exception as exc:
        app.logger.error("Failed to fetch nearby volunteers: %s", exc)
        return jsonify({"error": "Unable to load volunteer data"}), 500


@app.route("/api/volunteers/<int:volunteer_id>/location", methods=["PUT"])
def api_update_volunteer_location(volunteer_id):
    """Update stored geolocation for a volunteer."""
    payload = request.get_json(silent=True) or {}
    latitude = payload.get("latitude")
    longitude = payload.get("longitude")

    if latitude is None or longitude is None:
        return jsonify({"error": "Latitude and longitude are required"}), 400

    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid latitude or longitude"}), 400

    location_text = payload.get("location")

    volunteer = _load_volunteer_by_id(volunteer_id)
    if not volunteer:
        return jsonify({"error": "Volunteer not found"}), 404

    volunteer.latitude = latitude
    volunteer.longitude = longitude
    if location_text is not None:
        volunteer.location = location_text.strip() or None
    volunteer.updated_at = _utcnow()

    try:
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        app.logger.error("Failed to update volunteer location: %s", exc)
        return jsonify({"error": "Database error"}), 500

    return jsonify(
        {
            "success": True,
            "volunteer_id": volunteer.id,
            "location": {
                "lat": volunteer.latitude,
                "lng": volunteer.longitude,
                "text": volunteer.location,
            },
            "updated_at": (
                volunteer.updated_at.isoformat() if volunteer.updated_at else None
            ),
        }
    )


@app.route("/api/admin/dashboard", methods=["GET"])
@require_admin_login
def api_admin_dashboard():
    """API endpoint for admin dashboard that intentionally returns a 500 error for testing security improvements"""
    # This endpoint intentionally raises an exception to test error handling
    # and security improvements related to API error responses
    raise Exception("Intentional server error for testing security improvements")


@app.route("/api/chatbot/message", methods=["POST"])
def chatbot_message():
    """Handle chatbot messages with AI responses"""
    try:
        data = request.get_json()
        user_message = data.get("message", "").strip()
        session_id = data.get("session_id", "default")

        if not user_message:
            return jsonify({"error": "No message provided"}), 400

        if ai_service is None:
            app.logger.error(
                "AI service is not configured; cannot process chatbot message"
            )
            return (
                jsonify(
                    {
                        "response": "AI услугата не е налична в момента. Моля, опитайте по-късно.",
                        "error": True,
                    }
                ),
                503,
            )

        # Generate AI response (synchronously)
        ai_response = ai_service.generate_response_sync(user_message)

        # Track conversation for analytics
        try:
            from analytics_service import analytics_service

            analytics_service.track_event(
                event_type="chatbot_interaction",
                event_category="engagement",
                event_action="message_sent",
                context={
                    "session_id": session_id,
                    "message_length": len(user_message),
                    "ai_provider": ai_response.get("provider", "unknown"),
                    "ai_confidence": ai_response.get("confidence", 0),
                    "response_length": len(ai_response.get("response", "")),
                },
            )
        except Exception as analytics_error:
            app.logger.warning(f"Analytics tracking failed: {analytics_error}")

        return jsonify(
            {
                "response": ai_response["response"],
                "confidence": ai_response["confidence"],
                "provider": ai_response["provider"],
                "session_id": session_id,
            }
        )

    except BadRequest:
        # Handle invalid JSON input
        return jsonify({"error": "Invalid JSON format"}), 400
    except Exception as e:
        app.logger.error(f"Chatbot error: {e}")
        return (
            jsonify(
                {
                    "response": "Извинявам се, възникна грешка. Моля, опитайте пак или "
                    "се свържете с екипа ни.",
                    "error": True,
                }
            ),
            500,
        )


@app.route("/api/ai/status", methods=["GET"])
def api_ai_status():
    """Get AI service status"""
    try:
        # Return basic status info for API compatibility
        return jsonify(
            {
                "status": "healthy",
                "providers": ["openai", "gemini"],
                "active_provider": "openai",
            }
        )
    except Exception as e:
        app.logger.error(f"Error getting AI status: {e}")
        return (
            jsonify({"status": "error", "providers": [], "active_provider": "none"}),
            500,
        )


print("DEBUG: About to define /api route")  # Debug print before route definition


@app.route("/api", methods=["GET"])
def api_health_check():
    """Basic API health check endpoint"""
    try:
        print("DEBUG: api_health_check function called")  # Debug print
        response = jsonify(
            {
                "status": "healthy",
                "service": "HelpChain API",
                "version": "1.0",
                "timestamp": _utcnow().isoformat(),
            }
        )
        print(f"DEBUG: Response created: {response}")  # Debug print
        return response
    except Exception as e:
        print(f"DEBUG: Exception in api_health_check: {e}")  # Debug print
        return "Internal server error", 500


print("DEBUG: /api route registered")  # Debug print after route definition


@app.route("/api/volunteer/tasks", methods=["GET"])
def api_volunteer_tasks():
    db = get_db()
    """Get tasks for logged in volunteer"""
    if not session.get("volunteer_logged_in"):
        return jsonify({"error": "Authentication required"}), 401

    try:
        volunteer_id = session.get("volunteer_id")

        # Get assigned tasks
        assigned_tasks = (
            db.session.query(Task)
            .filter_by(assigned_to=volunteer_id)
            .filter(Task.status.in_(["assigned", "in_progress"]))
            .order_by(Task.created_at.desc())
            .all()
        )

        # Get available tasks (not assigned to anyone)
        available_tasks = (
            db.session.query(Task)
            .filter_by(assigned_to=None)
            .filter_by(status="open")
            .order_by(Task.created_at.desc())
            .limit(10)  # Limit to prevent overwhelming the volunteer
            .all()
        )

        def format_task(task):
            return {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "category": task.category,
                "priority": task.priority,
                "status": task.status,
                "location_required": task.location_required,
                "location_text": task.location_text,
                "estimated_hours": task.estimated_hours,
                "deadline": task.deadline.isoformat() if task.deadline else None,
                "created_at": task.created_at.isoformat(),
                "assigned_at": (
                    task.assigned_at.isoformat() if task.assigned_at else None
                ),
            }

        return jsonify(
            {
                "assigned_tasks": [format_task(task) for task in assigned_tasks],
                "available_tasks": [format_task(task) for task in available_tasks],
            }
        )

    except Exception as e:
        app.logger.error(f"Error getting volunteer tasks: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/admin_volunteers/edit/<int:id>", methods=["GET", "POST"])
@require_admin_login
def edit_volunteer(id):
    db = get_db()
    volunteer = db.session.query(Volunteer).get_or_404(id)
    if request.method == "POST":
        volunteer.name = request.form["name"]
        volunteer.email = request.form["email"]
        volunteer.phone = request.form["phone"]
        volunteer.location = request.form["location"]  # Добави и локацията тук
        db.session.commit()
        flash("Промените са запазени!", "success")
        return redirect(url_for("admin_volunteers"))
    return render_template("edit_volunteer.html", volunteer=volunteer)


@app.route("/admin_volunteers/<int:volunteer_id>/delete", methods=["POST"])
@require_admin_login
def admin_delete_volunteer(volunteer_id):
    db = get_db()
    """Delete a volunteer"""
    try:
        volunteer = db.session.query(Volunteer).get_or_404(volunteer_id)

        # Optional: Check if volunteer can be deleted (not assigned to active tasks, etc.)
        # Check if volunteer has active tasks
        active_tasks = (
            db.session.query(Task)
            .filter_by(assigned_to=volunteer_id)
            .filter(Task.status.in_(["assigned", "in_progress"]))
            .count()
        )

        if active_tasks > 0:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"Не може да изтриете доброволец с {active_tasks} активни задачи",
                    }
                ),
                400,
            )

        db.session.delete(volunteer)
        db.session.commit()

        # Track analytics
        try:
            from analytics_service import analytics_service

            analytics_service.track_event(
                event_type="volunteer_action",
                event_category="admin",
                event_action="delete_volunteer",
                context={"volunteer_id": volunteer_id},
            )
        except Exception as analytics_error:
            app.logger.warning(f"Analytics tracking failed: {analytics_error}")

        return jsonify({"success": True, "message": "Доброволецът е изтрит успешно"})

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting volunteer {volunteer_id}: {e}")
        return (
            jsonify(
                {"success": False, "message": "Грешка при изтриване на доброволеца"}
            ),
            500,
        )


@app.route("/admin_tasks", methods=["GET"])
@require_admin_login
def admin_tasks():
    db = get_db()
    """Admin interface for managing tasks"""
    try:
        # Get filter parameters
        status_filter = request.args.get("status", "all")
        category_filter = request.args.get("category", "all")
        page = int(request.args.get("page", 1))
        per_page = 20

        # Build query
        query = db.session.query(Task)

        if status_filter != "all":
            query = query.filter_by(status=status_filter)

        if category_filter != "all":
            query = query.filter_by(category=category_filter)

        # Get total count for pagination
        total_tasks = query.count()

        # Apply pagination and ordering
        tasks = (
            query.order_by(Task.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        total_pages = (total_tasks + per_page - 1) // per_page

        # Get current admin user
        current_user = None
        if session.get("admin_user_id"):
            current_user = db.session.get(AdminUser, session.get("admin_user_id"))

        # Get task statistics
        stats = {
            "total_tasks": db.session.query(Task).count(),
            "open_tasks": db.session.query(Task).filter_by(status="open").count(),
            "assigned_tasks": db.session.query(Task)
            .filter_by(status="assigned")
            .count(),
            "in_progress_tasks": db.session.query(Task)
            .filter(Task.status == "in_progress")
            .count(),
            "completed_tasks": db.session.query(Task)
            .filter_by(status="completed")
            .count(),
        }

        return render_template(
            "admin_tasks.html",
            tasks=tasks,
            current_user=current_user,
            stats=stats,
            status_filter=status_filter,
            category_filter=category_filter,
            page=page,
            total_pages=total_pages,
            total_tasks=total_tasks,
        )

    except Exception as e:
        app.logger.error(f"Error loading admin tasks: {e}")
        flash("Възникна грешка при зареждането на задачите", "error")
        return redirect(url_for("admin_dashboard"))


@app.route("/admin_tasks/create", methods=["GET", "POST"])
@require_admin_login
def create_task():
    db = get_db()
    """Create a new task"""
    if request.method == "POST":
        try:
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            category = request.form.get("category", "").strip()
            priority = request.form.get("priority", "medium")
            location_required = request.form.get("location_required") == "on"
            location_text = (
                request.form.get("location_text", "").strip()
                if location_required
                else None
            )
            estimated_hours = request.form.get("estimated_hours")
            deadline_str = request.form.get("deadline", "").strip()

            # Validation
            if not title or not description or not category:
                flash("Моля, попълнете всички задължителни полета", "error")
                return redirect(url_for("create_task"))

            # Parse deadline
            deadline = None
            if deadline_str:
                try:
                    from datetime import datetime

                    deadline = datetime.strptime(deadline_str, "%Y-%m-%dT%H:%M")
                except ValueError:
                    flash("Невалиден формат на краен срок", "error")
                    return redirect(url_for("create_task"))

            # Parse estimated hours
            estimated_hours_int = None
            if estimated_hours:
                try:
                    estimated_hours_int = int(estimated_hours)
                    if estimated_hours_int <= 0:
                        raise ValueError
                except ValueError:
                    flash("Невалиден брой часове", "error")
                    return redirect(url_for("create_task"))

            # Create task
            task = Task(
                title=title,
                description=description,
                category=category,
                priority=priority,
                location_required=location_required,
                location_text=location_text,
                estimated_hours=estimated_hours_int,
                deadline=deadline,
                created_by=session.get("admin_user_id"),
            )

            db.session.add(task)
            db.session.commit()

            flash("Задачата е създадена успешно!", "success")
            return redirect(url_for("admin_tasks"))

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error creating task: {e}")
            flash("Грешка при създаване на задачата", "error")
            return redirect(url_for("create_task"))

    # Get current admin user
    current_user = None
    if session.get("admin_user_id"):
        current_user = db.session.get(AdminUser, session.get("admin_user_id"))

    return render_template("create_task.html", current_user=current_user)


@app.route("/admin_tasks/<int:task_id>/edit", methods=["GET", "POST"])
@require_admin_login
def edit_task(task_id):
    db = get_db()
    """Edit an existing task"""
    task = db.session.query(Task).get_or_404(task_id)

    if request.method == "POST":
        try:
            task.title = request.form.get("title", "").strip()
            task.description = request.form.get("description", "").strip()
            task.category = request.form.get("category", "").strip()
            task.priority = request.form.get("priority", "medium")
            task.location_required = request.form.get("location_required") == "on"
            task.location_text = (
                request.form.get("location_text", "").strip()
                if task.location_required
                else None
            )

            estimated_hours = request.form.get("estimated_hours")
            if estimated_hours:
                try:
                    task.estimated_hours = int(estimated_hours)
                    if task.estimated_hours <= 0:
                        raise ValueError
                except ValueError:
                    flash("Невалиден брой часове", "error")
                    return redirect(url_for("edit_task", task_id=task_id))
            else:
                task.estimated_hours = None

            deadline_str = request.form.get("deadline", "").strip()
            if deadline_str:
                try:
                    from datetime import datetime

                    task.deadline = datetime.strptime(deadline_str, "%Y-%m-%dT%H:%M")
                except ValueError:
                    flash("Невалиден формат на краен срок", "error")
                    return redirect(url_for("edit_task", task_id=task_id))
            else:
                task.deadline = None

            # Validation
            if not task.title or not task.description or not task.category:
                flash("Моля, попълнете всички задължителни полета", "error")
                return redirect(url_for("edit_task", task_id=task_id))

            db.session.commit()

            flash("Задачата е обновена успешно!", "success")
            return redirect(url_for("admin_tasks"))

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error updating task {task_id}: {e}")
            flash("Грешка при обновяване на задачата", "error")
            return redirect(url_for("edit_task", task_id=task_id))

    # Get current admin user
    current_user = None
    if session.get("admin_user_id"):
        current_user = db.session.get(AdminUser, session.get("admin_user_id"))

    return render_template("edit_task.html", task=task, current_user=current_user)


@app.route("/admin_tasks/<int:task_id>/delete", methods=["POST"])
@require_admin_login
def delete_task(task_id):
    db = get_db()
    """Delete a task"""
    try:
        task = db.session.query(Task).get_or_404(task_id)

        # Check if task is assigned
        if task.assigned_to:
            flash(
                "Не може да изтриете задача, която е присвоена на доброволец", "error"
            )
            return redirect(url_for("admin_tasks"))

        db.session.delete(task)
        db.session.commit()

        flash("Задачата е изтрита успешно!", "success")

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error deleting task {task_id}: {e}")
        flash("Грешка при изтриване на задачата", "error")

    return redirect(url_for("admin_tasks"))


@app.route("/admin_tasks/<int:task_id>/assign", methods=["GET", "POST"])
@require_admin_login
def assign_task(task_id):
    db = get_db()
    """Assign a task to a volunteer"""
    task = db.session.query(Task).get_or_404(task_id)

    if request.method == "POST":
        volunteer_id = request.form.get("volunteer_id")

        if not volunteer_id:
            flash("Моля, изберете доброволец", "error")
            return redirect(url_for("assign_task", task_id=task_id))

        try:
            volunteer = db.session.query(Volunteer).get(volunteer_id)
            if not volunteer:
                flash("Избраният доброволец не е намерен", "error")
                return redirect(url_for("assign_task", task_id=task_id))

            # Assign task to volunteer
            task.assigned_to = volunteer.id
            task.assigned_at = _utcnow()
            task.status = "assigned"

            # Create task assignment record
            assignment = TaskAssignment(
                task_id=task.id, volunteer_id=volunteer.id, assigned_by="volunteer"
            )
            db.session.add(assignment)

            db.session.commit()

            flash(f"Задачата е присвоена успешно на {volunteer.name}!", "success")
            return redirect(url_for("admin_tasks"))

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Error assigning task {task_id}: {e}")
            flash("Грешка при присвояване на задачата", "error")
            return redirect(url_for("assign_task", task_id=task_id))

    # Get available volunteers
    volunteers = db.session.query(Volunteer).filter_by(is_active=True).all()

    # Get current admin user
    current_user = None
    if session.get("admin_user_id"):
        current_user = db.session.get(AdminUser, session.get("admin_user_id"))

    return render_template(
        "assign_task.html", task=task, volunteers=volunteers, current_user=current_user
    )


@app.route("/admin_tasks/<int:task_id>/unassign", methods=["POST"])
@require_admin_login
def unassign_task(task_id):
    db = get_db()
    """Unassign a task from volunteer"""
    try:
        task = db.session.query(Task).get_or_404(task_id)

        if not task.assigned_to:
            flash("Задачата не е присвоена на никого", "warning")
            return redirect(url_for("admin_tasks"))

        # Update task
        task.assigned_to = None
        task.assigned_at = None
        task.status = "open"

        # Update assignment record
        assignment = (
            db.session.query(TaskAssignment)
            .filter_by(task_id=task_id, volunteer_id=task.assigned_to)
            .first()
        )
        if assignment:
            assignment.status = "cancelled"

        db.session.commit()

        flash("Задачата е освободена успешно!", "success")

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error unassigning task {task_id}: {e}")
        flash("Грешка при освобождаване на задачата", "error")

    return redirect(url_for("admin_tasks"))


@app.route("/admin_update_request_status", methods=["POST"])
@require_admin_login
def admin_update_request_status():
    db = get_db()
    """Update the status of a help request via AJAX"""
    try:
        data = request.get_json()
        request_id = data.get("request_id")
        new_status = data.get("status")

        if not request_id or not new_status:
            return (
                jsonify(
                    {"success": False, "message": "Липсват задължителни параметри"}
                ),
                400,
            )

        request_obj = db.session.query(HelpRequest).get(request_id)
        if not request_obj:
            return jsonify({"success": False, "message": "Заявката не е намерена"}), 404

        # Validate status
        valid_statuses = [
            "pending",
            "assigned",
            "in_progress",
            "completed",
            "cancelled",
        ]
        if new_status not in valid_statuses:
            return jsonify({"success": False, "message": "Невалиден статус"}), 400

        old_status = request_obj.status
        if new_status == "completed":
            request_obj.mark_completed()
        else:
            request_obj.status = new_status
            request_obj.completed_at = None
        db.session.commit()

        app.logger.info(
            f"Request {request_id} status changed from {old_status} to {new_status}"
        )

        return jsonify(
            {
                "success": True,
                "message": f"Статусът е обновен на '{new_status}'",
                "new_status": new_status,
            }
        )

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error updating request status: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Възникна грешка при обновяване на статуса",
                }
            ),
            500,
        )


@app.route("/export_volunteers")
@require_admin_login
def export_volunteers():
    export_format = request.args.get("format", "csv")
    search = request.args.get("search", "")
    location_filter = request.args.get("location", "")

    # Build query with same filters as admin_volunteers
    query = db.session.query(Volunteer)

    if search:
        query = query.filter(
            (Volunteer.name.ilike(f"%{search}%"))
            | (Volunteer.email.ilike(f"%{search}%"))
            | (Volunteer.phone.ilike(f"%{search}%"))
        )

    if location_filter:
        query = query.filter(Volunteer.location.ilike(f"%{location_filter}%"))

    volunteers = query.all()

    if export_format == "csv":
        return export_volunteers_csv(volunteers)
    elif export_format == "json":
        return export_volunteers_json(volunteers)
    elif export_format == "pdf":
        return export_volunteers_pdf(volunteers)
    else:
        return export_volunteers_csv(volunteers)


def export_volunteers_csv(volunteers):
    """Export volunteers to CSV format"""
    si = StringIO()
    cw = csv.writer(si)

    # Write header
    cw.writerow(
        [
            "ID",
            "Име",
            "Имейл",
            "Телефон",
            "Локация",
            "Умения",
            "Дата на регистрация",
            "Ширина",
            "Дължина",
        ]
    )

    # Write data
    for v in volunteers:
        cw.writerow(
            [
                v.id,
                v.name,
                v.email,
                v.phone,
                v.location or "",
                getattr(v, "skills", "") or "",
                v.created_at.strftime("%Y-%m-%d %H:%M:%S") if v.created_at else "",
                getattr(v, "latitude", "") or "",
                getattr(v, "longitude", "") or "",
            ]
        )

    output = si.getvalue()
    return Response(
        output,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment;filename=volunteers_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "Content-Type": "text/csv; charset=utf-8",
        },
    )


def export_volunteers_json(volunteers):
    """Export volunteers to JSON format"""
    volunteers_data = []
    for v in volunteers:
        volunteer_dict = {
            "id": v.id,
            "name": v.name,
            "email": v.email,
            "phone": v.phone,
            "location": v.location,
            "skills": getattr(v, "skills", ""),
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "latitude": getattr(v, "latitude", None),
            "longitude": getattr(v, "longitude", None),
        }
        volunteers_data.append(volunteer_dict)

    export_data = {
        "export_date": datetime.now().isoformat(),
        "total_volunteers": len(volunteers_data),
        "volunteers": volunteers_data,
    }

    return Response(
        json.dumps(export_data, ensure_ascii=False, indent=2),
        mimetype="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment;filename=volunteers_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "Content-Type": "application/json; charset=utf-8",
        },
    )


def export_volunteers_pdf(volunteers):
    """Export volunteers to PDF format"""
    try:
        colors_module = importlib.import_module("reportlab.lib.colors")
        pagesizes_module = importlib.import_module("reportlab.lib.pagesizes")
        styles_module = importlib.import_module("reportlab.lib.styles")
        units_module = importlib.import_module("reportlab.lib.units")
        platypus_module = importlib.import_module("reportlab.platypus")
    except ImportError:
        app.logger.warning("ReportLab not installed; falling back to CSV export")
        return export_volunteers_csv(volunteers)

    colors = colors_module
    A4 = pagesizes_module.A4
    ParagraphStyle = styles_module.ParagraphStyle
    getSampleStyleSheet = styles_module.getSampleStyleSheet
    inch = units_module.inch
    Paragraph = platypus_module.Paragraph
    SimpleDocTemplate = platypus_module.SimpleDocTemplate
    Spacer = platypus_module.Spacer
    Table = platypus_module.Table
    TableStyle = platypus_module.TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=30,
        alignment=1,  # Center alignment
    )

    # Title
    title = Paragraph("Списък с доброволци - HelpChain", title_style)
    elements.append(title)
    elements.append(Spacer(1, 12))

    # Export info
    info_text = (
        f"Общо доброволци: {len(volunteers)} | Експортирано на: "
        f"{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    )
    info_paragraph = Paragraph(info_text, styles["Normal"])
    elements.append(info_paragraph)
    elements.append(Spacer(1, 20))

    # Table data
    data = [["ID", "Име", "Имейл", "Телефон", "Локация", "Регистриран"]]

    for v in volunteers:
        data.append(
            [
                str(v.id),
                v.name,
                v.email,
                v.phone,
                v.location or "",
                v.created_at.strftime("%d.%m.%Y") if v.created_at else "",
            ]
        )

    # Create table
    table = Table(
        data,
        colWidths=[
            0.5 * inch,
            1.5 * inch,
            2 * inch,
            1.5 * inch,
            1.5 * inch,
            1 * inch,
        ],
    )

    # Table style
    table_style = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 12),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
            ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 10),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]
    )

    table.setStyle(table_style)
    elements.append(table)

    # Build PDF
    doc.build(elements)
    buffer.seek(0)

    return Response(
        buffer.getvalue(),
        mimetype="application/pdf",
        headers={
            "Content-Disposition": (
                f"attachment;filename=volunteers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            )
        },
    )


@app.route("/faq")
def faq():
    return render_template("faq.html")


@app.route("/success_stories")
def success_stories():
    return render_template("success_stories.html")


@app.route("/feedback", methods=["GET", "POST"])
@limiter.limit("3 per minute; 10 per hour")  # Rate limit feedback submissions
def feedback():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")

        # Basic input validation
        if not all([name, email, message]) or len(message) < 10:
            flash("Моля, попълнете всички полета коректно!")
            return redirect(url_for("feedback"))

        # Log feedback with security tags
        app.logger.info(
            "[SECURITY:FEEDBACK] Feedback received from %s <%s>: %s",
            name,
            email,
            message[:100] + "..." if len(message) > 100 else message,
        )
        flash("Благодарим за обратната връзка!")
        return redirect(url_for("feedback"))
    return render_template("feedback.html")


@app.route("/category_help/<category>")
def category_help(category):
    """Показва доброволци по категория помощ"""
    # Дефинираме категориите и техните описания
    categories = {
        "food": {
            "name": "Храна",
            "icon": "fas fa-utensils",
            "color": "success",
        },
        "medical": {
            "name": "Медицинска помощ",
            "icon": "fas fa-medkit",
            "color": "danger",
        },
        "transport": {
            "name": "Транспорт",
            "icon": "fas fa-car",
            "color": "info",
        },
        "other": {
            "name": "Друго",
            "icon": "fas fa-hands-helping",
            "color": "secondary",
        },
    }

    if category not in categories:
        flash("Категорията не е намерена!")
        return redirect(url_for("index"))

    # Филтрираме доброволци които имат тази категория в skills
    # Търсим case-insensitive в skills полето
    volunteers = (
        db.session.query(Volunteer)
        .filter(Volunteer.skills.ilike(f"%{category}%"))
        .all()
    )

    # Ако няма доброволци, показваме съобщение
    no_volunteers = len(volunteers) == 0

    # Проверяваме дали потребителят е администратор
    is_admin = session.get("admin_logged_in", False)

    category_display = categories[category]["name"]

    return render_template(
        "category_help.html",
        category=category,
        category_info=categories[category],
        volunteers=volunteers,
        is_admin=is_admin,
        category_display=category_display,
        no_volunteers=no_volunteers,
    )

    """Export volunteers to PDF format"""
    try:
        from io import BytesIO

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []

        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=16,
            spaceAfter=30,
            alignment=1,  # Center alignment
        )

        # Title
        title = Paragraph("Списък с доброволци - HelpChain", title_style)
        elements.append(title)
        elements.append(Spacer(1, 12))

        # Export info
        info_text = (
            f"Общо доброволци: {len(volunteers)} | Експортирано на: "
            f"{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
        )
        info_paragraph = Paragraph(info_text, styles["Normal"])
        elements.append(info_paragraph)
        elements.append(Spacer(1, 20))

        # Table data
        data = [["ID", "Име", "Имейл", "Телефон", "Локация", "Регистриран"]]

        for v in volunteers:
            data.append(
                [
                    str(v.id),
                    v.name,
                    v.email,
                    v.phone,
                    v.location or "",
                    v.created_at.strftime("%d.%m.%Y") if v.created_at else "",
                ]
            )

        # Create table
        table = Table(
            data,
            colWidths=[
                0.5 * inch,
                1.5 * inch,
                2 * inch,
                1.5 * inch,
                1.5 * inch,
                1 * inch,
            ],
        )

        # Table style
        table_style = TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 12),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 10),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]
        )

        table.setStyle(table_style)
        elements.append(table)

        # Build PDF
        doc.build(elements)
        buffer.seek(0)

        return Response(
            buffer.getvalue(),
            mimetype="application/pdf",
            headers={
                "Content-Disposition": (
                    f"attachment;filename=volunteers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                )
            },
        )

    except ImportError:
        return redirect(url_for("feedback"))
    return render_template("feedback.html")


def chat():
    """Main chat page - shows available chat rooms"""
    try:
        # Get public chat rooms
        public_rooms = (
            db.session.query(ChatRoom)
            .filter_by(room_type="public", is_active=True)
            .order_by(ChatRoom.created_at.desc())
            .all()
        )

        # Get user's private rooms if logged in
        private_rooms = []
        user_info = {}

        # Check if user is logged in (volunteer or admin)
        if session.get("volunteer_logged_in"):
            volunteer_id = session.get("volunteer_id")
            volunteer = db.session.query(Volunteer).get(volunteer_id)
            if volunteer:
                user_info = {
                    "type": "volunteer",
                    "id": volunteer.id,
                    "name": volunteer.name,
                }
                # Get rooms where volunteer is participant
                private_rooms = (
                    db.session.query(ChatRoom)
                    .join(ChatParticipant)
                    .filter(
                        ChatParticipant.volunteer_id == volunteer.id,
                        ChatRoom.room_type.in_(["private", "help_request"]),
                        ChatRoom.is_active,
                    )
                    .all()
                )
        elif session.get("user_id"):
            user = db.session.query(User).get(session.get("user_id"))
            if user:
                user_info = {"type": "admin", "id": user.id, "name": user.username}

        return render_template(
            "chat.html",
            public_rooms=public_rooms,
            private_rooms=private_rooms,
            user_info=user_info,
        )

    except Exception as e:
        app.logger.error(f"Error loading chat page: {e}")
        flash("Възникна грешка при зареждането на чата", "error")
        return redirect(url_for("index"))


@app.route("/chat/room/<int:room_id>")
def chat_room(room_id):
    """Chat room page"""
    try:
        room = db.session.query(ChatRoom).get_or_404(room_id)

        # Check permissions
        if room.room_type == "private":
            # Check if user has access to private room
            has_access = False
            if session.get("volunteer_logged_in"):
                volunteer_id = session.get("volunteer_id")
                participant = (
                    db.session.query(ChatParticipant)
                    .filter_by(room_id=room_id, volunteer_id=volunteer_id)
                    .first()
                )
                has_access = participant is not None
            elif session.get("user_id"):
                # Admin has access to all rooms
                has_access = True

            if not has_access:
                flash("Нямате достъп до тази стая", "error")
                return redirect(url_for("chat"))

        # Get user info
        user_info = {}
        if session.get("volunteer_logged_in"):
            volunteer = db.session.query(Volunteer).get(session.get("volunteer_id"))
            if volunteer:
                user_info = {
                    "type": "volunteer",
                    "id": volunteer.id,
                    "name": volunteer.name,
                }
        elif session.get("user_id"):
            user = db.session.query(User).get(session.get("user_id"))
            if user:
                user_info = {"type": "admin", "id": user.id, "name": user.username}
        else:
            # Allow anonymous access to public rooms
            if room.room_type == "public":
                user_info = {"type": "guest", "id": 0, "name": "Гост"}
            else:
                flash("Трябва да сте логнати за достъп до тази стая", "error")
                return redirect(url_for("chat"))

        return render_template("chat_room.html", room=room, user_info=user_info)

    except Exception as e:
        app.logger.error(f"Error loading chat room {room_id}: {e}")
        flash("Възникна грешка при зареждането на стаята", "error")
        return redirect(url_for("chat"))


@app.route("/api/chat/rooms", methods=["GET"])
def api_get_chat_rooms():
    """API endpoint to get available chat rooms"""
    try:
        room_type = request.args.get("type", "public")

        if room_type == "public":
            rooms = (
                db.session.query(ChatRoom)
                .filter_by(room_type="public", is_active=True)
                .order_by(ChatRoom.created_at.desc())
                .all()
            )
        else:
            # For private rooms, check user permissions
            rooms = []
            if session.get("volunteer_logged_in"):
                volunteer_id = session.get("volunteer_id")
                rooms = (
                    db.session.query(ChatRoom)
                    .join(ChatParticipant)
                    .filter(
                        ChatParticipant.volunteer_id == volunteer_id,
                        ChatRoom.room_type.in_(["private", "help_request"]),
                        ChatRoom.is_active,
                    )
                    .all()
                )
            elif session.get("user_id"):
                # Admin sees all rooms
                rooms = db.session.query(ChatRoom).filter_by(is_active=True).all()

        rooms_data = []
        for room in rooms:
            # Count online participants
            online_count = (
                db.session.query(ChatParticipant)
                .filter_by(room_id=room.id, is_online=True)
                .count()
            )

            rooms_data.append(
                {
                    "id": room.id,
                    "name": room.name,
                    "description": room.description,
                    "room_type": room.room_type,
                    "created_at": room.created_at.isoformat(),
                    "online_count": online_count,
                }
            )

        return jsonify({"rooms": rooms_data})

    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/chat/room/<int:room_id>/messages", methods=["GET"])
def api_get_room_messages(room_id):
    """API endpoint to get room messages"""
    try:
        # Check permissions
        room = db.session.query(ChatRoom).get(room_id)
        if not room:
            return jsonify({"error": "Room not found"}), 404

        if room.room_type == "private":
            has_access = False
            if session.get("volunteer_logged_in"):
                volunteer_id = session.get("volunteer_id")
                participant = (
                    db.session.query(ChatParticipant)
                    .filter_by(room_id=room_id, volunteer_id=volunteer_id)
                    .first()
                )
                has_access = participant is not None
            elif session.get("user_id"):
                has_access = True

            if not has_access:
                return jsonify({"error": "Access denied"}), 403

        # Get messages
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))

        messages = (
            db.session.query(ChatMessage)
            .filter_by(room_id=room_id, is_deleted=False)
            .order_by(ChatMessage.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        messages_data = []
        for msg in reversed(messages):
            messages_data.append(
                {
                    "id": msg.id,
                    "sender_name": msg.sender_name,
                    "sender_type": msg.sender_type,
                    "content": msg.content,
                    "message_type": msg.message_type,
                    "file_url": msg.file_url,
                    "file_name": msg.file_name,
                    "created_at": msg.created_at.isoformat(),
                    "reply_to": msg.reply_to_id,
                }
            )

        return jsonify({"messages": messages_data})

    except Exception as e:
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/chat/create_room", methods=["POST"])
def api_create_chat_room():
    """API endpoint to create a new chat room"""
    try:
        data = request.get_json()
        room_name = data.get("name", "").strip()
        room_type = data.get("type", "public")
        description = data.get("description", "").strip()

        if not room_name:
            return jsonify({"error": "Room name is required"}), 400

        # Check permissions for private rooms
        if room_type == "private" and not session.get("user_id"):
            return jsonify({"error": "Only admins can create private rooms"}), 403

        # Get creator info
        creator_id = None
        if session.get("user_id"):
            creator_id = session.get("user_id")

        # Create room
        room = ChatRoom(
            name=room_name,
            description=description,
            room_type=room_type,
            created_by=creator_id,
        )
        db.session.add(room)
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "room": {
                    "id": room.id,
                    "name": room.name,
                    "description": room.description,
                    "room_type": room.room_type,
                    "created_at": room.created_at.isoformat(),
                },
            }
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/chat/leave_room", methods=["POST"])
def api_leave_chat_room():
    """API endpoint to leave a chat room"""
    try:
        data = request.get_json()
        room_id = data.get("room_id")
        user_type = data.get("user_type")
        user_name = data.get("user_name")

        if not room_id or not user_type or not user_name:
            return jsonify({"error": "Invalid leave room data"}), 400

        # Update participant status
        participant = (
            db.session.query(ChatParticipant)
            .filter_by(
                room_id=room_id,
                participant_type=user_type,
                participant_name=user_name,
            )
            .first()
        )

        if participant:
            participant.is_online = False
            participant.last_seen = _utcnow()
            db.session.commit()

        # Leave SocketIO room
        leave_room(f"chat_{room_id}")

        return jsonify({"success": True, "message": "Successfully left the room"})

    except Exception as e:
        app.logger.error(f"Error leaving chat room: {e}")
        return jsonify({"error": "Failed to leave chat room"}), 500


@app.route("/api/user/profile", methods=["GET"])
def api_user_profile():
    """Get user profile for logged in users"""
    # Check if volunteer is logged in
    if session.get("volunteer_logged_in"):
        volunteer_id = session.get("volunteer_id")
        volunteer = db.session.query(Volunteer).get(volunteer_id)
        if volunteer:
            return jsonify(
                {
                    "user_type": "volunteer",
                    "id": volunteer.id,
                    "name": volunteer.name,
                    "email": volunteer.email,
                    "phone": volunteer.phone,
                    "location": volunteer.location,
                }
            )
        return jsonify({"error": "Volunteer not found"}), 404

    # Check if admin is logged in
    elif session.get("admin_logged_in"):
        admin_user = db.session.query(AdminUser).get(session.get("admin_user_id"))
        if admin_user:
            return jsonify(
                {
                    "user_type": "admin",
                    "id": admin_user.id,
                    "username": admin_user.username,
                    "email": admin_user.email,
                    "role": admin_user.role,
                }
            )
        return jsonify({"error": "Admin not found"}), 404

    # Not authenticated
    return jsonify({"error": "Authentication required"}), 401


@app.route("/accept_task/<int:task_id>", methods=["POST"])
def accept_task(task_id):
    """Volunteer accepts/requests assignment to a task"""
    if not session.get("volunteer_logged_in"):
        flash("Моля, влезте като доброволец.", "warning")
        return redirect(url_for("volunteer_login"))

    try:
        volunteer_id = session.get("volunteer_id")
        volunteer = db.session.query(Volunteer).get(volunteer_id)

        if not volunteer:
            flash("Доброволецът не е намерен.", "error")
            return redirect(url_for("available_tasks"))

        task = db.session.query(Task).get_or_404(task_id)

        # Check if task is still available
        if task.assigned_to is not None:
            flash("Задачата вече е присвоена на друг доброволец.", "warning")
            return redirect(url_for("available_tasks"))

        # Check if task is open
        if task.status != "open":
            flash("Задачата вече не е налична.", "warning")
            return redirect(url_for("available_tasks"))

        # Assign task to volunteer
        task.assigned_to = volunteer.id
        task.assigned_at = _utcnow()
        task.status = "assigned"

        # Create task assignment record
        assignment = TaskAssignment(
            task_id=task.id, volunteer_id=volunteer.id, assigned_by="volunteer"
        )
        db.session.add(assignment)

        db.session.commit()
        flash(f"Успешно се записахте за задачата '{task.title}'!", "success")
        return redirect(url_for("my_tasks"))

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error accepting task {task_id}: {e}")
        flash("Възникна грешка при записването за задачата.", "error")
        return redirect(url_for("available_tasks"))


@app.route("/cancel_task/<int:task_id>", methods=["POST"])
def cancel_task(task_id):
    """Volunteer cancels their task assignment"""
    if not session.get("volunteer_logged_in"):
        flash("Моля, влезте като доброволец.", "warning")
        return redirect(url_for("volunteer_login"))

    try:
        volunteer_id = session.get("volunteer_id")
        volunteer = db.session.query(Volunteer).get(volunteer_id)

        if not volunteer:
            flash("Доброволецът не е намерен.", "error")
            return redirect(url_for("my_tasks"))

        task = db.session.query(Task).get_or_404(task_id)

        # Check if task is assigned to this volunteer
        if task.assigned_to != volunteer.id:
            flash("Задачата не е присвоена на вас.", "error")
            return redirect(url_for("my_tasks"))

        # Check if task can be cancelled (not completed)
        if task.status == "completed":
            flash("Завършените задачи не могат да бъдат отказани.", "warning")
            return redirect(url_for("my_tasks"))

        # Update task
        task.assigned_to = None
        task.assigned_at = None
        task.status = "open"

        # Update assignment record
        assignment = (
            db.session.query(TaskAssignment)
            .filter_by(task_id=task_id, volunteer_id=volunteer.id)
            .first()
        )
        if assignment:
            assignment.status = "cancelled"

        db.session.commit()

        flash(f"Успешно се отказахте от задачата '{task.title}'.", "info")
        return redirect(url_for("my_tasks"))

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error cancelling task {task_id}: {e}")
        flash("Възникна грешка при отказването от задачата.", "error")
        return redirect(url_for("my_tasks"))


@app.route("/update_task_progress/<int:task_id>", methods=["POST"])
def update_task_progress(task_id):
    """Volunteer updates task progress/status"""
    if not session.get("volunteer_logged_in"):
        flash("Моля, влезте като доброволец.", "warning")
        return redirect(url_for("volunteer_login"))

    try:
        volunteer_id = session.get("volunteer_id")
        volunteer = db.session.query(Volunteer).get(volunteer_id)

        if not volunteer:
            flash("Доброволецът не е намерен.", "error")
            return redirect(url_for("my_tasks"))

        task = db.session.query(Task).get_or_404(task_id)

        # Check if task is assigned to this volunteer
        if task.assigned_to != volunteer.id:
            flash("Задачата не е присвоена на вас.", "error")
            return redirect(url_for("my_tasks"))

        new_status = request.form.get("status")
        progress_notes = request.form.get("progress_notes", "").strip()

        # Validate status
        valid_statuses = ["assigned", "in_progress", "completed"]
        if new_status not in valid_statuses:
            flash("Невалиден статус.", "error")
            return redirect(url_for("my_tasks"))

        # Update task
        old_status = task.status
        task.status = new_status

        if new_status == "completed":
            task.completed_at = _utcnow()
        elif new_status == "in_progress" and old_status == "assigned":
            # Task started
            pass

        # Create performance record
        performance = TaskPerformance(
            task_id=task.id,
            volunteer_id=volunteer.id,
            status_change=f"{old_status} -> {new_status}",
            notes=progress_notes,
            created_at=_utcnow(),
        )
        db.session.add(performance)

        db.session.commit()

        status_messages = {
            "assigned": "Задачата е маркирана като присвоена.",
            "in_progress": "Задачата е започната.",
            "completed": "Задачата е завършена успешно!",
        }

        flash(status_messages.get(new_status, "Статусът е обновен."), "success")
        return redirect(url_for("my_tasks"))

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error updating task progress {task_id}: {e}")
        flash("Възникна грешка при обновяването на прогреса.", "error")
        return redirect(url_for("my_tasks"))


@app.route("/admin_analytics", methods=["GET"])
@require_admin_login
def admin_analytics():
    """Advanced Analytics Dashboard с real-time графики и прогнози"""
    try:
        from admin_analytics import AnalyticsEngine

        try:
            from analytics_service import analytics_service
        except ImportError:  # pragma: no cover - optional dependency
            analytics_service = None

        def _parse_date(value: str | None) -> datetime | None:
            if not value:
                return None
            try:
                return datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                return None

        range_param = request.args.get("days")
        start_param = request.args.get("start_date")
        end_param = request.args.get("end_date")

        custom_start = _parse_date(start_param)
        custom_end = _parse_date(end_param)

        if custom_start and custom_end and custom_start > custom_end:
            custom_start, custom_end = custom_end, custom_start

        if custom_start and custom_end:
            period_days = max(1, (custom_end.date() - custom_start.date()).days + 1)
        else:
            try:
                period_days = int(range_param)
            except (TypeError, ValueError):
                period_days = 30

        period_days = max(1, min(period_days, 365))

        dashboard_stats = AnalyticsEngine.get_dashboard_stats(
            days=period_days, start_date=custom_start, end_date=custom_end
        )

        # Допълнителна аналитика от advanced services, ако е налична
        advanced_analytics = (
            analytics_service.get_dashboard_analytics(
                days=period_days, start_date=custom_start, end_date=custom_end
            )
            if analytics_service
            else {}
        )

        geo_data = AnalyticsEngine.get_geo_data()
        trends_data = AnalyticsEngine.get_trends_data(months=12)
        predictions = AnalyticsEngine.get_predictions(months=3)
        live_stats = dashboard_stats.get("real_time", {})

        raw_category_stats = dashboard_stats.get("category_stats", {}) or {}
        category_stats = {
            "categories": list(raw_category_stats.keys()),
            "counts": list(raw_category_stats.values()),
        }

        performance_metrics = dashboard_stats.get("performance_metrics", {})
        if not performance_metrics:
            performance_metrics = AnalyticsEngine.get_performance_metrics()

        return render_template(
            "admin_analytics_professional.html",
            dashboard_stats=dashboard_stats,
            geo_data=geo_data,
            trends_data=trends_data,
            predictions=predictions,
            live_stats=live_stats,
            category_stats=category_stats,
            performance_metrics=performance_metrics,
            advanced_analytics=advanced_analytics,
        )

    except Exception as e:
        app.logger.error(f"Error loading analytics dashboard: {e}")
        flash("Възникна грешка при зареждането на аналитиката", "error")
        return redirect(url_for("admin_dashboard"))


@app.route("/api/admin/dashboard", endpoint="api_admin_dashboard_error")
@require_admin_login
def api_admin_dashboard():
    """API endpoint for admin dashboard that intentionally returns a 500 error for testing security improvements"""
    # This endpoint intentionally raises an exception to test error handling
    # and security improvements related to API error responses
    raise Exception("Intentional server error for testing security improvements")


def health_check():
    """Basic health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": _utcnow().isoformat()})


@app.route("/readyz")
def readiness_check():
    """Readiness check endpoint - checks if app is ready to serve requests"""
    try:
        # Check database connectivity
        db.session.execute(db.text("SELECT 1"))
        return jsonify(
            {
                "status": "ready",
                "database": "connected",
                "timestamp": _utcnow().isoformat(),
            }
        )
    except Exception as e:
        app.logger.error(f"Readiness check failed: {e}")
        return (
            jsonify(
                {
                    "status": "not ready",
                    "database": "disconnected",
                    "error": str(e),
                    "timestamp": _utcnow().isoformat(),
                }
            ),
            503,
        )


@app.route("/achievements")
def achievements():
    """Volunteer achievements page"""
    if not session.get("volunteer_logged_in"):
        flash("Моля, влезте като доброволец.", "warning")
        return redirect(url_for("volunteer_login"))

    try:
        volunteer_id = session.get("volunteer_id")
        volunteer = _resolve_volunteer_for_display(volunteer_id)

        # Get achievements data
        achievements_data = {
            "points": volunteer.points,
            "level": volunteer.level,
            "experience": volunteer.experience,
            "total_tasks_completed": volunteer.total_tasks_completed,
            "streak_days": volunteer.streak_days,
            "rating": volunteer.rating,
            "rating_count": volunteer.rating_count,
        }

        # Get recent achievements (placeholder for now)
        recent_achievements = []

        return render_template(
            "achievements.html",
            volunteer=volunteer,
            achievements=achievements_data,
            recent_achievements=recent_achievements,
        )

    except Exception as e:
        app.logger.error(f"Error loading achievements page: {e}")
        flash("Възникна грешка при зареждането на постиженията.", "error")
        return redirect(url_for("volunteer_dashboard"))


@app.route("/favicon.ico")
def favicon():
    """Serve favicon"""
    return send_from_directory(
        app.static_folder, "hands-heart.png", mimetype="image/png"
    )


if __name__ == "__main__":
    print("HelpChain server starting...")
    print("http://0.0.0.0:5000")
    print("Admin: admin / Admin123")
    print("Press Ctrl+C to stop")
    debug_mode = False  # Disable debug mode for production
    host = os.getenv("HELPCHAIN_HOST", "0.0.0.0")
    port = int(os.getenv("HELPCHAIN_PORT", "5000"))

    try:
        # For testing purposes, let's try running with standard Flask first
        # to see if SocketIO is causing the routing issues
        if socketio is None:
            # Run with standard Flask (for testing routes)
            print("Starting with standard Flask (SocketIO disabled)...")
            print("About to call app.run()...")
            app.run(debug=debug_mode, host=host, port=port, use_reloader=False)
            print("app.run() completed")
        else:
            # Run with SocketIO (normal operation)
            async_mode = app.config.get("SOCKETIO_ASYNC_MODE", "threading")
            if async_mode != "gevent":
                app.logger.warning(
                    "SocketIO running without gevent; WebSocket upgrades will remain disabled."
                )

            print("Starting with SocketIO...")
            run_kwargs = {
                "debug": debug_mode,
                "host": host,
                "port": port,
                "use_reloader": False,
            }
            if async_mode != "gevent":
                run_kwargs["allow_unsafe_werkzeug"] = True

            socketio.run(app, **run_kwargs)
    except Exception as e:
        print(f"Server startup failed: {e}")
        import traceback

        traceback.print_exc()
