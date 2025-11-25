"""
SQLAlchemy models for HelpChain application
"""

import sys
from datetime import UTC, datetime
from enum import Enum

# Ensure this module is available under a small set of canonical names so
# SQLAlchemy doesn't end up with duplicate module objects defining the same
# mapped classes during the test runs. If the module is imported under any
# of these aliases later, they will point to the same module object.
try:
    _this_module = sys.modules.get(__name__)
    for _alias in (
        "models",
        "backend.models",
        "helpchain_backend.src.models",
    ):
        if _alias not in sys.modules:
            sys.modules[_alias] = _this_module
except Exception:
    # Never fail import of the models file due to aliasing; aliasing is best-effort.
    pass

from extensions import db


def utc_now() -> datetime:
    """Return naive UTC timestamp without relying on datetime.utcnow."""
    return datetime.now(UTC).replace(tzinfo=None)


class PriorityEnum(Enum):
    """Priority levels for help requests"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class RoleEnum(Enum):
    """User role types"""

    user = "user"
    volunteer = "volunteer"
    moderator = "moderator"
    admin = "admin"
    superadmin = "superadmin"


class PermissionEnum(Enum):
    """Permission codenames"""

    VIEW_PROFILE = "view_profile"
    EDIT_PROFILE = "edit_profile"
    VIEW_VOLUNTEERS = "view_volunteers"
    MANAGE_VOLUNTEERS = "manage_volunteers"
    VIEW_REQUESTS = "view_requests"
    MANAGE_REQUESTS = "manage_requests"
    USE_VIDEO_CHAT = "use_video_chat"
    MODERATE_CONTENT = "moderate_content"
    VIEW_ANALYTICS = "view_analytics"
    MANAGE_CATEGORIES = "manage_categories"
    ADMIN_ACCESS = "admin_access"
    MANAGE_USERS = "manage_users"
    MANAGE_ROLES = "manage_roles"
    SYSTEM_SETTINGS = "system_settings"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    SUPER_ADMIN = "super_admin"


class AdminRole(Enum):
    """Роли в административната система"""

    SUPER_ADMIN = "super_admin"  # Пълен достъп до всичко
    ADMIN = "admin"  # Стандартен админ достъп
    MODERATOR = "moderator"  # Ограничен достъп само за модерация


class User(db.Model):
    """User model for regular users"""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.Enum(RoleEnum), default=RoleEnum.user)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    user_roles = db.relationship("UserRole", back_populates="user")

    def set_password(self, password):
        """Set password hash"""
        from werkzeug.security import generate_password_hash

        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check password"""
        from werkzeug.security import check_password_hash

        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


class AdminUser(db.Model):
    """Admin user model"""

    __tablename__ = "admin_users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.Enum(AdminRole), default=AdminRole.ADMIN)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    admin_logs = db.relationship("AdminLog", back_populates="admin_user")
    auth_sessions = db.relationship("TwoFactorAuth", back_populates="admin_user")
    sessions = db.relationship("AdminSession", back_populates="admin_user")
    created_tasks = db.relationship("Task", back_populates="creator")

    def set_password(self, password):
        """Set password hash"""
        from werkzeug.security import generate_password_hash

        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check password"""
        from werkzeug.security import check_password_hash

        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<AdminUser {self.username}>"


class Volunteer(db.Model):
    """Volunteer model"""

    __tablename__ = "volunteers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    skills = db.Column(db.Text)
    location = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<Volunteer {self.name}>"


class HelpRequest(db.Model):
    """Help request model"""

    __tablename__ = "help_requests"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    message = db.Column(db.Text)
    city = db.Column(db.String(100))
    region = db.Column(db.String(100))
    priority = db.Column(db.Enum(PriorityEnum), default=PriorityEnum.MEDIUM)
    status = db.Column(db.String(50), default="pending")
    channel = db.Column(db.String(50), default="web")
    category = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<HelpRequest {self.title}>"


class Permission(db.Model):
    """Permission model"""

    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    codename = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    is_system_permission = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    role_permissions = db.relationship("RolePermission", back_populates="permission")

    def __repr__(self):
        return f"<Permission {self.codename}>"


class Role(db.Model):
    """Role model"""

    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    is_system_role = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    role_permissions = db.relationship("RolePermission", back_populates="role")
    user_roles = db.relationship("UserRole", back_populates="role")

    def __repr__(self):
        return f"<Role {self.name}>"


class RolePermission(db.Model):
    """Many-to-many relationship between roles and permissions"""

    __tablename__ = "role_permissions"

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    permission_id = db.Column(
        db.Integer, db.ForeignKey("permissions.id"), nullable=False
    )
    created_at = db.Column(db.DateTime, default=utc_now)

    # Relationships
    role = db.relationship("Role", back_populates="role_permissions")
    permission = db.relationship("Permission", back_populates="role_permissions")

    def __repr__(self):
        return f"<RolePermission role:{self.role_id} perm:{self.permission_id}>"


class UserRole(db.Model):
    """Many-to-many relationship between users and roles"""

    __tablename__ = "user_roles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    assigned_at = db.Column(db.DateTime, default=utc_now)

    # Relationships
    user = db.relationship("User", back_populates="user_roles")
    role = db.relationship("Role", back_populates="user_roles")

    def __repr__(self):
        return f"<UserRole user:{self.user_id} role:{self.role_id}>"


# Export all models
__all__ = [
    "AdminRole",
    "AdminUser",
    "HelpRequest",
    "Permission",
    "PermissionEnum",
    "PriorityEnum",
    "Role",
    "RoleEnum",
    "RolePermission",
    "User",
    "UserRole",
    "Volunteer",
]
