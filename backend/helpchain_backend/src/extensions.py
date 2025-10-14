from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel
from flask_mail import Mail
from flask_migrate import Migrate
from flask_login import LoginManager

db = SQLAlchemy()
babel = Babel()
mail = Mail()
migrate = Migrate()
login_manager = LoginManager()
