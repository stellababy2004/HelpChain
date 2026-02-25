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
    ADMIN_NOTIFY_EMAIL = os.getenv("ADMIN_NOTIFY_EMAIL", "")

    # ✅ Database
    # Prefer explicit env; else Render/Heroku DATABASE_URL; else project instance/app.db (absolute to avoid CWD drift)
    INSTANCE_PATH = os.path.join(BASE_DIR, "instance")
    DEFAULT_SQLITE_PATH = os.path.join(INSTANCE_PATH, "app.db")
    _db_path_env = os.getenv("HC_DB_PATH")
    db_url = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI") or ""
    _db_url_env = db_url
    # normalize scheme for SQLAlchemy
    if _db_url_env.startswith("postgres://"):
        _db_url_env = _db_url_env.replace("postgres://", "postgresql://", 1)
    # explicit psycopg v3 driver for Python 3.13 compatibility on Render
    if _db_url_env.startswith("postgresql://") and "+psycopg" not in _db_url_env:
        _db_url_env = _db_url_env.replace("postgresql://", "postgresql+psycopg://", 1)
    if _db_url_env:
        # Allow %TEMP%, $HOME, etc. in dev env vars
        _db_url_env = os.path.expandvars(_db_url_env)
    if _db_path_env:
        _db_path_env = os.path.expandvars(_db_path_env).replace("\\", "/")
    SQLALCHEMY_DATABASE_URI = (
        (f"sqlite:///{_db_path_env}" if _db_path_env else None)
        or _db_url_env
        or f"sqlite:///{DEFAULT_SQLITE_PATH}"
    )

    # Rate limit headers (useful with ProxyFix and real client IPs)
    RATELIMIT_HEADERS_ENABLED = True
    TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "false").lower() in (
        "true",
        "1",
        "yes",
    )
    PROXY_FIX_X_FOR = int(os.getenv("PROXY_FIX_X_FOR", "1"))
    PROXY_FIX_X_PROTO = int(os.getenv("PROXY_FIX_X_PROTO", "1"))
    PROXY_FIX_X_HOST = int(os.getenv("PROXY_FIX_X_HOST", "1"))

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
    PRO_LEADS_NOTIFY_TO = os.getenv("PRO_LEADS_NOTIFY_TO", "")
    MAIL_DEDUPE_MINUTES = int(os.getenv("MAIL_DEDUPE_MINUTES", "10"))
    MAIL_RL_WINDOW_MINUTES = int(os.getenv("MAIL_RL_WINDOW_MINUTES", "30"))
    MAIL_RL_MAX_SENT = int(os.getenv("MAIL_RL_MAX_SENT", "3"))
    MAIL_HASH_SALT = os.getenv("MAIL_HASH_SALT", "")

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

    # --- Analytics (Plausible) ---
    PLAUSIBLE_ENABLED = os.getenv("PLAUSIBLE_ENABLED", "0") == "1"
    PLAUSIBLE_DOMAIN = os.getenv("PLAUSIBLE_DOMAIN", "helpchain.live")
    PLAUSIBLE_SCRIPT_URL = os.getenv(
        "PLAUSIBLE_SCRIPT_URL", "https://plausible.io/js/script.js"
    )
    # Optional override for self-hosted API endpoint base host, e.g.
    # https://plausible.helpchain.live
    PLAUSIBLE_API_HOST = (os.getenv("PLAUSIBLE_API_HOST", "") or "").strip()


class DevConfig(Config):
    SESSION_COOKIE_SECURE = False
    # Dev-only volunteer bypass: honor env (default off)
    VOLUNTEER_DEV_BYPASS_ENABLED = os.getenv("VOLUNTEER_DEV_BYPASS_ENABLED", "0") == "1"
    VOLUNTEER_DEV_BYPASS_EMAIL = (
        (os.getenv("VOLUNTEER_DEV_BYPASS_EMAIL") or "").strip().lower()
    )


class ProdConfig(Config):
    SESSION_COOKIE_SECURE = True
    # Never allow volunteer dev bypass in production, even if env var is set.
    VOLUNTEER_DEV_BYPASS_ENABLED = False
    VOLUNTEER_DEV_BYPASS_EMAIL = ""
