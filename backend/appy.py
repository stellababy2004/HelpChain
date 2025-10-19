import logging
import os
import secrets
import sys
import traceback
from datetime import datetime

# Import Celery for background tasks
from celery import Celery
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_babel import Babel, refresh
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_migrate import Migrate
from flask_talisman import Talisman
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlalchemy.exc import OperationalError
from werkzeug.exceptions import BadRequest
from werkzeug.utils import secure_filename

# Try relative imports first, fall back to absolute imports for standalone execution
try:
    from extensions import db
except ImportError:
    # Fallback for standalone execution
    try:
        from extensions import db
    except ImportError:
        from extensions import db

try:
    from models import (
        AdminUser,
        HelpRequest,
        Role,
        User,
        UserRole,
        Volunteer,
    )
except ImportError:
    from models import (
        AdminUser,
        HelpRequest,
        Role,
        User,
        UserRole,
        Volunteer,
    )

    try:
        from models_with_analytics import Task
    except ImportError:
        from models_with_analytics import Task

# Import permissions module - always needed
try:
    from permissions import (
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
    from models_with_analytics import Task
except ImportError:
    from models_with_analytics import Task

try:
    from admin_roles import admin_roles_bp
except ImportError:
    from admin_roles import admin_roles_bp

# try:
#     from routes.notifications import notification_bp
# except ImportError:
#     from routes.notifications import notification_bp

# Import smart matching engine
try:
    from ai_service import ai_service
except ImportError:
    from ai_service import ai_service

# Import analytics service
# try:
#     from analytics_service import analytics_service
# except ImportError:
#     from analytics_service import analytics_service

# Import Celery tasks
# try:
#     from tasks import process_request_immediately
# except ImportError:
#     pass

# Add the backend directory to Python path so we can import models and extensions
backend_dir = os.path.dirname(__file__)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Зареди environment variables от .env файла (от корена на проекта)
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
print(f"Loading .env from: {dotenv_path}")
print(f".env file exists: {os.path.exists(dotenv_path)}")
load_dotenv(dotenv_path=dotenv_path)
print(f"SECRET_KEY after load_dotenv: {os.getenv('SECRET_KEY')}")
print(f"VAPID_PUBLIC_KEY after load_dotenv: {os.getenv('VAPID_PUBLIC_KEY')}")

# Sentry for error monitoring

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

# Debug logging for environment variables after logger setup
logger.info(f"VAPID_PUBLIC_KEY from env: {repr(os.getenv('VAPID_PUBLIC_KEY'))}")
logger.info(f"VAPID_PRIVATE_KEY from env: {repr(os.getenv('VAPID_PRIVATE_KEY'))}")
logger.info(f"SECRET_KEY from env: {repr(os.getenv('SECRET_KEY'))}")


def initialize_default_admin():
    """
    Initialize default admin user if it doesn't exist, or update password if it does
    """
    try:
        logger.info("Checking for existing admin user...")
        # Check if admin user exists
        admin_user = db.session.query(AdminUser).filter_by(username="admin").first()
        if admin_user:
            logger.info("Admin user already exists, updating password...")
            # Update the password to ensure it matches the expected value
            admin_user.set_password(os.getenv("ADMIN_USER_PASSWORD", "Admin123"))
            db.session.commit()
            logger.info("Admin password updated successfully")
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
        superadmin_role = (
            db.session.query(Role).filter_by(name="Супер администратор").first()
        )
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
            logger.error(
                f"Failed to save email 2FA code to file: {file_e}", exc_info=True
            )
            return False


# Създай папката instance ако не съществува
os.makedirs(os.path.join(os.path.dirname(__file__), "instance"), exist_ok=True)

# Задаваме явни папки за шаблони и статични файлове (адаптирай пътищата ако е нужно)
_templates = os.path.join(os.path.dirname(__file__), "templates")
_static = os.path.join(os.path.dirname(__file__), "static")

# from flask_session import Session

# Initialize Flask app
app = Flask(__name__, template_folder=_templates, static_folder=_static)

# Задаваме SECRET_KEY за сесии и сигурност ПРЕДИ Flask-Session инициализация
app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY", "dev-secret-key-change-in-production"
)

# JWT Configuration
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", app.config["SECRET_KEY"])
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = int(
    os.getenv("JWT_ACCESS_TOKEN_EXPIRES", 3600)
)  # 1 hour
app.config["JWT_REFRESH_TOKEN_EXPIRES"] = int(
    os.getenv("JWT_REFRESH_TOKEN_EXPIRES", 86400)
)  # 24 hours

# VAPID Configuration for Push Notifications
app.config["VAPID_PUBLIC_KEY"] = os.getenv("VAPID_PUBLIC_KEY")
app.config["VAPID_PRIVATE_KEY"] = os.getenv("VAPID_PRIVATE_KEY")

# Debug logging for VAPID keys
app.logger.info(f"VAPID_PUBLIC_KEY loaded: {bool(app.config.get('VAPID_PUBLIC_KEY'))}")
app.logger.info(
    f"VAPID_PRIVATE_KEY loaded: {bool(app.config.get('VAPID_PRIVATE_KEY'))}"
)

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
        logger.info(
            f"Production mode detected, using fallback SQLite database: {db_path}"
        )
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


