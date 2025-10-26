"""
Admin routes for role and user management
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session

# Use absolute imports for production
from backend.models import User, Role, Permission, UserRole, RolePermission
from backend.extensions import db
from backend.permissions import require_permission

from werkzeug.security import generate_password_hash

admin_roles_bp = Blueprint("admin_roles", __name__)


@admin_roles_bp.route("/")
@require_permission("manage_roles")
def roles_dashboard():
    """Main roles and permissions dashboard"""
    roles = Role.query.all()
    permissions = Permission.query.all()
    users = User.query.all()

    # Get role-permission mappings
    role_permissions = {}
    for role in roles:
        role_permissions[role.id] = [
            rp.permission.codename for rp in role.role_permissions
        ]

    # Get user-role mappings
    user_roles = {}
    for user in users:
        user_roles[user.id] = [ur.role.name for ur in user.user_roles]

    return render_template(
        "admin_roles.html",
        roles=roles,
        permissions=permissions,
        users=users,
        role_permissions=role_permissions,
        user_roles=user_roles,
    )


@admin_roles_bp.route("/roles/create", methods=["GET", "POST"])
@require_permission("manage_roles")
def create_role():
    """Create a new role"""
    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        permission_ids = request.form.getlist("permissions")

        if not name:
            flash("Името на ролята е задължително.", "danger")
            return redirect(url_for("admin_roles.create_role"))

        # Check if role already exists
        existing_role = Role.query.filter_by(name=name).first()
        if existing_role:
            flash("Роля с това име вече съществува.", "danger")
            return redirect(url_for("admin_roles.create_role"))

        # Create role
        role = Role(name=name, description=description)
        db.session.add(role)
        db.session.flush()  # Get role ID

        # Assign permissions
        for perm_id in permission_ids:
            permission = db.session.get(Permission, int(perm_id))
            if permission:
                role_permission = RolePermission(
                    role_id=role.id, permission_id=permission.id
                )
                db.session.add(role_permission)

        db.session.commit()
        flash("Ролята е създадена успешно.", "success")
        return redirect(url_for("admin_roles.roles_dashboard"))

    permissions = Permission.query.all()
    return render_template("create_role.html", permissions=permissions)


@admin_roles_bp.route("/roles/<int:role_id>/edit", methods=["GET", "POST"])
@require_permission("manage_roles")
def edit_role(role_id):
    """Edit an existing role"""
    role = Role.query.get_or_404(role_id)

    if role.is_system_role:
        flash("Системните роли не могат да бъдат редактирани.", "danger")
        return redirect(url_for("admin_roles.roles_dashboard"))

    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        permission_ids = request.form.getlist("permissions")

        if not name:
            flash("Името на ролята е задължително.", "danger")
            return redirect(url_for("admin_roles.edit_role", role_id=role_id))

        # Check if name conflicts with another role
        existing_role = Role.query.filter(Role.name == name, Role.id != role_id).first()
        if existing_role:
            flash("Роля с това име вече съществува.", "danger")
            return redirect(url_for("admin_roles.edit_role", role_id=role_id))

        # Update role
        role.name = name
        role.description = description

        # Remove existing permissions
        RolePermission.query.filter_by(role_id=role_id).delete()

        # Add new permissions
        for perm_id in permission_ids:
            permission = db.session.get(Permission, int(perm_id))
            if permission:
                role_permission = RolePermission(
                    role_id=role.id, permission_id=permission.id
                )
                db.session.add(role_permission)

        db.session.commit()
        flash("Ролята е обновена успешно.", "success")
        return redirect(url_for("admin_roles.roles_dashboard"))

    permissions = Permission.query.all()
    current_permissions = [rp.permission_id for rp in role.role_permissions]

    return render_template(
        "edit_role.html",
        role=role,
        permissions=permissions,
        current_permissions=current_permissions,
    )


@admin_roles_bp.route("/roles/<int:role_id>/delete", methods=["POST"])
@require_permission("manage_roles")
def delete_role(role_id):
    """Delete a role"""
    role = Role.query.get_or_404(role_id)

    if role.is_system_role:
        flash("Системните роли не могат да бъдат изтрити.", "danger")
        return redirect(url_for("admin_roles.roles_dashboard"))

    # Check if role is assigned to users
    if role.user_roles:
        flash(
            "Ролята не може да бъде изтрита, защото е присвоена на потребители.",
            "danger",
        )
        return redirect(url_for("admin_roles.roles_dashboard"))

    # Delete role permissions first
    RolePermission.query.filter_by(role_id=role_id).delete()

    # Delete role
    db.session.delete(role)
    db.session.commit()

    flash("Ролята е изтрита успешно.", "success")
    return redirect(url_for("admin_roles.roles_dashboard"))


@admin_roles_bp.route("/users/<int:user_id>/roles", methods=["GET", "POST"])
@require_permission("manage_users")
def manage_user_roles(user_id):
    """Manage roles for a specific user"""
    user = User.query.get_or_404(user_id)

    if request.method == "POST":
        role_ids = request.form.getlist("roles")

        # Remove existing roles
        UserRole.query.filter_by(user_id=user_id).delete()

        # Add new roles
        for role_id in role_ids:
            role = db.session.get(Role, int(role_id))
            if role:
                user_role = UserRole(
                    user_id=user.id, role_id=role.id, assigned_by=session.get("user_id")
                )
                db.session.add(user_role)

        db.session.commit()
        flash("Ролите на потребителя са обновени успешно.", "success")
        return redirect(url_for("admin_roles.roles_dashboard"))

    roles = Role.query.all()
    current_roles = [ur.role_id for ur in user.user_roles]

    return render_template(
        "manage_user_roles.html", user=user, roles=roles, current_roles=current_roles
    )


@admin_roles_bp.route("/users/create", methods=["GET", "POST"])
@require_permission("manage_users")
def create_user():
    """Create a new user"""
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        role_ids = request.form.getlist("roles")

        if not all([username, email, password]):
            flash("Всички полета са задължителни.", "danger")
            return redirect(url_for("admin_roles.create_user"))

        # Check if user already exists
        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing_user:
            flash(
                "Потребител с това потребителско име или имейл вече съществува.",
                "danger",
            )
            return redirect(url_for("admin_roles.create_user"))

        # Create user
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()  # Get user ID

        # Assign roles
        for role_id in role_ids:
            role = Role.query.get(int(role_id))
            if role:
                user_role = UserRole(
                    user_id=user.id, role_id=role.id, assigned_by=session.get("user_id")
                )
                db.session.add(user_role)

        db.session.commit()
        flash("Потребителят е създаден успешно.", "success")
        return redirect(url_for("admin_roles.roles_dashboard"))

    roles = Role.query.all()
    return render_template("create_user.html", roles=roles)


@admin_roles_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@require_permission("manage_users")
def toggle_user_status(user_id):
    """Toggle user active status"""
    user = User.query.get_or_404(user_id)

    # Prevent disabling self
    if user.id == session.get("user_id"):
        flash("Не можете да деактивирате собствения си акаунт.", "danger")
        return redirect(url_for("admin_roles.roles_dashboard"))

    user.is_active = not user.is_active
    db.session.commit()

    status = "активиран" if user.is_active else "деактивиран"
    flash(f"Потребителят е {status} успешно.", "success")
    return redirect(url_for("admin_roles.roles_dashboard"))


@admin_roles_bp.route("/permissions/create", methods=["GET", "POST"])
@require_permission("manage_roles")
def create_permission():
    """Create a new permission"""
    if request.method == "POST":
        name = request.form.get("name")
        codename = request.form.get("codename")
        description = request.form.get("description")
        category = request.form.get("category")

        if not all([name, codename]):
            flash("Името и кодовото име са задължителни.", "danger")
            return redirect(url_for("admin_roles.create_permission"))

        # Check if permission already exists
        existing_perm = Permission.query.filter(
            (Permission.codename == codename) | (Permission.name == name)
        ).first()
        if existing_perm:
            flash("Право с това име или кодово име вече съществува.", "danger")
            return redirect(url_for("admin_roles.create_permission"))

        # Create permission
        permission = Permission(
            name=name, codename=codename, description=description, category=category
        )
        db.session.add(permission)
        db.session.commit()

        flash("Правото е създадено успешно.", "success")
        return redirect(url_for("admin_roles.roles_dashboard"))

    return render_template("create_permission.html")
