import os
from dotenv import load_dotenv

# === Project base (root of HelpChain.bg) ===
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Load .env ONCE, from project root
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    # --- Core ---
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # DEV: no expiry (fixes “token expired”)
    SESSION_PERMANENT = True
    DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ✅ Admin credentials (from .env)
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

    # ✅ Flask-canonical DB location → instance/app.db
    # If env var exists, we respect it (prod / CI),
    # otherwise Flask will resolve sqlite:///app.db → instance/app.db
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "SQLALCHEMY_DATABASE_URI",
        "sqlite:///app.db"
    )

    # --- Mail ---
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.mailtrap.io")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 2525))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() in ("true", "1")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", os.getenv("MAILTRAP_USERNAME"))
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", os.getenv("MAILTRAP_PASSWORD"))
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "contact@helpchain.live")

    # --- Optional / misc ---
    NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
    QR_CODE_SIZE = int(os.getenv("QR_CODE_SIZE", 250))
    ALLOWED_HOSTS = (
        [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()]
    )

