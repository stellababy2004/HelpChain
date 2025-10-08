from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin
from enum import Enum
import pyotp
import json

db = SQLAlchemy()


class AdminRole(Enum):
    """Роли в административната система"""

    SUPER_ADMIN = "super_admin"  # Пълен достъп до всичко
    ADMIN = "admin"  # Стандартен админ достъп
    MODERATOR = "moderator"  # Ограничен достъп само за модерация


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
    backup_codes = db.Column(db.Text, nullable=True)  # JSON масив с backup кодове
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
        return f"<AdminUser {self.username}>"

    def has_role(self, required_role):
        """Проверява дали потребителят има необходимата роля или по-висока"""
        role_hierarchy = {
            AdminRole.MODERATOR: 1,
            AdminRole.ADMIN: 2,
            AdminRole.SUPER_ADMIN: 3,
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

    def generate_totp_secret(self):
        """Генерира нов TOTP secret"""
        if not self.totp_secret:
            self.totp_secret = pyotp.random_base32()
            try:
                db.session.commit()
            except RuntimeError:
                pass  # Ignore if no app context
        return self.totp_secret

    def get_totp_uri(self):
        """Връща TOTP URI за QR код"""
        if not self.totp_secret:
            self.generate_totp_secret()
        return pyotp.totp.TOTP(self.totp_secret).provisioning_uri(
            name=self.email, issuer_name="HelpChain Admin"
        )

    def verify_totp(self, token):
        """Верифицира TOTP токен"""
        if not self.totp_secret:
            return False
        totp = pyotp.TOTP(self.totp_secret)
        return totp.verify(token)

    def enable_2fa(self):
        """Активира 2FA"""
        if not self.totp_secret:
            self.generate_totp_secret()
        self.two_factor_enabled = True
        try:
            db.session.commit()
        except RuntimeError:
            pass

    def disable_2fa(self):
        """Деактивира 2FA"""
        self.two_factor_enabled = False
        self.totp_secret = None
        try:
            db.session.commit()
        except RuntimeError:
            pass

    def generate_backup_codes(self, count=10):
        """Генерира backup кодове"""
        codes = [pyotp.random_base32(length=8) for _ in range(count)]
        self.backup_codes = json.dumps(codes)
        db.session.commit()
        return codes

    def verify_backup_code(self, code):
        """Верифицира backup код (еднократна употреба)"""
        if not self.backup_codes:
            return False
        codes = json.loads(self.backup_codes)
        if code in codes:
            codes.remove(code)
            self.backup_codes = json.dumps(codes)
            try:
                db.session.commit()
            except RuntimeError:
                pass
            return True
        return False


class AdminLog(db.Model):
    """Модел за проследяване на административни действия"""

    __tablename__ = "admin_logs"

    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(
        db.Integer, db.ForeignKey("admin_users.id"), nullable=False
    )
    action = db.Column(
        db.String(100), nullable=False
    )  # "approved_request", "rejected_request", etc.
    details = db.Column(db.Text, nullable=True)  # JSON или описание на действието
    entity_type = db.Column(
        db.String(50), nullable=True
    )  # "help_request", "volunteer", etc.
    entity_id = db.Column(db.Integer, nullable=True)  # ID на обекта
    ip_address = db.Column(db.String(45), nullable=True)  # IP адрес
    user_agent = db.Column(db.String(500), nullable=True)  # Browser info
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AdminLog {self.action} by {self.admin_user_id}>"


class TwoFactorAuth(db.Model):
    """Модел за 2FA токени и сесии"""

    __tablename__ = "two_factor_auth"

    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(
        db.Integer, db.ForeignKey("admin_users.id"), nullable=False
    )
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
    admin_user_id = db.Column(
        db.Integer, db.ForeignKey("admin_users.id"), nullable=False
    )
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


class VideoChatSession(db.Model):
    """Модел за видео чат сесии между потребители"""

    __tablename__ = "video_chat_sessions"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.String(128), unique=True, nullable=False
    )  # WebRTC session ID
    initiator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    participant_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(
        db.String(50), default="pending"
    )  # pending, active, completed, cancelled
    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    duration = db.Column(db.Integer, nullable=True)  # в секунди
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    initiator = db.relationship(
        "User", foreign_keys=[initiator_id], backref="initiated_video_chats"
    )
    participant = db.relationship(
        "User", foreign_keys=[participant_id], backref="participated_video_chats"
    )

    def __repr__(self):
        return f"<VideoChatSession {self.session_id}>"
