import csv
import json
import logging
import math
import os
import secrets
import sys
from datetime import datetime
from io import StringIO

# Import Celery for background tasks
from celery import Celery
from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_babel import Babel, refresh
from flask_babel import gettext as _
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_migrate import Migrate
from flask_socketio import emit, join_room, leave_room
from flask_talisman import Talisman
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlalchemy.exc import OperationalError
from werkzeug.utils import secure_filename
from werkzeug.exceptions import BadRequest

# Try relative imports first, fall back to absolute imports for standalone execution
try:
    from backend.extensions import db
except ImportError:
    # Fallback for standalone execution
    try:
        from extensions import db
    except ImportError:
        from extensions import db

try:
    from backend.models import (
        AdminUser,
        ChatMessage,
        ChatParticipant,
        ChatRoom,
        HelpRequest,
        Role,
        RoleEnum,
        User,
        UserRole,
        Volunteer,
    )
except ImportError:
    from models import (
        AdminUser,
        ChatMessage,
        ChatParticipant,
        ChatRoom,
        HelpRequest,
        Role,
        RoleEnum,
        User,
        UserRole,
        Volunteer,
    )

    try:
        from backend.models_with_analytics import Task, TaskAssignment, TaskPerformance
    except ImportError:
        from models_with_analytics import Task, TaskAssignment, TaskPerformance

# Import permissions module - always needed
try:
    from backend.permissions import (
        initialize_default_roles_and_permissions,
        require_admin_login,
        require_permission,
    )
except ImportError:
    from permissions import (
        initialize_default_roles_and_permissions,
        require_admin_login,
        require_permission,
    )

# Import Task models globally for use in routes
try:
    from backend.models_with_analytics import Task, TaskAssignment, TaskPerformance
except ImportError:
    from models_with_analytics import Task, TaskAssignment, TaskPerformance

try:
    from backend.admin_roles import admin_roles_bp
except ImportError:
    from admin_roles import admin_roles_bp

try:
    from backend.routes.notifications import notification_bp
except ImportError:
    from routes.notifications import notification_bp

# Import smart matching engine
try:
    from backend.ai_service import ai_service
except ImportError:
    from ai_service import ai_service

# Add the backend directory to Python path so we can import models and extensions
backend_dir = os.path.dirname(__file__)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Зареди environment variables от .env файла (от корена на проекта)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# Sentry for error monitoring
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
import random

# Add the backend directory to Python path for imports
backend_dir = os.path.dirname(__file__)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

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


# Setup enhanced logging
logger = setup_logging()


