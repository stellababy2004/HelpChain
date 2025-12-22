import os

try:
    from backend.appy import app
except Exception:
    # Fallback to the main app if appy is unavailable or corrupted
    from backend.app import app

print("App created successfully")
with app.app_context():
    print("App context entered")
    # Ensure tables exist for direct queries
    try:
        from backend.extensions import db
        import backend.models as models
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

    from backend.models import AdminUser

    admin = AdminUser.query.filter_by(username="admin").first()
    if admin:
        print(f"Admin found: {admin.username}")
        print(f"Password check {os.getenv('ADMIN_PASSWORD', 'Admin123')}: {admin.check_password(os.getenv('ADMIN_PASSWORD', 'Admin123'))}")
        print(f"Password check admin123: {admin.check_password('admin123')}")
    else:
        print("No admin found")
