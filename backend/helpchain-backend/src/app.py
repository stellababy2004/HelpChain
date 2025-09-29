import os
from flask import Flask, render_template, request, redirect, url_for
from routes.api import api_bp
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel, get_locale
from flask_mail import Mail
from flask_migrate import Migrate

db = SQLAlchemy()
babel = Babel()
mail = Mail()
migrate = Migrate()


def create_app(config_object=None):
    # Задаваме абсолютни пътища към templates/static (относно този файл)
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    templates_dir = os.path.join(base, "templates")
    static_dir = os.path.join(base, "static")

    app = Flask(__name__, template_folder=templates_dir, static_folder=static_dir)
    app.config.from_object(config_object or Config)

    # fallback за база при тестове (ако още не е зададена)
    app.config.setdefault(
        "SQLALCHEMY_DATABASE_URI",
        os.environ.get("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:"),
    )

    # инициализация на разширения (db, babel, mail, migrate) ...
    db.init_app(app)
    babel.init_app(app)

    # expose safe get_locale to Jinja templates so base.html can call get_locale()
    def _safe_get_locale():
        try:
            return get_locale()
        except Exception:
            # fallback: връща низ или обект, който шаблоните очакват (може да е просто 'bg')
            return "bg"

    app.jinja_env.globals["get_locale"] = _safe_get_locale

    # expose builtins used by templates
    app.jinja_env.globals["str"] = str
    app.jinja_env.globals["getattr"] = getattr

    # Регистрираме API blueprint под /api (тестовете очакват /api/some_endpoint)
    app.register_blueprint(api_bp, url_prefix="/api")

    # Ако няма index шаблон/маршрут в appy, осигуряваме прост home route
    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/set_language", methods=["POST"])
    def set_language():
        # вземи избрания език от формата и го запиши в cookie, после редирект към реферера
        lang = request.form.get("language", "bg")
        resp = redirect(request.referrer or url_for("index"))
        resp.set_cookie("language", lang, max_age=30 * 24 * 3600)
        return resp

    return app


# създаваме default 'app' за тестове/локално стартиране
app = create_app(Config)

if __name__ == "__main__":
    app.run(debug=True)
