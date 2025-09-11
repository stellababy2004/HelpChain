import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.appy import app
from backend.models import User
from werkzeug.security import check_password_hash

EMAIL = "testuser@example.com"
PASSWORD = "Test1234"

with app.app_context():
    u = User.query.filter_by(email=EMAIL).first()
    print("found user:", bool(u))
    if u:
        print("stored password hash:", u.password)
        print("check_password:", check_password_hash(u.password, PASSWORD))