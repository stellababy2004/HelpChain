import argparse
import os


def _get_app():
    # Prefer full backend.app if available
    try:
        from backend.app import app

        return app
    except Exception:
        pass
    # Fallback to minimal backend.appy
    try:
        from backend.appy import app

        return app
    except Exception:
        pass
    raise RuntimeError(
        "Неуспешен импорт на Flask приложението (backend.app или backend.appy)"
    )


def main():
    parser = argparse.ArgumentParser(description="Initialize or update the admin user")
    parser.add_argument("--username", default=os.getenv("ADMIN_USERNAME", "admin"))
    parser.add_argument(
        "--email", default=os.getenv("ADMIN_EMAIL", "admin@helpchain.live")
    )
    parser.add_argument("--password", default=os.getenv("ADMIN_PASSWORD", "Admin1234"))
    args = parser.parse_args()

    app = _get_app()
    with app.app_context():
        import backend.models as models
        from backend.extensions import db

        # Ensure models are configured and tables exist
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
            try:
                admin.set_password(args.password)
            except Exception:
                pass
        else:
            print("Създавам нов админ...")
            admin = AdminUser(username=args.username, email=args.email)
            try:
                admin.set_password(args.password)
            except Exception:
                pass
            sess.add(admin)
        sess.commit()
        print("Готово: админ записът е инициализиран/обновен.")


if __name__ == "__main__":
    main()
