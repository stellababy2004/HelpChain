from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel
from flask_mail import Mail
from flask_migrate import Migrate

# инстанции на разширенията (инициализацията ще се направи в app.create_app)
db = SQLAlchemy()
babel = Babel()
mail = Mail()
migrate = Migrate()
