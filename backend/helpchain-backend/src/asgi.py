from asgiref.wsgi import WsgiToAsgi
from .app import app as flask_app

asgi_app = WsgiToAsgi(flask_app)
