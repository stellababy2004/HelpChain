import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(HERE)
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)
from app import app
from models import AdminUser


def main():
    with app.app_context():
        a = AdminUser.query.filter_by(username="admin").first()
        print("admin exists:", bool(a))
        if a:
            print("locked_until:", a.locked_until)
            print("failed_attempts:", a.failed_login_attempts)
            print("hash prefix:", (a.password_hash or "").split("$")[0])
            try:
                print("check StrongPass123:", a.check_password("StrongPass123"))
            except Exception as e:
                print("check error:", e)


if __name__ == "__main__":
    main()
