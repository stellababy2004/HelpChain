def create_or_update_admin(username, password, email=None):
    admin = AdminUser.query.filter_by(username=username).first()
    if not admin:
        admin = AdminUser(username=username, email=email, role="ADMIN", is_active=True)
        db.session.add(admin)
    admin.set_password(password)
    admin.is_active = True
    db.session.commit()
    print(f"Админ '{username}' е създаден/обновен успешно!")


from flask import Flask

from app import app
from backend.extensions import db
from backend.models import AdminUser

if __name__ == "__main__":
    # Задай пътя към базата, ако не е конфигуриран
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///./instance/volunteers.db"
    db.init_app(app)
    with app.app_context():
        db.create_all()
        create_or_update_admin("admin", "Admin1234", "admin@example.com")
