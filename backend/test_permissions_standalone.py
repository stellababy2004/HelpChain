import sys

sys.path.insert(0, ".")

from flask import Flask
from models import db, User, Role, UserRole
from permissions import initialize_default_roles_and_permissions
from werkzeug.security import generate_password_hash

# Create a simple Flask app for testing
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
app.config["SECRET_KEY"] = "test"
db.init_app(app)

with app.app_context():
    db.create_all()
    initialize_default_roles_and_permissions()

    # Create a test admin user
    admin_role = Role.query.filter_by(name="Администратор").first()
    if not admin_role:
        print("Admin role not found")
        exit(1)

    # Create test user
    test_user = User(
        username="testadmin",
        email="test@example.com",
        password_hash=generate_password_hash("password"),
        role="admin",  # Use English enum value
    )
    db.session.add(test_user)
    db.session.flush()  # Get the user ID before committing

    # Assign admin role via UserRole
    user_role = UserRole(user_id=test_user.id, role_id=admin_role.id)
    db.session.add(user_role)

    db.session.commit()
    print(f"Created test admin user: {test_user.username}")
    print(f"User has role: {admin_role.name}")
    print(f"Role has {len(admin_role.role_permissions)} permissions")

    # Test permission checking - create a mock session
    import flask

    # Create a mock session
    with app.test_request_context():
        flask.session["user_id"] = test_user.id

        # Test with user that has admin role
        admin_permissions = ["admin_access", "manage_users", "view_volunteers"]
        for perm in admin_permissions:
            from permissions import has_permission

            has_perm = has_permission(perm)
            print(f'User has permission "{perm}": {has_perm}')

    print("Permission testing completed successfully!")