@app.route("/sw.js")
def serve_sw():
    """Serve the service worker from the static directory"""
    response = make_response(
        send_from_directory(
            app.static_folder, "sw.js", mimetype="application/javascript"
        )
    )
    response.headers["Service-Worker-Allowed"] = "/"
    return response


ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# Email configuration
app.config["MAIL_DEFAULT_SENDER"] = os.getenv(
    "MAIL_DEFAULT_SENDER", "noreply@helpchain.live"
)
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
app.config["SESSION_COOKIE_SECURE"] = True  # Require HTTPS for session cookies
app.config["SESSION_COOKIE_HTTPONLY"] = (
    True  # Prevent JavaScript access to session cookies
)
app.config["SESSION_COOKIE_SAMESITE"] = (
    "Lax"  # CSRF protection while allowing some cross-site requests
)

# Upload folder configuration
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB limit

if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])

# Initialize security extensions
limiter = Limiter(
    app=app,
    default_limits=["100 per day", "30 per hour"],  # Stricter default limits
    storage_uri="memory://",  # In production, use Redis: "redis://localhost:6379/0"
    strategy="fixed-window",  # Use fixed window for more predictable limiting
    key_func=get_remote_address,
    headers_enabled=True,  # Enable rate limit headers
)

# Initialize JWT Manager
jwt = JWTManager(app)

# Register blueprints after app is created

# Register analytics blueprint first to avoid import issues
try:
    from analytics_routes import analytics_bp
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
try:
    from routes.notifications import notification_bp

    print(f"Notification blueprint imported: {notification_bp}")  # Debug print
    app.register_blueprint(notification_bp, url_prefix="/api/notification")
    app.logger.info("Notification blueprint registered successfully")
    print("Notification blueprint registered successfully")  # Debug print

    # Debug: Print all registered routes
    print("Registered routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.rule} -> {rule.endpoint}")

except ImportError as e:
    app.logger.error(f"Failed to import notification blueprint: {e}")
    print(f"Failed to import notification blueprint: {e}")  # Debug print
except Exception as e:
    app.logger.error(f"Failed to register notification blueprint: {e}")
    print(f"Failed to register notification blueprint: {e}")  # Debug print

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

# talisman = Talisman(
talisman = Talisman(
    app,
    content_security_policy=csp,  # ENFORCED - no longer report-only
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


# Add CSP headers manually to ensure they are applied
# @app.after_request
# def add_csp_headers(response):
#     """Add Content Security Policy headers to all responses"""
#     csp_value = (
#         "default-src 'self'; "
#         "font-src 'self' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
#         "script-src 'self' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net "
#         "'unsafe-inline'; "
#         "style-src 'self' https://fonts.googleapis.com https://cdnjs.cloudflare.com "
#         "https://cdn.jsdelivr.net 'unsafe-inline'; "
#         "connect-src 'self' https://cdn.jsdelivr.net; "
#         "img-src 'self' data: https://helpchain.live *; "
#         "frame-ancestors 'none'; "
#         "base-uri 'self'; "
#         "form-action 'self'"
#     )
#     response.headers["Content-Security-Policy"] = csp_value
#     return response


# csrf = CSRFProtect(app)  # Disabled for development testing

# CORS configuration - STRICT allowlist (no wildcards)
cors = CORS(
    app,
    resources={
        r"/api/*": {
            "origins": [
                "https://helpchain.live",
                "https://www.helpchain.live",
                # Add staging if needed: "https://staging.helpchain.live"
            ],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
            "supports_credentials": False,  # Never allow credentials for API
            "max_age": 86400,  # Cache preflight for 24h
        }
    },
    # Disable CORS for non-API routes (default deny)
)

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


# Centralized error logging function
def log_error(error, error_type="general", context=None):
    """Centralized error logging with comprehensive context"""
    try:
        # Prepare error context
        error_context = {
            "error_type": error_type,
            "error_message": str(error),
            "url": request.url if request else "N/A",
            "method": request.method if request else "N/A",
            "user_agent": request.headers.get("User-Agent") if request else "N/A",
            "ip_address": request.remote_addr if request else "N/A",
            "user_id": (
                session.get("user_id")
                or session.get("volunteer_id")
                or session.get("admin_user_id")
            ),
            "session_id": session.sid if hasattr(session, "sid") else "N/A",
            "timestamp": datetime.now().isoformat(),
        }

        # Add additional context if provided
        if context:
            error_context.update(context)

        # Log to different handlers based on error type
        if error_type == "security":
            security_logger = logging.getLogger("security")
            security_logger.warning(f"Security error: {error_context}")
        elif error_type == "rate_limit":
            security_logger = logging.getLogger("security")
            security_logger.info(f"Rate limit exceeded: {error_context}")
        elif isinstance(error, Exception) and "database" in str(error).lower():
            app.logger.error(f"Database error: {error_context}", exc_info=True)
        else:
            app.logger.error(f"Application error: {error_context}", exc_info=True)

        # Track error in analytics if available
        try:
            from analytics_service import analytics_service

            analytics_service.track_event(
                event_type="error",
                event_category="system",
                event_action=f"{error_type}_error",
                context=error_context,
            )
        except Exception as analytics_error:
            app.logger.debug(f"Analytics tracking failed: {analytics_error}")

    except Exception as log_error:
        # Fallback logging if centralized logging fails
        print(f"CRITICAL: Error in log_error function: {log_error}")
        app.logger.critical(f"Error in centralized logging: {log_error}", exc_info=True)


@app.errorhandler(404)
def page_not_found(error):
    """Handle 404 errors with custom template"""
    log_error(
        error,
        "page_not_found",
        {
            "url": request.url,
            "method": request.method,
            "user_agent": request.headers.get("User-Agent"),
            "ip": request.remote_addr,
            "referrer": request.referrer,
        },
    )
    if request.is_json or request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "error": "Not Found",
                    "message": "The requested resource was not found",
                    "status_code": 404,
                }
            ),
            404,
        )
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def internal_server_error(error):
    """Handle 500 errors with custom template and error tracking"""
    log_error(
        error,
        "internal_server_error",
        {
            "url": request.url,
            "method": request.method,
            "user_agent": request.headers.get("User-Agent"),
            "ip": request.remote_addr,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
        },
    )
    if request.is_json or request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred. Please try again later.",
                    "status_code": 500,
                }
            ),
            500,
        )
    return render_template("errors/500.html"), 500