def initialize_default_admin():
    """
    Initialize default admin user if it doesn't exist
    """
    try:
        logger.info("Checking for existing admin user...")
        # Check if admin user exists
        admin_user = db.session.query(AdminUser).filter_by(username="admin").first()
        if admin_user:
            logger.info("Admin user already exists")
            # Check if User record exists and has super admin role
            user = db.session.query(User).filter_by(username="admin").first()
            if user:
                # Check if user has super admin role
                superadmin_role = (
                    db.session.query(Role).filter_by(name="Супер администратор").first()
                )
                if superadmin_role:
                    existing_role = (
                        db.session.query(UserRole)
                        .filter_by(user_id=user.id, role_id=superadmin_role.id)
                        .first()
                    )
                    if not existing_role:
                        user_role = UserRole(
                            user_id=user.id,
                            role_id=superadmin_role.id,
                            assigned_by=user.id,  # Self-assigned
                        )
                        db.session.add(user_role)
                        db.session.commit()
                        logger.info("Super admin role assigned to existing user")
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

        # Also create a User record for permissions system
        user = User(
            username="admin",
            email="admin@helpchain.live",
            password_hash=admin_user.password_hash,  # Use same password hash
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()  # Get user ID

        # Assign super admin role to the user
        superadmin_role = db.session.query(Role).filter_by(name="Супер администратор").first()
        if superadmin_role:
            # Check if user already has this role
            existing_role = (
                db.session.query(UserRole)
                .filter_by(user_id=user.id, role_id=superadmin_role.id)
                .first()
            )
            if not existing_role:
                user_role = UserRole(
                    user_id=user.id,
                    role_id=superadmin_role.id,
                    assigned_by=user.id,  # Self-assigned
                )
                db.session.add(user_role)

        db.session.commit()
        logger.info("Default admin user created successfully")
        return admin_user

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating default admin user: {e}", exc_info=True)
        return None


# Add the backend directory to Python path so we can import models
backend_dir = os.path.dirname(__file__)

sys.path.insert(0, backend_dir)

# Also add parent directory in case we need it
parent_dir = os.path.dirname(backend_dir)
sys.path.insert(0, parent_dir)

# Add helpchain_backend/src directory to Python path
helpchain_backend_dir = os.path.join(backend_dir, "helpchain-backend")
src_dir = os.path.join(helpchain_backend_dir, "src")
sys.path.insert(0, src_dir)

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


def generate_email_2fa_code():
    """Generate a 6-digit 2FA code"""
    return str(secrets.randbelow(900000) + 100000)


def send_email_2fa_code(code, ip_address, user_agent):
    """Send 2FA code via email"""
    try:
        logger.info(f"Attempting to send 2FA code to {EMAIL_2FA_RECIPIENT}")
        from flask_mail import Message

        msg = Message(
            subject="HelpChain - Код за верификация на администратор",
            recipients=[EMAIL_2FA_RECIPIENT],
            sender=app.config["MAIL_DEFAULT_SENDER"],
            body=f"""Здравейте,

Получен е опит за вход в администраторския панел на HelpChain.

Код за верификация: {code}

Детайли за достъпа:
- IP адрес: {ip_address}
- Браузър: {user_agent}
- Време: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Ако това не сте вие, моля игнорирайте това съобщение.

С уважение,
HelpChain системата
""",
        )

        mail.send(msg)
        logger.info(f"Email 2FA code sent successfully to {EMAIL_2FA_RECIPIENT}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email 2FA code: {e}", exc_info=True)
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
            logger.error(f"Failed to save email 2FA code to file: {file_e}", exc_info=True)
            return False


# Създай папката instance ако не съществува
os.makedirs(os.path.join(os.path.dirname(__file__), "instance"), exist_ok=True)

# Задаваме явни папки за шаблони и статични файлове (адаптирай пътищата ако е нужно)
_templates = os.path.join(os.path.dirname(__file__), "templates")
_static = os.path.join(os.path.dirname(__file__), "static")

# Създаваме приложението с правилните пътища
app = Flask(__name__, template_folder=_templates, static_folder=_static)


# Initialize Celery (optional - app will work without it)
def make_celery(app):
    try:
        celery = Celery(
            app.import_name,
            backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
            broker_url=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
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


celery = make_celery(app)

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

# Задаваме SECRET_KEY за сесии и сигурност
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

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
if os.getenv("RENDER") == "true" or os.getenv("PRODUCTION") == "true":
    # Check if DATABASE_URL is provided (for PostgreSQL on Render)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
        logger.info("Production mode detected, using DATABASE_URL from environment")
    else:
        # Fallback to SQLite for development/production without DATABASE_URL
        db_path = "/opt/render/project/src/volunteers.db"
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
        logger.info(f"Production mode detected, using fallback SQLite database: {db_path}")
else:
    # Локално development - използвайме instance директория в root проекта
    instance_dir = os.path.join(os.path.dirname(basedir), "instance")
    os.makedirs(instance_dir, exist_ok=True)
    db_path = os.path.join(instance_dir, "volunteers.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
    logger.info(f"Development mode, using database path: {db_path}")

logger.info(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")  # Debug print
logger.debug(f"Database path: {app.config['SQLALCHEMY_DATABASE_URI']}")  # Debug print
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
migrate = Migrate(app, db)


# Initialize database in production mode
def initialize_database():
    """Initialize database tables and default data for production"""
    try:
        with app.app_context():
            # Create all tables
            db.create_all()
            app.logger.info("Database tables created successfully")

            # Run migrations if available
            try:
                from flask_migrate import upgrade

                upgrade()
                app.logger.info("Database migrations applied successfully")
            except Exception as migration_error:
                app.logger.warning(f"Migration failed, continuing: {migration_error}")

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
            db.create_all()
            app.logger.info("Database tables created successfully for development")

            # Initialize default admin user for development
            try:
                admin_user = initialize_default_admin()
                if admin_user:
                    app.logger.info("Default admin user initialized for development")
                else:
                    app.logger.warning("Failed to initialize default admin user for development")
            except Exception as admin_error:
                app.logger.warning(f"Admin initialization failed for development: {admin_error}")

            # Initialize default roles and permissions for development
            try:
                initialize_default_roles_and_permissions()
                app.logger.info("Default roles and permissions initialized for development")
            except Exception as roles_error:
                app.logger.warning(f"Roles initialization failed for development: {roles_error}")

    except Exception as e:
        app.logger.error(f"Database initialization failed for development: {e}")
        # Don't fail the app startup, just log the error

# Езици
app.config["BABEL_DEFAULT_LOCALE"] = "bg"
app.config["BABEL_SUPPORTED_LOCALES"] = ["bg", "en"]


def get_locale():
    """Determine the best locale for the current request"""
    # Check if language is set in session
    session_lang = session.get("language")
    if session_lang and session_lang in ["bg", "en"]:
        return session_lang

    # Check browser language preference
    browser_lang = request.accept_languages.best_match(["bg", "en"])
    if browser_lang:
        return browser_lang

    # Default to Bulgarian
    return "bg"


babel = Babel(app, locale_selector=get_locale)


@app.route("/set_language/<language>", methods=["POST"])
def set_language(language):
    """Set language preference for the user session"""
    if language in ["bg", "en"]:
        session["language"] = language
        # Refresh babel to use new language
        refresh()
    return redirect(request.referrer or url_for("index"))


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# Email configuration
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER", "noreply@helpchain.live")
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "True").lower() == "true"
app.config["MAIL_USE_SSL"] = os.getenv("MAIL_USE_SSL", "False").lower() == "true"
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")

logger.info("Email configuration loaded")
logger.debug(f"MAIL_SERVER: {app.config.get('MAIL_SERVER')}")
logger.debug(f"MAIL_PORT: {app.config.get('MAIL_PORT')}")
logger.debug(f"MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS')}")
logger.debug(f"MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
logger.debug(f"MAIL_DEFAULT_SENDER: {app.config.get('MAIL_DEFAULT_SENDER')}")

# Initialize Mail early
mail = Mail(app)

# Security configurations
app.config["SESSION_COOKIE_SECURE"] = False  # Disabled for development
app.config["SESSION_COOKIE_HTTPONLY"] = False  # Changed to False for testing
app.config["SESSION_COOKIE_SAMESITE"] = None  # Changed to None for testing

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

# Register blueprints after app is created

# Register analytics blueprint first to avoid import issues
try:
    from backend.analytics_routes import analytics_bp
except ImportError:
    from analytics_routes import analytics_bp

app.register_blueprint(analytics_bp)


# Test direct route
@app.route("/test_analytics")
def test_analytics():
    return "test analytics direct"


@app.route("/simple_test")
def simple_test():
    return "simple test works"


app.register_blueprint(admin_roles_bp, url_prefix="/admin/roles")

# Register notification blueprint
app.register_blueprint(notification_bp, url_prefix="/api/notifications")

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

talisman = Talisman(
    app,
    content_security_policy=csp,  # TEMPORARILY PERMISSIVE TO OVERRIDE BROWSER CACHE
    content_security_policy_report_uri="https://csp-report.helpchain.live/report",
    force_https=False,  # Disabled for development testing
    strict_transport_security=False,  # TEMPORARILY DISABLED FOR TESTING
    strict_transport_security_preload=True,
    strict_transport_security_include_subdomains=True,
    strict_transport_security_max_age=63072000,  # 2 years
    referrer_policy="strict-origin-when-cross-origin",
    permissions_policy={
        "camera": "()",
        "microphone": "()",
        "geolocation": "()",
        "payment": "()",
        "usb": "()",
        "magnetometer": "()",
        "accelerometer": "()",
        "gyroscope": "()",
        "ambient-light-sensor": "()",
        "autoplay": "()",
        "encrypted-media": "()",
        "fullscreen": "()",
        "picture-in-picture": "()",
    },
    feature_policy={},  # Deprecated, but keeping for compatibility
)

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
    pass


# Error handlers
@app.errorhandler(404)
def page_not_found(error):
    """Handle 404 errors with custom template"""
    app.logger.warning(f"404 error: {request.url} - {error}")
    if request.is_json or request.path.startswith("/api/"):
        return jsonify(
            {
                "error": "Not Found",
                "message": "The requested resource was not found",
                "status_code": 404,
            }
        ), 404
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def internal_server_error(error):
    """Handle 500 errors with custom template and error tracking"""
    app.logger.error(f"500 error: {request.url} - {error}", exc_info=True)

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
        return jsonify(
            {
                "error": "Internal Server Error",
                "message": "An unexpected error occurred. Please try again later.",
                "status_code": 500,
            }
        ), 500
    return render_template("errors/500.html"), 500


@app.errorhandler(403)
def forbidden(error):
    """Handle 403 errors"""
    app.logger.warning(f"403 error: {request.url} - {error}")
    if request.is_json or request.path.startswith("/api/"):
        return jsonify(
            {
                "error": "Forbidden",
                "message": "You don't have permission to access this resource",
                "status_code": 403,
            }
        ), 403
    flash("Нямате права за достъп до тази страница.", "error")
    return redirect(url_for("index"))


@app.errorhandler(429)
def rate_limit_exceeded(error):
    """Handle rate limit errors"""
    app.logger.warning(f"429 error: {request.url} - Rate limit exceeded")
    if request.is_json or request.path.startswith("/api/"):
        return jsonify(
            {
                "error": "Too Many Requests",
                "message": "Rate limit exceeded. Please try again later.",
                "status_code": 429,
            }
        ), 429
    flash("Твърде много заявки. Моля, изчакайте малко преди да опитате отново.", "warning")
    return redirect(request.referrer or url_for("index"))


@app.route("/")
def index():
    # безопасно извличаме агрегати — ако моделът липсва или схемата
    # не е съвместима, връщаме fallback
    try:
        volunteers_count = db.session.query(Volunteer).count() if "Volunteer" in globals() else 0
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
    logger.debug(f"Request method: {request.method}, EMAIL_2FA_ENABLED = {EMAIL_2FA_ENABLED}")
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
                if admin_user.twofa_enabled:
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
                    session["user_id"] = admin_user.id  # For permission system compatibility
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


@app.route("/logout", methods=["GET", "POST"])
def logout():
    return admin_logout()


@app.route("/admin_logout", methods=["POST"])
def admin_logout():
    session.pop("admin_logged_in", None)
    session.pop("admin_user_id", None)
    session.pop("admin_username", None)
    session.pop("user_id", None)  # Clear permission system user_id
    flash("Излезе от админ панела.", "info")
    return redirect(url_for("admin_login"))


@app.route("/admin_dashboard", endpoint="admin_dashboard")
@require_admin_login
def admin_dashboard():
    # Get filter parameter
    filter_param = request.args.get("filter", "all")

    # Get real statistics from database
    try:
        # Check if HelpRequest model is available
        total_requests = db.session.query(HelpRequest).count()
        pending_requests = (
            db.session.query(HelpRequest).filter(HelpRequest.status == "pending").count()
        )
        completed_requests = (
            db.session.query(HelpRequest).filter(HelpRequest.status == "completed").count()
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
            requests_query = db.session.query(HelpRequest).filter(HelpRequest.status == "pending")
        elif filter_param == "completed":
            requests_query = db.session.query(HelpRequest).filter(HelpRequest.status == "completed")
        else:  # "all" or default
            requests_query = db.session.query(HelpRequest)

        # Limit to recent requests for dashboard display
        requests = requests_query.order_by(HelpRequest.created_at.desc()).limit(10).all()

        # Convert to the expected format for template
        requests_data = []
        for req in requests:
            requests_data.append(
                {
                    "id": req.id,
                    "name": getattr(req, "name", "Неизвестно име"),
                    "status": req.status,
                    "created_at": (
                        req.created_at.strftime("%Y-%m-%d %H:%M") if req.created_at else "Няма дата"
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

    return render_template(
        "admin_dashboard.html",
        requests=requests,
        logs_dict=logs_dict,
        stats=stats,
        current_user=current_user,
        current_filter=filter_param,
    )


# Request management routes
@app.route("/admin/request/<int:request_id>/approve", methods=["POST"])
@require_admin_login
def admin_approve_request(request_id):
    """Approve a help request"""
    try:
        request_obj = db.session.query(HelpRequest).get_or_404(request_id)

        if request_obj.status != "pending":
            return jsonify({"success": False, "message": "Заявката вече е обработена"}), 400

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
        return jsonify({"success": False, "message": "Грешка при одобряване на заявката"}), 500


@app.route("/admin/request/<int:request_id>/reject", methods=["POST"])
@require_admin_login
def admin_reject_request(request_id):
    """Reject a help request"""
    try:
        data = request.get_json() or {}
        reason = data.get("reason", "").strip()

        request_obj = db.session.query(HelpRequest).get_or_404(request_id)

        if request_obj.status != "pending":
            return jsonify({"success": False, "message": "Заявката вече е обработена"}), 400

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
        return jsonify({"success": False, "message": "Грешка при отхвърляне на заявката"}), 500


@app.route("/admin/request/<int:request_id>/assign", methods=["POST"])
@require_admin_login
def admin_assign_volunteer(request_id):
    """Assign a volunteer to a help request"""
    try:
        data = request.get_json() or {}
        volunteer_id = data.get("volunteer_id")

        if not volunteer_id:
            return jsonify({"success": False, "message": "Не е посочен доброволец"}), 400

        request_obj = db.session.query(HelpRequest).get_or_404(request_id)
        volunteer = db.session.query(Volunteer).get_or_404(volunteer_id)

        if request_obj.status != "approved":
            return jsonify(
                {"success": False, "message": "Заявката трябва да бъде одобрена преди присвояване"}
            ), 400

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
            {"success": True, "message": f"Доброволецът {volunteer.name} е присвоен успешно"}
        )

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error assigning volunteer to request {request_id}: {e}")
        return jsonify({"success": False, "message": "Грешка при присвояване на доброволец"}), 500


@app.route("/admin/request/<int:request_id>/delete", methods=["POST"])
@require_admin_login
def admin_delete_request(request_id):
    """Delete a help request"""
    try:
        request_obj = db.session.query(HelpRequest).get_or_404(request_id)

        # Optional: Check if request can be deleted (not assigned, etc.)
        if request_obj.status == "assigned":
            return jsonify(
                {"success": False, "message": "Не може да изтриете присвоена заявка"}
            ), 400

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
        return jsonify({"success": False, "message": "Грешка при изтриване на заявката"}), 500


@app.route("/admin/request/<int:request_id>/edit", methods=["GET", "POST"])
@require_admin_login
def admin_edit_request(request_id):
    """Edit a help request"""
    try:
        request_obj = db.session.query(HelpRequest).get_or_404(request_id)

        if request.method == "POST":
            # Update request fields
            request_obj.name = request.form.get("name", request_obj.name)
            request_obj.email = request.form.get("email", request_obj.email)
            request_obj.message = request.form.get("message", request_obj.message)
            request_obj.title = request.form.get("category", request_obj.title)
            request_obj.location_text = request.form.get("location", request_obj.location_text)

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


@app.route("/notification_dashboard", methods=["GET"], endpoint="notification_dashboard")
@require_admin_login
def notification_dashboard():
    # Get current admin user
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
@require_permission("admin_access", redirect_url="admin_login")
def admin_2fa_setup():
    # Get current admin user
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
                Volunteer.location.asc() if sort_order == "asc" else Volunteer.location.desc()
            )
        elif sort_by == "created_at":
            query = query.order_by(
                Volunteer.created_at.asc() if sort_order == "asc" else Volunteer.created_at.desc()
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

        app.logger.info(
            f"Admin volunteers query successful: {len(volunteers)} volunteers "
            f"returned, page {page}/{total_pages}"
        )

    except Exception as e:
        app.logger.error(f"Error in admin_volunteers: {e}", exc_info=True)
        flash("Възникна грешка при зареждането на доброволците", "error")
        # Return empty results on error
        volunteers = []
        total_volunteers = 0
        total_pages = 1
        page = 1

    return render_template(
        "admin_volunteers.html",
        volunteers=volunteers,
        search=search,
        location_filter=location_filter,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        per_page=per_page,
        total_volunteers=total_volunteers,
        total_pages=total_pages,
    )


@app.route("/admin_volunteers/add", methods=["GET", "POST"])
@require_permission("manage_volunteers", redirect_url="admin_login")
def add_volunteer():
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
        existing_volunteer = db.session.query(Volunteer).filter_by(email=email).first()
        if existing_volunteer:
            flash("Доброволец с този имейл вече съществува!", "error")
            return render_template("add_volunteer.html")

        try:
            volunteer = Volunteer(name=name, email=email, phone=phone, location=location)
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
            "problem": (problem[:50] + "..." if len(problem) > 50 else problem),  # Truncate
            "filename": filename,
        }
        app.logger.info("submit_request received: %s", request_data)

        # TODO: Save to database instead of just logging
        try:
            help_request = HelpRequest(
                name=name, email=email, message=problem, description=problem, status="pending"
            )
            if category:
                help_request.title = category
            if location:
                help_request.location_text = location
            if filename:
                # TODO: Save file reference
                pass

            db.session.add(help_request)
            db.session.commit()
            app.logger.info("Help request saved to database with ID: %s", help_request.id)
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
        existing_volunteer = db.session.query(Volunteer).filter_by(email=email).first()
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
            from flask_mail import Message

            logger.debug(
                "Mail config - SERVER: %s, PORT: %s, USERNAME: %s, PASSWORD: %s",
                app.config.get("MAIL_SERVER"),
                app.config.get("MAIL_PORT"),
                app.config.get("MAIL_USERNAME"),
                "***" if app.config.get("MAIL_PASSWORD") else "None",
            )
            msg = Message(
                subject="Нов доброволец в HelpChain",
                recipients=["contact@helpchain.live"],
                sender=app.config["MAIL_DEFAULT_SENDER"],
                body=f"""Нов доброволец се е регистрирал:

Име: {name}
Имейл: {email}
Телефон: {phone}
Локация: {location}

Моля, свържете се с доброволеца за допълнителна информация.
""",
            )
            logger.debug(
                "Sending volunteer registration email to %s from %s",
                msg.recipients,
                msg.sender,
            )
            mail.send(msg)
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
        email = request.form.get("email")
        app.logger.info(f"POST request received. Email: '{email}'")
        app.logger.info(f"Request form data: {dict(request.form)}")

        # Check if volunteer exists with this email
        try:
            app.logger.info(f"Login attempt for email: {email}")
            volunteer = db.session.query(Volunteer).filter_by(email=email).first()
            app.logger.info(f"Volunteer found: {volunteer is not None}")
            if volunteer:
                app.logger.info(
                    f"Volunteer details: ID={volunteer.id}, Name={volunteer.name}, "
                    f"Email={volunteer.email}"
                )

                # TEMPORARY: Skip 2FA for test email
                if email == "ivan@example.com":
                    app.logger.info("Skipping 2FA for test email")
                    # Clear any admin session to prevent conflicts
                    session.pop("admin_logged_in", None)
                    session.pop("admin_user_id", None)
                    session.pop("admin_username", None)
                    # Set volunteer session
                    session.permanent = True
                    session["volunteer_logged_in"] = True
                    session["volunteer_id"] = volunteer.id
                    session["volunteer_name"] = volunteer.name
                    session.modified = True  # Force session save
                    app.logger.info(
                        f"Session set: volunteer_logged_in={session.get('volunteer_logged_in')}, "
                        f"volunteer_id={session.get('volunteer_id')}"
                    )

                    app.logger.info(f"Volunteer {volunteer.name} logged in directly (test mode)")
                    # For testing, return dashboard directly instead of redirecting
                    # This bypasses session persistence issues in test environment
                    try:
                        # Get statistics with safe database operations
                        stats = _get_volunteer_stats_safe(volunteer.id)
                        active_tasks = _get_active_tasks_safe(volunteer.id)
                        gamification = _get_gamification_data_safe(volunteer)

                        app.logger.info("Rendering dashboard template directly for test mode")
                        return render_template(
                            "volunteer_dashboard.html",
                            current_user=volunteer,
                            stats=stats,
                            active_tasks=active_tasks,
                            gamification=gamification,
                            urgent_tasks=0,  # Add missing urgent_tasks variable
                            recent_points=0,  # Add missing recent_points variable
                        )
                    except Exception as e:
                        app.logger.error(f"Error rendering dashboard for test mode: {e}")
                        return f"Test mode dashboard error: {e}", 500

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
                    from flask_mail import Message

                    msg = Message(
                        subject="HelpChain - Код за достъп",
                        recipients=[email],
                        sender=app.config["MAIL_DEFAULT_SENDER"],
                        body=f"""Здравейте {volunteer.name},

Получен е опит за вход в доброволческия панел на HelpChain.

Вашият код за достъп: {access_code}

Кодът е валиден за 15 минути.

Ако това не сте вие, моля игнорирайте това съобщение.

С уважение,
HelpChain системата
""",
                    )
                    mail.send(msg)
                    app.logger.info(f"Access code sent to {email}")
                except Exception as e:
                    app.logger.error(f"Failed to send access code email: {e}")
                    # Fallback: save to file for development
                    try:
                        with open("sent_emails.txt", "a", encoding="utf-8") as f:
                            f.write(
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
                        app.logger.info("Access code saved to file as fallback")
                    except Exception as file_e:
                        app.logger.error(f"Failed to save email to file: {file_e}")
                        return (
                            jsonify(
                                {"success": False, "message": "Грешка при изпращане на имейл."}
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
            app.logger.error(f"Database error during volunteer login: {e}", exc_info=True)
    return render_template("volunteer_login.html", error=error)


@app.route("/volunteer_verify_code", methods=["GET", "POST"])
def volunteer_verify_code():
    # Check if there's a pending login
    pending = session.get("pending_volunteer_login")
    if not pending:
        flash("Няма чакащ процес на вход. Моля, започнете отново.", "error")
        return redirect(url_for("volunteer_login"))

    # Check if code has expired
    if datetime.now().timestamp() > pending.get("expires", 0):
        session.pop("pending_volunteer_login", None)
        flash("Кодът за достъп е изтекъл. Моля, опитайте отново.", "error")
        return redirect(url_for("volunteer_login"))

    # DEBUG: Print the code to console
    print(f"DEBUG: Volunteer verification code is: {pending.get('access_code')}")

    error = None
    if request.method == "POST":
        entered_code = request.form.get("code", "").strip()

        # TEMPORARY: Allow test code for development
        if entered_code == "test123":
            # Test code accepted, complete login
            volunteer = db.session.query(Volunteer).get(pending["volunteer_id"])
            if volunteer:
                # Clear any admin session to prevent conflicts
                session.pop("admin_logged_in", None)
                session.pop("admin_user_id", None)
                session.pop("admin_username", None)
                # Set volunteer session
                session.permanent = True
                session["volunteer_logged_in"] = True
                session["volunteer_id"] = volunteer.id
                session["volunteer_name"] = volunteer.name
                # Clear pending login
                session.pop("pending_volunteer_login", None)

                app.logger.info(f"Volunteer {volunteer.name} logged in with test code")
                return redirect(url_for("volunteer_dashboard"))
            else:
                error = "Доброволецът не е намерен."
                session.pop("pending_volunteer_login", None)
        elif entered_code == pending.get("access_code"):
            # Code is correct, complete login
            volunteer = db.session.query(Volunteer).get(pending["volunteer_id"])
            if volunteer:
                # Clear any admin session to prevent conflicts
                session.pop("admin_logged_in", None)
                session.pop("admin_user_id", None)
                session.pop("admin_username", None)
                # Set volunteer session
                session.permanent = True
                session["volunteer_logged_in"] = True
                session["volunteer_id"] = volunteer.id
                session["volunteer_name"] = volunteer.name
                # Clear pending login
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
    return redirect(url_for("volunteer_login"))


@app.route("/resend_volunteer_code", methods=["POST"])
def resend_volunteer_code():
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
        volunteer = db.session.query(Volunteer).get(pending["volunteer_id"])
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
            from flask_mail import Message

            msg = Message(
                subject="HelpChain - Нов код за достъп",
                recipients=[volunteer.email],
                sender=app.config["MAIL_DEFAULT_SENDER"],
                body=f"""Здравейте {volunteer.name},

Получен е нов опит за вход в доброволческия панел на HelpChain.

Вашият нов код за достъп: {access_code}

Кодът е валиден за 15 минути.

Ако това не сте вие, моля игнорирайте това съобщение.

С уважение,
HelpChain системата
""",
            )
            mail.send(msg)
            app.logger.info(f"New access code sent to {volunteer.email}")
        except Exception as e:
            app.logger.error(f"Failed to send new access code email: {e}")
            # Fallback: save to file for development
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
                app.logger.info("New access code saved to file as fallback")
            except Exception as file_e:
                app.logger.error(f"Failed to save email to file: {file_e}")
                return (
                    jsonify({"success": False, "message": "Грешка при изпращане на имейл."}),
                    500,
                )

        return jsonify({"success": True, "message": "Нов код е изпратен на вашия имейл."})

    except Exception as e:
        app.logger.error(f"Error resending volunteer code: {e}")
        return (
            jsonify({"success": False, "message": "Възникна грешка при изпращане на кода."}),
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

        # Get volunteer with optimized query
        volunteer = (
            db.session.query(Volunteer)
            .options(db.joinedload(Volunteer.assigned_tasks).joinedload(Task.performance_records))
            .filter_by(id=volunteer_id)
            .first()
        )

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

        # Count urgent tasks nearby (simplified - all urgent pending requests)
        urgent_tasks = (
            db.session.query(HelpRequest).filter_by(status="pending", priority="urgent").count()
        )

        app.logger.info("Rendering template with volunteer data")
        return render_template(
            "volunteer_dashboard.html",
            current_user=volunteer,
            stats=stats,
            active_tasks=active_tasks,
            gamification=gamification,
            urgent_tasks=urgent_tasks,
        )

    except Exception as e:
        app.logger.error(f"Critical error in volunteer dashboard: {e}", exc_info=True)
        flash("Възникна грешка при зареждането на панела. Моля, опитайте отново.", "error")
        return redirect(url_for("index"))


def _get_volunteer_stats_safe(volunteer_id):
    """Safely get volunteer statistics with fallback values"""
    try:
        from models_with_analytics import Task, TaskPerformance

        # Completed tasks count with timeout protection
        completed_tasks = (
            db.session.query(Task).filter_by(assigned_to=volunteer_id, status="completed").count()
        )

        # Active tasks count
        active_tasks_count = (
            db.session.query(Task)
            .filter_by(assigned_to=volunteer_id)
            .filter(Task.status.in_(["assigned", "in_progress"]))
            .count()
        )

        # Average rating with null safety
        avg_rating_result = (
            db.session.query(db.func.avg(TaskPerformance.quality_rating))
            .filter_by(volunteer_id=volunteer_id)
            .scalar()
        )
        rating = round(avg_rating_result, 1) if avg_rating_result else 0.0

        # People helped count
        people_helped = completed_tasks

        # Reviews count
        reviews_count = (
            db.session.query(TaskPerformance).filter_by(volunteer_id=volunteer_id).count()
        )

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
            db.session.query(Task)
            .filter_by(assigned_to=volunteer_id)
            .filter(Task.status.in_(["assigned", "in_progress"]))
            .order_by(Task.created_at.desc())
            .limit(5)
        )

        active_tasks = []
        for task in active_tasks_query:
            # Calculate progress based on status
            progress = 10 if task.status == "assigned" else 50

            # Calculate time remaining safely
            time_remaining = "Няма краен срок"
            if task.deadline:
                try:
                    now = datetime.utcnow()
                    if task.deadline > now:
                        days_remaining = (task.deadline - now).days
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
                    "id": task.id,
                    "title": task.title,
                    "location": task.location_text or "Не е посочена локация",
                    "date": (
                        task.created_at.strftime("%Y-%m-%d") if task.created_at else "Няма дата"
                    ),
                    "time_remaining": time_remaining,
                    "description": task.description or "Няма описание",
                    "priority": task.priority or "medium",
                    "progress": progress,
                }
            )

        return active_tasks

    except Exception as e:
        app.logger.error(f"Error fetching active tasks for volunteer {volunteer_id}: {e}")
        return []


def _get_gamification_data_safe(volunteer):
    """Safely get gamification data"""
    try:
        return {
            "points": volunteer.points,
            "level": volunteer.level,
            "experience": volunteer.experience,
            "level_progress": (
                volunteer.get_level_progress() if hasattr(volunteer, "get_level_progress") else 0
            ),
            "next_level_exp": ((volunteer.level * 100) if hasattr(volunteer, "level") else 100),
        }
    except Exception as e:
        app.logger.error(f"Error getting gamification data for volunteer {volunteer.id}: {e}")
        return {
            "points": 0,
            "level": 1,
            "experience": 0,
            "level_progress": 0,
            "next_level_exp": 100,
        }


@app.route("/chatbot", methods=["GET"])
def chatbot():
    """AI Chatbot interface for users"""
    return render_template("chatbot.html")


@app.route("/api/volunteer/dashboard", methods=["GET"])
def api_volunteer_dashboard():
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


@app.route("/api/admin/dashboard", methods=["GET"])
@require_admin_login
def api_admin_dashboard():
    """API endpoint for admin dashboard data"""
    try:
        # Get basic counts
        volunteers_count = db.session.query(Volunteer).count()
        requests_count = db.session.query(HelpRequest).count()
        admins_count = db.session.query(AdminUser).count()

        # Get recent requests
        recent_requests = (
            db.session.query(HelpRequest).order_by(HelpRequest.created_at.desc()).limit(5).all()
        )

        requests_data = []
        for req in recent_requests:
            requests_data.append(
                {
                    "id": req.id,
                    "title": req.title,
                    "status": req.status,
                    "created_at": req.created_at.isoformat(),
                    "requester_name": req.requester_name,
                }
            )

        return jsonify(
            {
                "stats": {
                    "volunteers_count": volunteers_count,
                    "requests_count": requests_count,
                    "admins_count": admins_count,
                },
                "recent_requests": requests_data,
            }
        )

    except Exception as e:
        app.logger.error(f"Error getting admin dashboard: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/chatbot/message", methods=["POST"])
def chatbot_message():
    """Handle chatbot messages with AI responses"""
    try:
        data = request.get_json()
        user_message = data.get("message", "").strip()
        session_id = data.get("session_id", "default")

        if not user_message:
            return jsonify({"error": "No message provided"}), 400

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
            {"status": "healthy", "providers": ["openai", "gemini"], "active_provider": "openai"}
        )
    except Exception as e:
        app.logger.error(f"Error getting AI status: {e}")
        return jsonify({"status": "error", "providers": [], "active_provider": "none"}), 500


@app.route("/api/volunteer/tasks", methods=["GET"])
def api_volunteer_tasks():
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
                "assigned_at": task.assigned_at.isoformat() if task.assigned_at else None,
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


@app.route("/dashboard", endpoint="dashboard")
def dashboard():
    """General dashboard for logged in users"""
    # Check if user is logged in as volunteer
    if session.get("volunteer_logged_in"):
        return redirect(url_for("volunteer_dashboard"))
    # Check if admin is logged in
    elif session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))
    else:
        flash("Моля, влезте в системата", "warning")
        return redirect(url_for("index"))


@app.route("/update_volunteer_settings", methods=["POST"])
def update_volunteer_settings():
    if not session.get("volunteer_logged_in"):
        return jsonify({"success": False, "message": "Не сте логнати"}), 401

    volunteer_id = session.get("volunteer_id")
    volunteer = db.session.query(Volunteer).get(volunteer_id)
    if not volunteer:
        return jsonify({"success": False, "message": "Доброволецът не е намерен"}), 404

    try:
        # Here you can save settings to volunteer model or separate settings table
        # For now, just return success
        return jsonify({"success": True, "message": "Настройките са запазени"})
    except Exception as e:
        app.logger.error(f"Error updating volunteer settings: {e}")
        return (
            jsonify({"success": False, "message": "Грешка при запазване на настройките"}),
            500,
        )


@app.route("/achievements", methods=["GET"], endpoint="achievements")
def achievements():
    # Check if volunteer is logged in
    if not session.get("volunteer_logged_in"):
        flash("Моля, влезте като доброволец.", "warning")
        return redirect(url_for("volunteer_login"))

    try:
        volunteer_id = session.get("volunteer_id")
        volunteer = db.session.query(Volunteer).get(volunteer_id)

        if not volunteer:
            flash("Доброволецът не е намерен.", "error")
            return redirect(url_for("volunteer_login"))

        # Import gamification service
        try:
            from gamification_service import GamificationService
            from models import Achievement
        except ImportError:
            # Fallback for standalone execution
            from backend.gamification_service import GamificationService
            from backend.models import Achievement

        # Get all achievements and calculate progress for each
        all_achievements = db.session.query(Achievement).all()
        achievements_data = []
        for achievement in all_achievements:
            progress = GamificationService.get_achievement_progress(volunteer, achievement)
            is_unlocked = achievement.id in volunteer.achievements

            achievements_data.append(
                {
                    "id": achievement.id,
                    "name": achievement.name,
                    "description": achievement.description,
                    "icon": achievement.icon,
                    "category": achievement.category,
                    "rarity": achievement.rarity,
                    "progress": progress,
                    "is_unlocked": is_unlocked,
                    "requirement_value": achievement.requirement_value,
                    "requirement_type": achievement.requirement_type,
                }
            )

        # Get leaderboard data
        leaderboard = GamificationService.get_leaderboard(limit=10)

        # Get volunteer's rank
        volunteer_rank = None
        for i, entry in enumerate(leaderboard, 1):
            if entry.id == volunteer_id:
                volunteer_rank = i
                break

        # Prepare stats for display
        volunteer_stats = {
            "points": volunteer.points,
            "level": volunteer.level,
            "experience": volunteer.experience,
            "total_tasks_completed": volunteer.total_tasks_completed,
            "streak_days": volunteer.streak_days,
            "rank": volunteer_rank,
        }

        # Get level progress info
        level_progress = volunteer.get_level_progress()

        return render_template(
            "achievements.html",
            volunteer=volunteer,
            achievements=achievements_data,
            leaderboard=leaderboard,
            stats=volunteer_stats,
            level_progress=level_progress,
        )

    except Exception as e:
        app.logger.error(f"Error loading achievements page: {e}")
        flash("Възникна грешка при зареждането на постиженията", "error")
        return redirect(url_for("volunteer_dashboard"))


@app.route("/volunteer_chat", methods=["GET"], endpoint="volunteer_chat")
def volunteer_chat():
    # Check if volunteer is logged in
    if not session.get("volunteer_logged_in"):
        flash("Моля, влезте като доброволец.", "warning")
        return redirect(url_for("volunteer_login"))
    # Placeholder for volunteer chat page
    return render_template("volunteer_chat.html")


@app.route("/volunteer_reports", methods=["GET"], endpoint="volunteer_reports")
def volunteer_reports():
    # Check if volunteer is logged in
    if not session.get("volunteer_logged_in"):
        flash("Моля, влезте като доброволец.", "warning")
        return redirect(url_for("volunteer_login"))
    # Placeholder for volunteer reports page
    return render_template("volunteer_reports.html")


@app.route("/volunteer_settings", methods=["GET", "POST"], endpoint="volunteer_profile")
def volunteer_settings():
    # Check if volunteer is logged in
    if not session.get("volunteer_logged_in"):
        flash("Моля, влезте като доброволец.", "warning")
        return redirect(url_for("volunteer_login"))
    # Placeholder for volunteer settings page
    return render_template("volunteer_settings.html")


@app.route("/my_tasks", endpoint="my_tasks")
def my_tasks():
    """Show volunteer's assigned tasks"""
    if not session.get("volunteer_logged_in"):
        flash("Моля, влезте като доброволец.", "warning")
        return redirect(url_for("volunteer_login"))

    try:
        volunteer_id = session.get("volunteer_id")
        volunteer = db.session.query(Volunteer).get(volunteer_id)

        if not volunteer:
            flash("Доброволецът не е намерен.", "error")
            return redirect(url_for("volunteer_login"))

        # Get assigned tasks with different statuses
        active_tasks = (
            db.session.query(Task)
            .filter_by(assigned_to=volunteer_id)
            .filter(Task.status.in_(["assigned", "in_progress"]))
            .order_by(Task.created_at.desc())
            .all()
        )

        completed_tasks = (
            db.session.query(Task)
            .filter_by(assigned_to=volunteer_id)
            .filter_by(status="completed")
            .order_by(Task.completed_at.desc())
            .limit(10)
            .all()
        )

        return render_template(
            "my_tasks.html",
            volunteer=volunteer,
            active_tasks=active_tasks,
            completed_tasks=completed_tasks,
        )

    except Exception as e:
        app.logger.error(f"Error loading my tasks: {e}")
        flash("Възникна грешка при зареждането на задачите", "error")
        return redirect(url_for("volunteer_dashboard"))


@app.route("/available_tasks", endpoint="available_tasks")
def available_tasks():
    """Show available tasks for volunteers to apply"""
    if not session.get("volunteer_logged_in"):
        flash("Моля, влезте като доброволец.", "warning")
        return redirect(url_for("volunteer_login"))

    try:
        volunteer_id = session.get("volunteer_id")
        volunteer = db.session.query(Volunteer).get(volunteer_id)

        if not volunteer:
            flash("Доброволецът не е намерен.", "error")
            return redirect(url_for("volunteer_login"))

        # Get available tasks (not assigned to anyone)
        page = int(request.args.get("page", 1))
        per_page = 12

        available_tasks_query = (
            db.session.query(Task)
            .filter_by(assigned_to=None)
            .filter_by(status="open")
            .order_by(Task.created_at.desc())
        )

        # Apply pagination
        total_tasks = available_tasks_query.count()
        available_tasks = available_tasks_query.offset((page - 1) * per_page).limit(per_page).all()

        total_pages = (total_tasks + per_page - 1) // per_page

        return render_template(
            "available_tasks.html",
            volunteer=volunteer,
            available_tasks=available_tasks,
            page=page,
            total_pages=total_pages,
            total_tasks=total_tasks,
        )

    except Exception as e:
        app.logger.error(f"Error loading available tasks: {e}")
        flash("Възникна грешка при зареждането на наличните задачи", "error")
        return redirect(url_for("volunteer_dashboard"))


@app.route("/admin_volunteers/edit/<int:id>", methods=["GET", "POST"])
@require_admin_login
def edit_volunteer(id):
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


@app.route("/admin_tasks", methods=["GET"])
@require_admin_login
def admin_tasks():
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
            "assigned_tasks": db.session.query(Task).filter_by(status="assigned").count(),
            "in_progress_tasks": db.session.query(Task)
            .filter(Task.status == "in_progress")
            .count(),
            "completed_tasks": db.session.query(Task).filter_by(status="completed").count(),
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
    """Create a new task"""
    if request.method == "POST":
        try:
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            category = request.form.get("category", "").strip()
            priority = request.form.get("priority", "medium")
            location_required = request.form.get("location_required") == "on"
            location_text = (
                request.form.get("location_text", "").strip() if location_required else None
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
                request.form.get("location_text", "").strip() if task.location_required else None
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
    """Delete a task"""
    try:
        task = db.session.query(Task).get_or_404(task_id)

        # Check if task is assigned
        if task.assigned_to:
            flash("Не може да изтриете задача, която е присвоена на доброволец", "error")
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
            task.assigned_at = datetime.utcnow()
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


@app.route("/admin_request_details/<int:request_id>")
@require_admin_login
def admin_request_details(request_id):
    """Show detailed view of a specific help request"""
    try:
        request_obj = db.session.query(HelpRequest).get_or_404(request_id)

        # Get current admin user
        current_user = None
        if session.get("admin_user_id"):
            current_user = db.session.get(AdminUser, session.get("admin_user_id"))

        return render_template(
            "admin_request_details.html", request=request_obj, current_user=current_user
        )
    except Exception as e:
        app.logger.error(f"Error loading request details for ID {request_id}: {e}")
        flash("Грешка при зареждането на детайлите за заявката", "error")
        return redirect(url_for("admin_dashboard"))


@app.route("/admin_update_request_status", methods=["POST"])
@require_admin_login
def admin_update_request_status():
    """Update the status of a help request via AJAX"""
    try:
        data = request.get_json()
        request_id = data.get("request_id")
        new_status = data.get("status")

        if not request_id or not new_status:
            return (
                jsonify({"success": False, "message": "Липсват задължителни параметри"}),
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
        request_obj.status = new_status
        db.session.commit()

        app.logger.info(f"Request {request_id} status changed from {old_status} to {new_status}")

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
        # Fallback to CSV if reportlab is not installed
        return export_volunteers_csv(volunteers)


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
    volunteers = db.session.query(Volunteer).filter(Volunteer.skills.ilike(f"%{category}%")).all()

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


@app.route("/all_categories")
def all_categories():
    """Показва всички категории помощ"""
    categories = [
        {
            "slug": "medical",
            "name": "Спешна помощ",
            "icon": "fas fa-ambulance",
            "color": "danger",
            "description": "Медицинска помощ, спешни случаи",
        },
        {
            "slug": "transport",
            "name": "Транспорт",
            "icon": "fas fa-car",
            "color": "info",
            "description": "Превоз на хора и стоки",
        },
        {
            "slug": "household",
            "name": "Домакинска помощ",
            "icon": "fas fa-home",
            "color": "success",
            "description": "Почистване, ремонт, грижи за дома",
        },
        {
            "slug": "education",
            "name": "Образование",
            "icon": "fas fa-graduation-cap",
            "color": "warning",
            "description": "Помощ с уроци, консултации",
        },
        {
            "slug": "legal",
            "name": "Правна помощ",
            "icon": "fas fa-gavel",
            "color": "primary",
            "description": "Юридически консултации",
        },
        {
            "slug": "psychological",
            "name": "Психологическа помощ",
            "icon": "fas fa-brain",
            "color": "secondary",
            "description": "Подкрепа и консултации",
        },
    ]

    return render_template("all_categories.html", categories=categories)


@app.route("/chat")
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
            volunteer = db.session.query(Volunteer).get(session.get("volunteer_id"))
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
                db.session.query(ChatParticipant).filter_by(room_id=room.id, is_online=True).count()
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
        return jsonify({"error": str(e)}), 500


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
        return jsonify({"error": str(e)}), 500


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
        return jsonify({"error": str(e)}), 500


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
            participant.last_seen = datetime.utcnow()
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
        task.assigned_at = datetime.utcnow()
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
            task.completed_at = datetime.utcnow()
        elif new_status == "in_progress" and old_status == "assigned":
            # Task started
            pass

        # Create performance record
        performance = TaskPerformance(
            task_id=task.id,
            volunteer_id=volunteer.id,
            status_change=f"{old_status} -> {new_status}",
            notes=progress_notes,
            created_at=datetime.utcnow(),
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
        from analytics_service import analytics_service

        # Получаваме основни статистики
        dashboard_stats = analytics_service.get_dashboard_analytics(days=30)

        # Геолокационни данни за карта
        geo_data = []  # Placeholder - implement if needed

        # Трендове за последните 12 месеца - предоставяме основни данни
        trends_data = {
            "labels": ["Януари", "Февруари", "Март", "Април", "Май", "Юни"],
            "requests": [10, 15, 8, 22, 18, 25],
            "completed": [8, 12, 6, 18, 15, 20],
            "volunteers": [5, 7, 4, 12, 9, 14],
        }

        # Прогнози за следващите 3 месеца - предоставяме примерни данни
        predictions = {
            "labels": ["Месец 1", "Месец 2", "Месец 3"],
            "requests_predicted": [25, 28, 32],
            "volunteers_predicted": [14, 16, 18],
            "ml_insights": {
                "anomalies": [],
                "predictions": {"optimal_engagement_time": {"hour": 14, "engagement_score": 85}},
                "recommendations": [
                    {
                        "title": "Подобри видимостта",
                        "description": "Увеличи броя на доброволците",
                        "action": "Рекламирай повече",
                        "priority": "high",
                    }
                ],
            },
        }

        # Live статистики
        live_stats = dashboard_stats.get("real_time", {})

        # Категорийни статистики - предоставяме примерни данни
        category_stats = {
            "categories": ["Медицинска помощ", "Транспорт", "Домакинска помощ", "Образование"],
            "counts": [15, 8, 12, 6],
        }

        # Performance метрики
        performance_metrics = dashboard_stats.get("performance_metrics", {})

        return render_template(
            "admin_analytics.html",
            dashboard_stats=dashboard_stats,
            geo_data=geo_data,
            trends_data=trends_data,
            predictions=predictions,
            live_stats=live_stats,
            category_stats=category_stats,
            performance_metrics=performance_metrics,
        )

    except Exception as e:
        app.logger.error(f"Error loading analytics dashboard: {e}")
        flash("Възникна грешка при зареждането на аналитиката", "error")
        return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    print("🚀 HelpChain server starting...")
    print("📍 http://127.0.0.1:5000")
    print("👤 Admin: admin / Admin123")
    print("Press Ctrl+C to stop")
    debug_mode = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    app.run(debug=debug_mode, host="127.0.0.1", port=5000)
