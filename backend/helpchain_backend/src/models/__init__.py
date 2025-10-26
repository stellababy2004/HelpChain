import json
from datetime import datetime
from enum import Enum

import pyotp
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

# Try multiple import strategies for extensions
try:
    from ...extensions import db
except ImportError:
    try:
        from ..extensions import db
    except ImportError:
        from extensions import db


class AdminRole(Enum):
    """Роли в административната система"""

    SUPER_ADMIN = "super_admin"  # Пълен достъп до всичко
    ADMIN = "admin"  # Стандартен админ достъп
    MODERATOR = "moderator"  # Ограничен достъп само за модерация


class User(UserMixin, db.Model):
    """Модел за потребители"""

    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(200), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_volunteer = db.Column(db.Boolean, default=False)
    is_organization = db.Column(db.Boolean, default=False)
    citizen_id = db.Column(db.String(20), nullable=True)
    skills = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(100), nullable=True)
    available_time = db.Column(db.String(100), nullable=True)
    profile_picture = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class AdminUser(UserMixin, db.Model):
    """Модел за административни потребители с роли и 2FA"""

    __tablename__ = "admin_users"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.Enum(AdminRole), nullable=False, default=AdminRole.MODERATOR)

    # 2FA полета
    totp_secret = db.Column(db.String(32), nullable=True)  # TOTP secret key
    backup_codes = db.Column(db.Text, nullable=True)  # JSON масив с backup кодове
    two_factor_enabled = db.Column(db.Boolean, default=False)

    # Метаданни
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

    # Връзки
    # logs relationship removed - AdminLog is defined in models_with_analytics.py

    def __repr__(self):
        return f"<AdminUser {self.username}>"

    def has_role(self, required_role):
        """Проверява дали потребителят има необходимата роля или по-висока"""
        role_hierarchy = {
            AdminRole.MODERATOR: 1,
            AdminRole.ADMIN: 2,
            AdminRole.SUPER_ADMIN: 3,
        }
        return role_hierarchy.get(self.role, 0) >= role_hierarchy.get(required_role, 0)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_totp_secret(self):
        """Генерира нов TOTP secret"""
        self.totp_secret = pyotp.random_base32()

    def get_totp_uri(self):
        """Връща TOTP URI за QR код"""
        return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(
            name=self.username, issuer_name="HelpChain Admin"
        )

    def verify_totp(self, token):
        """Проверява TOTP token"""
        if not self.totp_secret:
            return False
        totp = pyotp.TOTP(self.totp_secret)
        return totp.verify(token)

    def enable_2fa(self):
        """Активира 2FA"""
        self.two_factor_enabled = True
        # Генерира backup кодове
        backup_codes = [pyotp.random_base32()[:8] for _ in range(10)]
        self.backup_codes = json.dumps(backup_codes)

    def disable_2fa(self):
        """Деактивира 2FA"""
        self.two_factor_enabled = False
        self.totp_secret = None
        self.backup_codes = None

    def verify_backup_code(self, code):
        """Проверява backup код"""
        if not self.backup_codes:
            return False
        codes = json.loads(self.backup_codes)
        if code in codes:
            codes.remove(code)
            self.backup_codes = json.dumps(codes)
            return True
        return False


# AdminLog is now defined in models_with_analytics.py


class Request(db.Model):
    __tablename__ = "requests"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    location = db.Column(db.String(100))
    category = db.Column(db.String(50))
    description = db.Column(db.Text)
    urgency = db.Column(db.String(20))
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class RequestLog(db.Model):
    __tablename__ = "request_logs"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("requests.id"))
    status = db.Column(db.String(20))
    changed_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class Volunteer(db.Model):
    __tablename__ = "volunteers"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    skills = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(150), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class Feedback(db.Model):
    __tablename__ = "feedbacks"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


__all__ = [
    "Request",
    "RequestLog",
    "Volunteer",
    "Feedback",
    "AdminUser",
    "User",
    # "AdminLog",  # Now defined in models_with_analytics.py
]