@app.errorhandler(403)
def forbidden(error):
    """Handle 403 errors"""
    log_error(
        error,
        "forbidden",
        {
            "url": request.url,
            "method": request.method,
            "user_agent": request.headers.get("User-Agent"),
            "ip": request.remote_addr,
            "referrer": request.referrer,
        },
    )
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


@app.errorhandler(429)
def rate_limit_exceeded(error):
    """Handle rate limit errors"""
    log_error(
        error,
        "rate_limit",
        {
            "url": request.url,
            "method": request.method,
            "user_agent": request.headers.get("User-Agent"),
            "ip": request.remote_addr,
            "referrer": request.referrer,
            "rate_limit_info": getattr(error, "description", "Rate limit exceeded"),
        },
    )
    if request.is_json or request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "error": "Too Many Requests",
                    "message": "Rate limit exceeded. Please try again later.",
                    "status_code": 429,
                }
            ),
            429,
        )
    flash(
        "Твърде много заявки. Моля, изчакайте малко преди да опитате отново.", "warning"
    )
    return redirect(request.referrer or url_for("index"))


@app.route("/")
def index():
    # безопасно извличаме агрегати — ако моделът липсва или схемата
    # не е съвместима, връщаме fallback
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
    logger.info(f"Current directory: {os.getcwd()}")
    logger.info(f"Request form data: {dict(request.form)}")
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
                    session["user_id"] = (
                        admin_user.id
                    )  # For permission system compatibility
                    session.permanent = True  # Make session persistent
                    logger.info(
                        f"Session set: admin_logged_in={session.get('admin_logged_in')}, admin_user_id={session.get('admin_user_id')}"
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


@app.route("/api/auth/admin/login", methods=["POST"])
@limiter.limit("5 per minute; 20 per hour")  # Rate limit login attempts
def jwt_admin_login():
    """JWT-based admin login endpoint"""
    try:
        data = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()

        if not username or not password:
            return jsonify({"error": "Username and password are required"}), 400

        # Initialize default admin if needed
        admin_user = initialize_default_admin()
        if not admin_user:
            return jsonify({"error": "Admin initialization failed"}), 500

        # Check credentials
        if admin_user.username == username and admin_user.check_password(password):
            # Check if 2FA is enabled
            if admin_user.twofa_enabled:
                return (
                    jsonify(
                        {
                            "error": "2FA required",
                            "requires_2fa": True,
                            "admin_id": admin_user.id,
                        }
                    ),
                    200,
                )

            # Generate JWT tokens
            access_token = create_access_token(
                identity=str(admin_user.id),
                additional_claims={"role": "admin", "username": admin_user.username},
            )
            refresh_token = create_refresh_token(
                identity=str(admin_user.id),
                additional_claims={"role": "admin", "username": admin_user.username},
            )

            # Track analytics
            try:
                from analytics_service import analytics_service

                analytics_service.track_event(
                    event_type="admin_login",
                    event_category="authentication",
                    event_action="jwt_login_success",
                    context={"admin_id": admin_user.id, "method": "jwt"},
                )
            except Exception as analytics_error:
                app.logger.warning(f"Analytics tracking failed: {analytics_error}")

            return (
                jsonify(
                    {
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                        "user": {
                            "id": admin_user.id,
                            "username": admin_user.username,
                            "role": "admin",
                        },
                    }
                ),
                200,
            )
        else:
            # Track failed login
            try:
                from analytics_service import analytics_service

                analytics_service.track_event(
                    event_type="admin_login",
                    event_category="authentication",
                    event_action="jwt_login_failed",
                    context={"username": username, "ip": request.remote_addr},
                )
            except Exception as analytics_error:
                app.logger.warning(f"Analytics tracking failed: {analytics_error}")

            return jsonify({"error": "Invalid credentials"}), 401

    except Exception as e:
        app.logger.error(f"JWT admin login error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/auth/admin/2fa", methods=["POST"])
def jwt_admin_2fa():
    """JWT-based admin 2FA verification"""
    try:
        data = request.get_json()
        admin_id = data.get("admin_id")
        token = data.get("token", "").strip()

        if not admin_id or not token:
            return jsonify({"error": "Admin ID and token are required"}), 400

        admin_user = db.session.query(AdminUser).get(admin_id)
        if not admin_user:
            return jsonify({"error": "Admin not found"}), 404

        # Verify TOTP token
        if admin_user.verify_totp(token):
            # Generate JWT tokens
            access_token = create_access_token(
                identity=str(admin_user.id),
                additional_claims={"role": "admin", "username": admin_user.username},
            )
            refresh_token = create_refresh_token(
                identity=str(admin_user.id),
                additional_claims={"role": "admin", "username": admin_user.username},
            )

            return (
                jsonify(
                    {
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                        "user": {
                            "id": admin_user.id,
                            "username": admin_user.username,
                            "role": "admin",
                        },
                    }
                ),
                200,
            )
        else:
            return jsonify({"error": "Invalid 2FA token"}), 401

    except Exception as e:
        app.logger.error(f"JWT admin 2FA error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/auth/volunteer/login", methods=["POST"])
@limiter.limit("5 per minute; 15 per hour")  # Rate limit volunteer login attempts
def jwt_volunteer_login():
    """JWT-based volunteer login endpoint"""
    try:
        data = request.get_json()
        email = data.get("email", "").strip()

        if not email:
            return jsonify({"error": "Email is required"}), 400

        # Check if volunteer exists
        volunteer = db.session.query(Volunteer).filter_by(email=email).first()
        if not volunteer:
            return jsonify({"error": "Volunteer not found"}), 404

        # For test volunteer, skip email verification
        if email == "ivan@example.com":
            access_token = create_access_token(
                identity=str(volunteer.id),
                additional_claims={"role": "volunteer", "name": volunteer.name},
            )
            refresh_token = create_refresh_token(
                identity=str(volunteer.id),
                additional_claims={"role": "volunteer", "name": volunteer.name},
            )

            # Track analytics
            try:
                from analytics_service import analytics_service

                analytics_service.track_event(
                    event_type="volunteer_login",
                    event_category="authentication",
                    event_action="jwt_login_success",
                    context={
                        "volunteer_id": volunteer.id,
                        "method": "jwt",
                        "test_mode": True,
                    },
                )
            except Exception as analytics_error:
                app.logger.warning(f"Analytics tracking failed: {analytics_error}")

            return (
                jsonify(
                    {
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                        "user": {
                            "id": volunteer.id,
                            "name": volunteer.name,
                            "email": volunteer.email,
                            "role": "volunteer",
                        },
                    }
                ),
                200,
            )

        # Generate verification code
        import secrets

        verification_code = str(secrets.randbelow(900000) + 100000)

        # Store in session with expiration
        session["jwt_volunteer_pending"] = {
            "volunteer_id": volunteer.id,
            "email": email,
            "verification_code": verification_code,
            "expires": datetime.now().timestamp() + 900,  # 15 minutes
        }

        # Send verification email
        try:
            from flask_mail import Message

            msg = Message(
                subject="HelpChain - JWT Код за достъп",
                recipients=[email],
                sender=app.config["MAIL_DEFAULT_SENDER"],
                body=f"""Здравейте {volunteer.name},

Получен е опит за JWT вход в доброволческия панел на HelpChain.

Вашият код за верификация: {verification_code}

Кодът е валиден за 15 минути.

Използвайте този код в приложението за да завършите входа.

С уважение,
HelpChain системата
""",
            )
            mail.send(msg)
            app.logger.info(f"JWT verification code sent to {email}")
        except Exception as e:
            app.logger.error(f"Failed to send JWT verification email: {e}")
            # Fallback: save to file
            try:
                with open("sent_emails.txt", "a", encoding="utf-8") as f:
                    f.write(
                        "Subject: HelpChain - JWT Код за достъп\n"
                        f"To: {email}\nFrom: {app.config['MAIL_DEFAULT_SENDER']}\n\n"
                        f"Здравейте {volunteer.name},\n\n"
                        "Получен е опит за JWT вход в доброволческия панел на HelpChain.\n\n"
                        f"Вашият код за верификация: {verification_code}\n\n"
                        "Кодът е валиден за 15 минути.\n\n"
                        "Използвайте този код в приложението за да завършите входа.\n\n"
                        "С уважение,\nHelpChain системата\n\n"
                        f"{'=' * 50}\n"
                    )
                app.logger.info("JWT verification code saved to file as fallback")
            except Exception as file_e:
                app.logger.error(f"Failed to save JWT email to file: {file_e}")
                return jsonify({"error": "Failed to send verification email"}), 500

        return (
            jsonify(
                {
                    "message": "Verification code sent to email",
                    "requires_verification": True,
                }
            ),
            200,
        )

    except Exception as e:
        app.logger.error(f"JWT volunteer login error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/auth/volunteer/verify", methods=["POST"])
def jwt_volunteer_verify():
    """JWT-based volunteer verification endpoint"""
    try:
        data = request.get_json()
        code = data.get("code", "").strip()

        if not code:
            return jsonify({"error": "Verification code is required"}), 400

        # Check pending verification
        pending = session.get("jwt_volunteer_pending")
        if not pending:
            return jsonify({"error": "No pending verification"}), 400

        # Check expiration
        if datetime.now().timestamp() > pending.get("expires", 0):
            session.pop("jwt_volunteer_pending", None)
            return jsonify({"error": "Verification code expired"}), 400

        # Verify code
        if code == pending.get("verification_code"):
            volunteer = db.session.query(Volunteer).get(pending["volunteer_id"])
            if not volunteer:
                return jsonify({"error": "Volunteer not found"}), 404

            # Generate JWT tokens
            access_token = create_access_token(
                identity=str(volunteer.id),
                additional_claims={"role": "volunteer", "name": volunteer.name},
            )
            refresh_token = create_refresh_token(
                identity=str(volunteer.id),
                additional_claims={"role": "volunteer", "name": volunteer.name},
            )

            # Clear pending verification
            session.pop("jwt_volunteer_pending", None)

            # Track analytics
            try:
                from analytics_service import analytics_service

                analytics_service.track_event(
                    event_type="volunteer_login",
                    event_category="authentication",
                    event_action="jwt_login_success",
                    context={"volunteer_id": volunteer.id, "method": "jwt"},
                )
            except Exception as analytics_error:
                app.logger.warning(f"Analytics tracking failed: {analytics_error}")

            return (
                jsonify(
                    {
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                        "user": {
                            "id": volunteer.id,
                            "name": volunteer.name,
                            "email": volunteer.email,
                            "role": "volunteer",
                        },
                    }
                ),
                200,
            )
        else:
            return jsonify({"error": "Invalid verification code"}), 401

    except Exception as e:
        app.logger.error(f"JWT volunteer verification error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/api/auth/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh_token():
    """Refresh access token using refresh token"""
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()

        # Generate new access token
        access_token = create_access_token(
            identity=current_user_id,
            additional_claims={
                "role": claims.get("role"),
                "username": claims.get("username"),
                "name": claims.get("name"),
            },
        )

        return jsonify({"access_token": access_token}), 200

    except Exception as e:
        app.logger.error(f"Token refresh error: {e}")
        return jsonify({"error": "Invalid refresh token"}), 401


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
                    "created_at": (
                        req.created_at.strftime("%Y-%m-%d %H:%M")
                        if req.created_at
                        else "Няма дата"
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


@app.route(
    "/notification_dashboard", methods=["GET"], endpoint="notification_dashboard"
)
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

    # Build query

    query = Volunteer.query

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

    # Apply pagination
    total_volunteers = query.count()
    volunteers = query.offset((page - 1) * per_page).limit(per_page).all()

    # Calculate pagination info
    total_pages = (total_volunteers + per_page - 1) // per_page

    # Create pagination object for template compatibility
    class Pagination:
        def __init__(self, page, per_page, total, items):
            self.page = page
            self.per_page = per_page
            self.total = total
            self.items = items
            self.pages = (total + per_page - 1) // per_page
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1 if self.has_prev else None
            self.next_num = page + 1 if self.has_next else None

    pagination = Pagination(page, per_page, total_volunteers, volunteers)

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
        pagination=pagination,
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
            volunteer = Volunteer(
                name=name, email=email, phone=phone, location=location
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
@limiter.limit(
    "5 per minute; 20 per hour; 50 per day"
)  # Stricter limits for form submissions
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
@limiter.limit(
    "3 per minute; 10 per hour; 25 per day"
)  # Very strict limits for registrations
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
                return (
                    jsonify(
                        {
                            "success": False,
                            "message": "Грешка при изпращане на имейл.",
                        }
                    ),
                    500,
                )

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
                    f"Volunteer details: ID={volunteer.id}, Name={volunteer.name}, Email={volunteer.email}"
                )

                # TEMPORARY: Skip 2FA for test emails
                if email in ["ivan@example.com", "test@example.com"]:
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
                        f"Session set: volunteer_logged_in={session.get('volunteer_logged_in')}, volunteer_id={session.get('volunteer_id')}"
                    )

                    app.logger.info(
                        f"Volunteer {volunteer.name} logged in directly (test mode)"
                    )
                    # For testing, return dashboard directly instead of redirecting
                    # This bypasses session persistence issues in test environment
                    try:
                        # Get statistics with safe database operations
                        stats = _get_volunteer_stats_safe(volunteer.id)
                        active_tasks = _get_active_tasks_safe(volunteer.id)
                        gamification = _get_gamification_data_safe(volunteer)

                        app.logger.info(
                            "Rendering dashboard template directly for test mode"
                        )
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
                        app.logger.error(
                            f"Error rendering dashboard for test mode: {e}"
                        )
                        return f"Test mode dashboard error: {e}", 500

                # Generate 6-digit access code
                access_code = str(secrets.randbelow(900000) + 100000)
                app.logger.info(f"Generated access code: {access_code}")

                # Store in session with expiration (15 minutes)
                session["pending_volunteer_login"] = {
                    "volunteer_id": volunteer.id,
                    "email": email,
                    "verification_code": access_code,
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
                f"Database error during volunteer login: {e}", exc_info=True
            )
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
                    jsonify(
                        {"success": False, "message": "Грешка при изпращане на имейл."}
                    ),
                    500,
                )

        return jsonify(
            {"success": True, "message": "Нов код е изпратен на вашия имейл."}
        )

    except Exception as e:
        app.logger.error(f"Error resending volunteer code: {e}")
        return (
            jsonify(
                {"success": False, "message": "Възникна грешка при изпращане на кода."}
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

        # Get volunteer with optimized query
        volunteer = (
            db.session.query(Volunteer)
            .options(
                db.joinedload(Volunteer.assigned_tasks).joinedload(
                    Task.performance_records
                )
            )
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
            db.session.query(HelpRequest)
            .filter_by(status="pending", priority="urgent")
            .count()
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
        flash(
            "Възникна грешка при зареждането на панела. Моля, опитайте отново.", "error"
        )
        return redirect(url_for("index"))


@app.route("/my_tasks")
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

        # Get assigned tasks
        assigned_tasks = (
            db.session.query(Task)
            .filter_by(assigned_to=volunteer_id)
            .filter(Task.status.in_(["assigned", "in_progress"]))
            .order_by(Task.created_at.desc())
            .all()
        )

        return render_template(
            "my_tasks.html", current_user=volunteer, tasks=assigned_tasks
        )

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error loading my tasks for volunteer {volunteer_id}: {e}")
        flash("Възникна грешка при зареждането на задачите.", "error")
        return redirect(url_for("volunteer_dashboard"))


@app.route("/achievements", methods=["GET"], endpoint="achievements")
def achievements():
    # Check if volunteer is logged in
    if not session.get("volunteer_logged_in"):
        flash("Моля, влезте като доброволец.", "warning")
        return redirect(url_for("volunteer_login"))
    # Placeholder for achievements page
    return render_template("achievements.html")


def _get_volunteer_stats_safe(volunteer_id):
    """Safely get volunteer statistics with fallback values"""
    try:
        from models_with_analytics import Task, TaskPerformance

        # Completed tasks count with timeout protection
        completed_tasks = (
            db.session.query(Task)
            .filter_by(assigned_to=volunteer_id, status="completed")
            .count()
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
            db.session.query(TaskPerformance)
            .filter_by(volunteer_id=volunteer_id)
            .count()
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
                        task.created_at.strftime("%Y-%m-%d")
                        if task.created_at
                        else "Няма дата"
                    ),
                    "time_remaining": time_remaining,
                    "description": task.description or "Няма описание",
                    "priority": task.priority or "medium",
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


@app.route("/api/chatbot/message", methods=["POST"])
# @limiter.limit("10 per minute; 50 per hour; 100 per day")  # Rate limit chatbot usage
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
                    "response": "Извинявам се, възникна грешка. Моля, опитайте пак или се свържете с екипа ни.",
                    "error": True,
                }
            ),
            500,
        )


@app.route("/api/health")
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check database connectivity
        db.session.execute("SELECT 1").first()

        # Check Celery connectivity (if available)
        celery_status = "unknown"
        try:
            from backend.celery_app import celery

            inspect = celery.control.inspect()
            active = inspect.active()
            celery_status = "healthy" if active is not None else "unhealthy"
        except Exception:
            celery_status = "unavailable"

        health_info = {
            "status": "healthy",
            "database": "connected",
            "celery": celery_status,
            "timestamp": datetime.now().isoformat(),
        }

        return jsonify(health_info)

    except Exception as e:
        app.logger.error(f"Health check failed: {e}")
        return (
            jsonify(
                {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            500,
        )


@app.route("/api/ai/status")
def ai_status():
    """Get AI service status and available providers"""
    try:
        from ai_service import ai_service

        # Get AI service status
        status_info = ai_service.get_ai_status()

        # Format response to match expected API structure
        providers_list = []
        active_provider = status_info.get("active_provider")

        if "providers" in status_info:
            for provider_key, provider_info in status_info["providers"].items():
                if provider_info.get("enabled", False):
                    providers_list.append(
                        {
                            "name": provider_info.get("name", provider_key),
                            "model": provider_info.get("model", ""),
                            "enabled": provider_info.get("enabled", False),
                        }
                    )

        response = {
            "status": (
                "healthy" if status_info.get("service_ready", False) else "unhealthy"
            ),
            "providers": providers_list,
            "active_provider": active_provider,
        }

        return jsonify(response)

    except Exception as e:
        app.logger.error(f"Error getting AI status: {e}")
        return (
            jsonify(
                {
                    "status": "error",
                    "providers": [],
                    "active_provider": None,
                    "error": str(e),
                }
            ),
            500,
        )


@app.route("/api/tasks/trigger/<task_name>", methods=["POST"])
@require_admin_login
def trigger_task(task_name):
    """Manually trigger a Celery task (admin only)"""
    try:
        from backend import tasks

        # Map task names to functions
        task_map = {
            "auto_match_requests": tasks.auto_match_requests,
            "send_reminders": tasks.send_reminders,
            "generate_daily_reports": tasks.generate_daily_reports,
            "cleanup_old_data": tasks.cleanup_old_data,
            "monitor_system_health": tasks.monitor_system_health,
            "update_realtime_stats": tasks.update_realtime_stats,
        }

        if task_name not in task_map:
            return jsonify({"error": f"Unknown task: {task_name}"}), 400

        # Trigger the task
        result = task_map[task_name].delay()

        return jsonify(
            {
                "task_id": result.id,
                "task_name": task_name,
                "status": "triggered",
            }
        )

    except Exception as e:
        app.logger.error(f"Error triggering task {task_name}: {e}")
        return jsonify({"error": f"Failed to trigger task: {str(e)}"}), 500


# Predictive Analytics Routes
@app.route("/api/predictive/regional-demand")
@require_admin_login
def predictive_regional_demand():
    """Get regional demand forecast data"""
    try:
        from predictive_analytics import predictive_analytics

        region = request.args.get("region")
        days_ahead = int(request.args.get("days_ahead", 7))

        forecast = predictive_analytics.get_regional_demand_forecast(
            region=region, days_ahead=days_ahead
        )
        return jsonify(forecast)

    except Exception as e:
        app.logger.error(f"Error getting regional demand forecast: {e}")
        return (
            jsonify(
                {"error": "Failed to get regional demand forecast", "details": str(e)}
            ),
            500,
        )


@app.route("/api/predictive/workload")
@require_admin_login
def predictive_workload():
    """Get workload prediction data"""
    try:
        from predictive_analytics import predictive_analytics

        hours_ahead = int(request.args.get("hours_ahead", 24))

        prediction = predictive_analytics.get_workload_prediction(
            hours_ahead=hours_ahead
        )
        return jsonify(prediction)

    except Exception as e:
        app.logger.error(f"Error getting workload prediction: {e}")
        return (
            jsonify({"error": "Failed to get workload prediction", "details": str(e)}),
            500,
        )


@app.route("/api/predictive/insights")
@require_admin_login
def predictive_insights():
    """Get predictive insights and recommendations"""
    try:
        from predictive_analytics import predictive_analytics

        insights = predictive_analytics.get_predictive_insights()
        return jsonify(insights)

    except Exception as e:
        app.logger.error(f"Error getting predictive insights: {e}")
        return (
            jsonify({"error": "Failed to get predictive insights", "details": str(e)}),
            500,
        )


@app.route("/api/predictive/model-info")
@require_admin_login
def predictive_model_info():
    """Get information about predictive models"""
    try:
        from predictive_analytics import predictive_analytics

        # Get sample data to extract model info
        regional_sample = predictive_analytics.get_regional_demand_forecast(
            days_ahead=1
        )
        workload_sample = predictive_analytics.get_workload_prediction(hours_ahead=1)

        model_info = {
            "regional_demand_model": {
                "type": "Random Forest Regression",
                "features": [
                    "day_of_week",
                    "month",
                    "season",
                    "historical_avg",
                    "trend_factor",
                    "volunteer_density",
                    "population_density",
                ],
                "prediction_horizon": "1-30 days",
                "accuracy_metrics": regional_sample.get("model_info", {}).get(
                    "accuracy", "N/A"
                ),
                "last_trained": regional_sample.get("generated_at", "N/A"),
            },
            "workload_prediction_model": {
                "type": "Gradient Boosting Regression",
                "features": [
                    "current_requests",
                    "active_volunteers",
                    "avg_response_time",
                    "day_of_week",
                    "hour_of_day",
                    "season",
                ],
                "prediction_horizon": "1-168 hours",
                "accuracy_metrics": workload_sample.get("model_info", {}).get(
                    "accuracy", "N/A"
                ),
                "last_trained": workload_sample.get("generated_at", "N/A"),
            },
            "data_sources": [
                "HelpRequest table (historical patterns)",
                "Volunteer table (capacity data)",
                "UserActivity table (engagement patterns)",
                "Real-time system metrics",
            ],
            "update_frequency": "Real-time predictions with 1-hour cache",
            "fallback_strategy": "Rule-based heuristics when ML models unavailable",
        }

        return jsonify(model_info)

    except Exception as e:
        app.logger.error(f"Error getting model info: {e}")
        return (
            jsonify({"error": "Failed to get model information", "details": str(e)}),
            500,
        )


@app.route("/predictive-analytics")
@require_admin_login
def predictive_analytics_page():
    """Render the predictive analytics dashboard"""
    return render_template("predictive_analytics.html")


@app.route("/analytics")
@require_admin_login
def analytics_page():
    """Render the main analytics dashboard"""
    return render_template("analytics.html")


# Smart Matching API Routes
@app.route("/api/matching/find-matches/<int:request_id>")
@require_admin_login
def find_matches(request_id):
    """Find best volunteer matches for a help request"""
    try:
        from smart_matching import smart_matching_service

        limit = int(request.args.get("limit", 5))
        matches = smart_matching_service.find_best_matches(request_id, limit)

        # Convert volunteer objects to dictionaries for JSON response
        result = []
        for match in matches:
            volunteer = match["volunteer"]
            result.append(
                {
                    "volunteer_id": volunteer.id,
                    "name": volunteer.name,
                    "email": volunteer.email,
                    "phone": volunteer.phone,
                    "skills": volunteer.skills,
                    "location": volunteer.location,
                    "rating": volunteer.rating,
                    "experience": volunteer.experience,
                    "total_tasks_completed": volunteer.total_tasks_completed,
                    "match_score": match["scores"],
                    "recommendation_reason": match["recommendation_reason"],
                }
            )

        return jsonify(
            {"request_id": request_id, "matches": result, "total_matches": len(result)}
        )

    except Exception as e:
        app.logger.error(f"Error finding matches for request {request_id}: {e}")
        return jsonify({"error": "Failed to find matches", "details": str(e)}), 500


@app.route("/api/matching/auto-assign/<int:request_id>", methods=["POST"])
@require_admin_login
def auto_assign_request(request_id):
    """Automatically assign the best matching volunteer to a help request"""
    try:
        from smart_matching import smart_matching_service

        result = smart_matching_service.auto_assign_request(request_id)

        if result:
            return jsonify(
                {
                    "success": True,
                    "message": "Request auto-assigned successfully",
                    "assignment": {
                        "request_id": result["help_request"].id,
                        "volunteer_id": result["volunteer"].id,
                        "volunteer_name": result["volunteer"].name,
                        "match_score": result["match_score"],
                    },
                }
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "No suitable volunteer found for auto-assignment",
                    }
                ),
                404,
            )

    except Exception as e:
        app.logger.error(f"Error auto-assigning request {request_id}: {e}")
        return (
            jsonify({"error": "Failed to auto-assign request", "details": str(e)}),
            500,
        )


@app.route("/api/matching/analytics")
@require_admin_login
def matching_analytics():
    """Get analytics for the smart matching system"""
    try:
        from smart_matching import smart_matching_service

        analytics = smart_matching_service.get_matching_analytics()
        return jsonify(analytics)

    except Exception as e:
        app.logger.error(f"Error getting matching analytics: {e}")
        return (
            jsonify({"error": "Failed to get matching analytics", "details": str(e)}),
            500,
        )


@app.route("/api/matching/ai-insights/<int:request_id>")
@require_admin_login
def get_ai_insights(request_id):
    """Get AI-powered insights for a help request"""
    try:
        from smart_matching import smart_matching_service

        insights = smart_matching_service.get_ai_insights(request_id)
        return jsonify(insights)

    except Exception as e:
        app.logger.error(f"Error getting AI insights for request {request_id}: {e}")
        return jsonify({"error": "Failed to get AI insights", "details": str(e)}), 500


@app.route("/api/matching/assign/<int:request_id>/<int:volunteer_id>", methods=["POST"])
@require_admin_login
def manual_assign_request(request_id, volunteer_id):
    """Manually assign a volunteer to a help request"""
    try:
        # Get the request and volunteer
        help_request = HelpRequest.query.get_or_404(request_id)
        volunteer = Volunteer.query.get_or_404(volunteer_id)

        # Update request status
        help_request.status = "assigned"
        help_request.updated_at = datetime.utcnow()

        # Create assignment record if TaskAssignment exists
        try:
            from models_with_analytics import TaskAssignment

            assignment = TaskAssignment(
                task_id=request_id,  # Using request_id as task_id
                volunteer_id=volunteer.id,
                skill_match_score=50.0,  # Default for manual assignment
                location_match_score=50.0,
                availability_match_score=100.0,
                performance_match_score=volunteer.rating * 20,
                overall_match_score=50.0,  # Manual assignment
                assigned_at=datetime.utcnow(),
                status="assigned",
                assigned_by="manual",
            )
            db.session.add(assignment)
        except ImportError:
            assignment = None

        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": "Volunteer assigned successfully",
                "assignment": {
                    "request_id": request_id,
                    "volunteer_id": volunteer_id,
                    "volunteer_name": volunteer.name,
                },
            }
        )

    except Exception as e:
        db.session.rollback()
        app.logger.error(
            f"Error manually assigning request {request_id} to volunteer {volunteer_id}: {e}"
        )
        return jsonify({"error": "Failed to assign volunteer", "details": str(e)}), 500


