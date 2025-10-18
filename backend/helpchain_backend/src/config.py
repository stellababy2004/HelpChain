import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "default_secret_key"
    DEBUG = os.environ.get("DEBUG", "False").lower() in ["true", "1"]
    DATABASE_URI = os.environ.get("DATABASE_URI") or "sqlite:///app.db"
    NGROK_AUTH_TOKEN = os.environ.get("NGROK_AUTH_TOKEN")
    QR_CODE_SIZE = int(os.environ.get("QR_CODE_SIZE", 250))  # Size in pixels
    ALLOWED_HOSTS = (
        os.environ.get("ALLOWED_HOSTS", "").split(",")
        if os.environ.get("ALLOWED_HOSTS")
        else []
    )
    MAIL_SERVER = os.environ.get(
        "MAIL_SERVER", "smtp.mailtrap.io"
    )  # Mailtrap за тестове
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 2525))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "True").lower() in ["true", "1"]
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", os.environ.get("MAILTRAP_USERNAME"))
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", os.environ.get("MAILTRAP_PASSWORD"))
    MAIL_DEFAULT_SENDER = os.environ.get(
        "MAIL_DEFAULT_SENDER", "contact@helpchain.live"
    )
