from flask_babel import Babel
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy

# Optional imports - handle gracefully if not available
try:
    from flask_caching import Cache

    FLASK_CACHING_AVAILABLE = True
except ImportError:
    FLASK_CACHING_AVAILABLE = False
    Cache = None

db = SQLAlchemy()
babel = Babel()
mail = Mail()

# Initialize cache conditionally
if FLASK_CACHING_AVAILABLE:
    cache = Cache()
else:
    cache = None