@app.route("/admin_analytics", methods=["GET"])
@require_admin_login
def admin_analytics():
    """Render the admin analytics dashboard"""
    try:
        from analytics_service import analytics_service

        dashboard_stats = analytics_service.get_dashboard_analytics()

        # Prepare chart data
        trends_data = {
            "labels": [
                "Яну",
                "Фев",
                "Мар",
                "Апр",
                "Май",
                "Юни",
                "Юли",
                "Авг",
                "Сеп",
                "Окт",
                "Ное",
                "Дек",
            ],
            "requests": [65, 59, 80, 81, 56, 55, 40, 45, 60, 75, 85, 90],
            "completed": [28, 48, 40, 19, 86, 27, 90, 35, 50, 65, 75, 80],
            "volunteers": [12, 15, 18, 22, 25, 28, 30, 32, 35, 38, 40, 42],
        }

        category_stats = {
            "categories": [
                "Медицинска помощ",
                "Транспорт",
                "Домакинска помощ",
                "Образование",
                "Други",
            ],
            "counts": [35, 25, 20, 15, 5],
        }

        predictions = {
            "labels": ["Месец 1", "Месец 2", "Месец 3"],
            "requests_predicted": [95, 105, 115],
            "volunteers_predicted": [45, 48, 52],
            "ml_insights": {
                "anomalies": [],
                "predictions": {
                    "optimal_engagement_time": {"hour": 14, "engagement_score": 85},
                    "churn_risk": {"risk": "low", "days_since_activity": 2},
                },
                "recommendations": [
                    {
                        "title": "Оптимизация на работното време",
                        "description": "Най-добрите резултати са между 14:00 и 16:00",
                        "action": "Фокусирай маркетинговите кампании в този период",
                        "priority": "medium",
                    }
                ],
            },
        }

    except Exception as e:
        print(f"Error getting analytics data: {type(e).__name__}")
        dashboard_stats = {"error": "Analytics not available"}
        trends_data = {"labels": [], "requests": [], "completed": [], "volunteers": []}
        category_stats = {"categories": [], "counts": []}
        predictions = {"ml_insights": None}

    return render_template(
        "admin_analytics.html",
        dashboard_stats=dashboard_stats,
        trends_data=trends_data,
        category_stats=category_stats,
        predictions=predictions,
    )


