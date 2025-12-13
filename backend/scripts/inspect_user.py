import os
import sys

# Ensure running the script from the repo root can import the `backend` package.
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
# Also add the `backend` package directory explicitly to help resolve imports
backend_dir = os.path.join(repo_root, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from backend import models
from backend.app import app

with app.app_context():
    u = models.User.query.filter_by(username="testuser").first()
    if not u:
        print("User testuser не е намерен")
    else:
        print("id=", getattr(u, "id", None))
        print("username=", getattr(u, "username", None))
        print("email=", getattr(u, "email", None))
        print("role=", getattr(u, "role", None))
        print("password_hash=", getattr(u, "password_hash", None))
        try:
            print('check_password("secret123")=', u.check_password("secret123"))
        except Exception as exc:
            print("check_password raised:", exc)
