import os
import sys

# Ensure repo root is on sys.path for module imports
REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from backend.helpchain_backend.src.app import create_app

app = create_app(
    {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    }
)

c = app.test_client()
for url in ["/categories", "/category_help/food", "/admin/login"]:
    r = c.get(url)
    print(url, r.status_code)
