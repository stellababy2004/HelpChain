from flask_babel import Babel
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
babel = Babel()
mail = Mail()
migrate = Migrate()
login_manager = LoginManager()
