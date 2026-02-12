import os
from datetime import timedelta

from dotenv import load_dotenv

# === Project base (root of HelpChain.bg) ===
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Load .env ONCE, from project root
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    # --- Core ---
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    PROPAGATE_EXCEPTIONS = True  # Enable full tracebacks during MFA debug
    DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1")

    # --- Session / cookies hardening ---
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "").lower() in (
        "true",
        "1",
        "yes",
    )
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=6)
    SESSION_REFRESH_EACH_REQUEST = True

    # --- CSRF ---
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 60 * 60 * 2  # 2 hours

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ✅ Admin credentials (from .env)
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

    # ✅ Database
    # Prefer explicit env; else Render/Heroku DATABASE_URL; else project instance/app.db (absolute to avoid CWD drift)
    INSTANCE_PATH = os.path.join(BASE_DIR, "instance")
    DEFAULT_SQLITE_PATH = os.path.join(INSTANCE_PATH, "app.db")
    _db_url_env = os.getenv("SQLALCHEMY_DATABASE_URI") or os.getenv("DATABASE_URL")
    if _db_url_env:
        # Allow %TEMP%, $HOME, etc. in dev env vars
        _db_url_env = os.path.expandvars(_db_url_env)
    SQLALCHEMY_DATABASE_URI = _db_url_env or f"sqlite:///{DEFAULT_SQLITE_PATH}"

    # Rate limit headers (useful with ProxyFix and real client IPs)
    RATELIMIT_HEADERS_ENABLED = True

    # --- Mail ---
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.mailtrap.io")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 2525))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() in ("true", "1")
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "false").lower() in ("true", "1")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", os.getenv("MAILTRAP_USERNAME"))
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", os.getenv("MAILTRAP_PASSWORD"))
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "contact@helpchain.live")
    MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "HelpChain")
    MAIL_REPLY_TO = os.getenv("MAIL_REPLY_TO", MAIL_DEFAULT_SENDER)

    # --- Optional / misc ---
    NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
    QR_CODE_SIZE = int(os.getenv("QR_CODE_SIZE", 250))
    ALLOWED_HOSTS = [
        h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()
    ]
    PUBLIC_BASE_URL = (os.getenv("PUBLIC_BASE_URL", "") or "").strip()

    # Dev-only volunteer bypass (disabled by default)
    VOLUNTEER_DEV_BYPASS_ENABLED = os.getenv("VOLUNTEER_DEV_BYPASS_ENABLED", "0") == "1"
    VOLUNTEER_DEV_BYPASS_EMAIL = (
        (os.getenv("VOLUNTEER_DEV_BYPASS_EMAIL") or "").strip().lower()
    )

    # --- MFA ---
    MFA_ENABLED = os.getenv("MFA_ENABLED", "true").lower() in ("true", "1", "yes")
    MFA_SESSION_KEY = os.getenv("MFA_SESSION_KEY", "mfa_ok")
    MFA_SESSION_TTL_MIN = int(os.getenv("MFA_SESSION_TTL_MIN", 30))
    MFA_VERIFY_MAX_ATTEMPTS = int(os.getenv("MFA_VERIFY_MAX_ATTEMPTS", 8))
    MFA_VERIFY_LOCK_MIN = int(os.getenv("MFA_VERIFY_LOCK_MIN", 10))

    # --- Web Push (VAPID) ---
    VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY")
    VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY")
    VAPID_SUBJECT = os.getenv("VAPID_SUBJECT", "mailto:admin@example.com")

    # --- JWT for API ---
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY")

    # --- JWT hardening ---
    JWT_ISSUER = "helpchain"
    JWT_AUDIENCE = "helpchain-api"
    JWT_ALG = "HS256"  # switch to RS256 when keypair available
    JWT_ACCESS_TTL_SECONDS = 900  # 15 minutes
    JWT_REFRESH_TTL_SECONDS = 2592000  # 30 days
    JWT_CLOCK_SKEW_SECONDS = 30
    JWT_REQUIRE_JTI = True

    # --- CORS ---
    CORS_ALLOWED_ORIGINS = [
        "http://127.0.0.1:5000",
        "http://localhost:5000",
        # "https://helpchain.live",  # prod
    ]

    # --- i18n / Babel ---
    # Keep in sync with app factory (FR-first).
    BABEL_DEFAULT_LOCALE = "fr"
    BABEL_DEFAULT_TIMEZONE = "Europe/Paris"


class DevConfig(Config):
    SESSION_COOKIE_SECURE = False
    # Dev-only volunteer bypass: honor env (default off)
    VOLUNTEER_DEV_BYPASS_ENABLED = os.getenv("VOLUNTEER_DEV_BYPASS_ENABLED", "0") == "1"
    VOLUNTEER_DEV_BYPASS_EMAIL = (
        (os.getenv("VOLUNTEER_DEV_BYPASS_EMAIL") or "").strip().lower()
    )


class ProdConfig(Config):
    SESSION_COOKIE_SECURE = True
