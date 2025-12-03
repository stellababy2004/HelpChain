import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def main():
    try:
        from appy import app

        from backend.extensions import db

        print("App imported successfully")
        with app.app_context():
            print("App context works")
            from backend.models import AdminUser

            admin = db.session.query(AdminUser).filter_by(username="admin").first()
            if admin:
                print(f"Admin user found: {admin.username}")
            else:
                print("Admin user not found")
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
