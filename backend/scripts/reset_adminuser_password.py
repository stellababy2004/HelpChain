import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(HERE)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app import app, db
from models import AdminUser


def main():
    with app.app_context():
        a = AdminUser.query.filter_by(username="admin").first()
        if not a:
            print("AdminUser not found")
            return
        a.set_password("StrongPass123")
        db.session.add(a)
        db.session.commit()
        print("Password reset; prefix:", (a.password_hash or "").split("$")[0])


if __name__ == "__main__":
    main()
