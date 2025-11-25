def create_or_update_admin(username, password, email=None):
    admin = AdminUser.query.filter_by(username=username).first()
    if not admin:
        admin = AdminUser(username=username, email=email, role="ADMIN", is_active=True)
        db.session.add(admin)
    admin.set_password(password)
    admin.is_active = True
    admin.locked_until = None
    admin.failed_login_attempts = 0
    db.session.commit()
    print(f"Админ '{username}' е създаден/обновен успешно!")


from flask import Flask

from app import app
from extensions import db
from models import AdminUser

if __name__ == "__main__":
    # Задай пътя към базата, ако не е конфигуриран
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///./instance/volunteers.db"
    ## db.init_app(app)  # Already initialized in app.py
    with app.app_context():
        db.create_all()
        create_or_update_admin("admin", "Azerty5!", "admin@example.com")
