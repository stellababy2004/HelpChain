# Инициализация на пакета src

from .app import app as app
from .config import Config as Config
from .routes.api import api_bp as api
from .controllers.helpchain_controller import HelpChainController as HelpChainController
from .services.ngrok_service import NgrokService as NgrokService
from .utils.qr_generator import generate_qr_code as generate_qr_code

# НЕ дефинираме нов Blueprint тук — използваме този от routes/api.py
# from flask import Blueprint
# api_bp = Blueprint("api", __name__, url_prefix="/api")

__all__ = [
    "app",
    "Config",
    "api",
    "HelpChainController",
    "NgrokService",
    "generate_qr_code",
]
