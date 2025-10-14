import os
import sys
from pathlib import Path
import pytest

# Добавяме helpchain-backend (родител на папката src) в началото на sys.path,
# за да може `import src` да работи
_root = os.path.dirname(__file__)
_src_parent = os.path.join(_root, "helpchain-backend")
if os.path.isdir(_src_parent):
    sys.path.insert(0, _src_parent)

# Добавя текущата папка (backend) в sys.path така че 'appy' да се импортира директно
HERE = Path(__file__).parent.resolve()
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

# Import models_with_analytics first to ensure Task model is available for relationships
try:
    import models_with_analytics  # noqa: F401
except ImportError:
    pass


@pytest.fixture(scope="session", autouse=True)
def setup_models():
    """Setup models before any tests run"""
    try:
        import models_with_analytics  # noqa: F401
    except ImportError:
        pass


@pytest.fixture
def app():
    """Create and configure a test app instance."""
    try:
        from appy import app

        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False  # Disable CSRF for testing
        return app
    except ImportError:
        # Fallback if appy import fails
        from flask import Flask

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "test_key"
        return app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()
