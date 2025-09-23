from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin
import hashlib
import secrets
from enum import Enum

db = SQLAlchemy()


class AdminRole(Enum):
    """Роли в административната система"""
    SUPER_ADMIN = "super_admin"  # Пълен достъп до всичко
    ADMIN = "admin"              # Стандартен админ достъп
    MODERATOR = "moderator"      # Ограничен достъп само за модерация


class AdminUser(UserMixin, db.Model):
    """Модел за административни потребители с роли и 2FA"""
    __tablename__ = "admin_users"
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.Enum(AdminRole), nullable=False, default=AdminRole.MODERATOR)
    
    # 2FA полета
    totp_secret = db.Column(db.String(32), nullable=True)  # TOTP secret key
    backup_codes = db.Column(db.Text, nullable=True)       # JSON масив с backup кодове
    two_factor_enabled = db.Column(db.Boolean, default=False)
    
    # Метаданни
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    
    # Връзки
    logs = db.relationship("AdminLog", backref="admin_user", lazy=True)

    def __repr__(self):
        return f'<AdminUser {self.username}>'

    def has_role(self, required_role):
        """Проверява дали потребителят има необходимата роля или по-висока"""
        role_hierarchy = {
            AdminRole.MODERATOR: 1,
            AdminRole.ADMIN: 2,
            AdminRole.SUPER_ADMIN: 3
        }
        
        user_level = role_hierarchy.get(self.role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        
        return user_level >= required_level

    def can_manage_users(self):
        """Само super_admin може да управлява други админи"""
        return self.role == AdminRole.SUPER_ADMIN

    def can_view_logs(self):
        """Admin и super_admin могат да виждат логове"""
        return self.role in [AdminRole.ADMIN, AdminRole.SUPER_ADMIN]


class AdminLog(db.Model):
    """Модел за проследяване на административни действия"""
    __tablename__ = "admin_logs"
    
    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"), nullable=False)
    action = db.Column(db.String(100), nullable=False)  # "approved_request", "rejected_request", etc.
    details = db.Column(db.Text, nullable=True)         # JSON или описание на действието
    entity_type = db.Column(db.String(50), nullable=True)  # "help_request", "volunteer", etc.
    entity_id = db.Column(db.Integer, nullable=True)       # ID на обекта
    ip_address = db.Column(db.String(45), nullable=True)   # IP адрес
    user_agent = db.Column(db.String(500), nullable=True)  # Browser info
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AdminLog {self.action} by {self.admin_user_id}>'


class TwoFactorAuth(db.Model):
    """Модел за 2FA токени и сесии"""
    __tablename__ = "two_factor_auth"
    
    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"), nullable=False)
    session_token = db.Column(db.String(128), unique=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    admin_user = db.relationship("AdminUser", backref="auth_sessions")

    def is_expired(self):
        return datetime.utcnow() > self.expires_at


class AdminSession(db.Model):
    """Модел за следене на активни админ сесии"""
    __tablename__ = "admin_sessions"
    
    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"), nullable=False)
    session_id = db.Column(db.String(128), unique=True, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    admin_user = db.relationship("AdminUser", backref="sessions")

    def update_activity(self):
        self.last_activity = datetime.utcnow()
        db.session.commit()


class User(UserMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), default="volunteer")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    requests = db.relationship("HelpRequest", backref="user", lazy=True)


class HelpRequest(db.Model):
    __tablename__ = "help_requests"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class Volunteer(db.Model):
    __tablename__ = "volunteers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    location = db.Column(db.String(100))


class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class SuccessStory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
