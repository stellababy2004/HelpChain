import os
from dotenv import load_dotenv

# === Project base (root of HelpChain.bg) ===
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Load .env ONCE, from project root
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    # --- Core ---
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    PROPAGATE_EXCEPTIONS = True  # Enable full tracebacks during MFA debug
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # DEV: no expiry (fixes "token expired")
    SESSION_PERMANENT = True
    DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ✅ Admin credentials (from .env)
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

    # ✅ Database
    # Prefer explicit SQLALCHEMY_DATABASE_URI; fall back to Render's DATABASE_URL; else sqlite app.db.
    _db_url = (
        os.getenv("SQLALCHEMY_DATABASE_URI")
        or os.getenv("DATABASE_URL")
        or "sqlite:///app.db"
    )
    SQLALCHEMY_DATABASE_URI = _db_url

    # --- Mail ---
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.mailtrap.io")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 2525))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() in ("true", "1")
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "false").lower() in ("true", "1")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", os.getenv("MAILTRAP_USERNAME"))
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", os.getenv("MAILTRAP_PASSWORD"))
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "contact@helpchain.live")

    # --- Optional / misc ---
    NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
    QR_CODE_SIZE = int(os.getenv("QR_CODE_SIZE", 250))
    ALLOWED_HOSTS = (
        [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()]
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