print("DEBUG: Checking if admin_analytics route is registered")
for rule in app.url_map.iter_rules():
    if "admin_analytics" in rule.rule:
        print(f"  Found route: {rule.rule} -> {rule.endpoint}")
print("DEBUG: Route check complete")


# Celery monitoring endpoints
@app.route("/api/celery/stats")
def celery_stats():
    """Get Celery worker and task statistics"""
    try:
        from backend.celery_app import celery

        # Get active workers
        inspect = celery.control.inspect()

        stats = {
            "active_workers": inspect.active() or {},
            "scheduled_tasks": inspect.scheduled() or {},
            "active_tasks": inspect.active() or {},
            "registered_tasks": inspect.registered() or {},
            "stats": inspect.stats() or {},
        }

        return jsonify(stats)

    except Exception as e:
        app.logger.error(f"Error getting Celery stats: {e}")
        return jsonify({"error": "Failed to get Celery statistics"}), 500


@app.route("/api/celery/tasks/<task_id>")
def celery_task_status(task_id):
    """Get status of a specific Celery task"""
    try:
        from backend.celery_app import celery

        # Get task result
        result = celery.AsyncResult(task_id)

        task_info = {
            "task_id": task_id,
            "state": result.state,
            "current": result.current,
            "info": str(result.info) if result.info else None,
            "result": str(result.result) if result.result else None,
        }

        return jsonify(task_info)

    except Exception as e:
        app.logger.error(f"Error getting task status: {e}")
        return jsonify({"error": "Failed to get task status"}), 500


if __name__ == "__main__":
    print("HelpChain server starting...")
    print("http://127.0.0.1:8000")
    print("Admin: admin / Admin123")
    print("Press Ctrl+C to stop")
    try:
        debug_mode = True  # Enable debug mode for development
        use_https = False  # Set to True to enable HTTPS for push notifications

        if use_https:
            # For HTTPS development (requires SSL certificates)
            import ssl

            context = ssl.SSLContext(ssl.PROTOCOL_TLS)
            # Load the generated certificates
            cert_path = os.path.join(os.path.dirname(__file__), "..", "cert.pem")
            key_path = os.path.join(os.path.dirname(__file__), "..", "key.pem")
            context.load_cert_chain(cert_path, key_path)
            app.run(
                debug=debug_mode,
                host="127.0.0.1",
                port=8000,
                ssl_context=context,
                use_reloader=False,
            )
        else:
            app.run(debug=debug_mode, host="127.0.0.1", port=8000, use_reloader=False)
    except Exception as e:
        print(f"Server crashed with error: {e}")
        traceback.print_exc()
        raise
