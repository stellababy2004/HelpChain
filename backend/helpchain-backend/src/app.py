from flask import Flask
from routes.api import api_bp
from config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Регистрирай API маршрути
    app.register_blueprint(api_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000)
