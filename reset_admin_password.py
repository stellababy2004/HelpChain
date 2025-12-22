import argparse
import os
import sys


def _get_app():
    try:
        from backend.app import app  # preferred full app
        return app
    except Exception:
        pass
    try:
        from backend.appy import app  # minimal preview app
        return app
    except Exception:
        pass
    raise RuntimeError("Неуспешен импорт на Flask приложението (backend.app или backend.appy)")


def main():
    parser = argparse.ArgumentParser(description="Reset or create admin password")
    parser.add_argument("--username", help="Admin username", default=os.getenv("ADMIN_USERNAME", "admin"))
    parser.add_argument("--email", help="Admin email", default=os.getenv("ADMIN_EMAIL", "admin@helpchain.live"))
    parser.add_argument("--password", help="New password", required=True)
    args = parser.parse_args()

    app = _get_app()
    with app.app_context():
        try:
            from backend.extensions import db
            import backend.models as models
        except Exception as e:
            raise RuntimeError(f"Липсващ модул: {e}")

        # Ensure models use the Flask-SQLAlchemy session and tables exist
        try:
            if hasattr(models, "configure_models"):
                models.configure_models(db)
        except Exception:
            pass
        try:
            engine = getattr(db, "engine", None)
            if engine is None:
                try:
                    engine = db.get_engine(app)
                except Exception:
                    engine = None
            if engine is not None:
                try:
                    models.Base.metadata.create_all(bind=engine)
                except Exception:
                    pass
        except Exception:
            pass

        AdminUser = models.AdminUser

        # Find by username or email
        sess = db.session
        admin = None
        try:
            admin = sess.query(AdminUser).filter_by(username=args.username).first()
        except Exception:
            admin = None
        if not admin:
            try:
                admin = sess.query(AdminUser).filter_by(email=args.email).first()
            except Exception:
                admin = None

        if admin:
            print(f"Открит админ: {admin.username}, email: {admin.email}")
            admin.set_password(args.password)
            sess.commit()
            print("Паролата е обновена успешно.")
        else:
            print("Админ не е намерен, създавам нов...")
            admin = AdminUser(username=args.username, email=args.email)
            admin.set_password(args.password)
            sess.add(admin)
            sess.commit()
            print("Админът е създаден успешно.")


if __name__ == "__main__":
    main()
