import sys

sys.path.insert(0, ".")
from appy import app
from permissions import has_permission

from .models import Role, RolePermission, User, UserRole

with app.app_context():
    admin = User.query.filter_by(username="admin").first()
    if admin:
        print(f"Admin user: {admin.username}, ID: {admin.id}")

        user_roles = UserRole.query.filter_by(user_id=admin.id).all()
        print(f"User roles count: {len(user_roles)}")
        for ur in user_roles:
            role = Role.query.get(ur.role_id)
            print(f"Role: {role.name}")

            role_perms = RolePermission.query.filter_by(role_id=role.id).all()
            print(f"  Permissions: {[rp.permission.codename for rp in role_perms]}")

        from flask import session

        with app.test_request_context():
            session["user_id"] = admin.id
            print(f'Has manage_roles: {has_permission("manage_roles")}')
            print(f'Has admin_access: {has_permission("admin_access")}')
    else:
        print("Admin user not found")
