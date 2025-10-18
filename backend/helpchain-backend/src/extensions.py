from flask_babel import Babel
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
babel = Babel()
mail = Mail()
