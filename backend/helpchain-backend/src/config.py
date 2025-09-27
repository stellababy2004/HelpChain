import os


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
