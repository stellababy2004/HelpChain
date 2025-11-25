from enum import Enum


# Dummy PermissionEnum for test compatibility
class PermissionEnum(Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


# Модели и енумерации за HelpChain
import datetime
from enum import Enum

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db

# Expose AdminRole from helpchain_backend.src.models if available
try:
    from helpchain_backend.src.models import AdminRole
except ImportError:
    AdminRole = None


class PermissionEnum(Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


def utc_now():
    return datetime.datetime.utcnow()


class Permission(db.Model):
    __tablename__ = "permissions"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))


class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(255))


class UserRole(db.Model):
    __tablename__ = "user_roles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    role_id = db.Column(db.Integer)


class PushSubscription(db.Model):
    __tablename__ = "push_subscriptions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    endpoint = db.Column(db.String(255))
    auth = db.Column(db.String(255))
    p256dh = db.Column(db.String(255))


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime)


class ChatParticipant(db.Model):
    __tablename__ = "chat_participants"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    chat_id = db.Column(db.Integer)
    joined_at = db.Column(db.DateTime)


class ChatRoom(db.Model):
    __tablename__ = "chat_rooms"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    created_at = db.Column(db.DateTime)


class RequestLog(db.Model):
    __tablename__ = "request_logs"
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer)
    log = db.Column(db.Text)


class RolePermission(db.Model):
    __tablename__ = "role_permissions"
    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer)
    permission = db.Column(db.String(80))


class RoleEnum(Enum):
    ADMIN = "admin"
    VOLUNTEER = "volunteer"


class PriorityEnum(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class AdminUser(db.Model):
    __tablename__ = "admin_users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default=RoleEnum.ADMIN.value)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default=RoleEnum.VOLUNTEER.value)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Volunteer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    city = db.Column(db.String(80))
    role = db.Column(db.String(20), default=RoleEnum.VOLUNTEER.value)


class HelpRequest(db.Model):
    __tablename__ = "help_requests"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending")
    priority = db.Column(db.String(20), default=PriorityEnum.MEDIUM.value)
    city = db.Column(db.String(80))
    region = db.Column(db.String(80))
    name = db.Column(db.String(80))
    email = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )


class AdminLog(db.Model):
    __tablename__ = "admin_logs"
    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(
        db.Integer, db.ForeignKey("admin_users.id"), nullable=False
    )
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime)
    admin_user = db.relationship(
        "AdminUser",
        backref=db.backref("logs", overlaps="admin_user,admin_logs"),
        overlaps="admin_user",
    )


class Feedback(db.Model):
    __tablename__ = "feedbacks"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime)


class Request(db.Model):
    __tablename__ = "requests"
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Text)


class AnalyticsEvent(db.Model):
    __tablename__ = "analytics_events"
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(80))
    user_id = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime)


class ChatbotConversation(db.Model):
    __tablename__ = "chatbot_conversations"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    started_at = db.Column(db.DateTime)


class PerformanceMetrics(db.Model):
    __tablename__ = "performance_metrics"
    id = db.Column(db.Integer, primary_key=True)
    metric = db.Column(db.String(80))
    value = db.Column(db.Float)
    timestamp = db.Column(db.DateTime)


class UserBehavior(db.Model):
    __tablename__ = "user_behaviors"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    action = db.Column(db.String(80))
    timestamp = db.Column(db.DateTime)


__all__ = [
    "RolePermission",
    "Role",
    "Notification",
    "RequestLog",
    "AdminUser",
    "User",
    "PushSubscription",
    "Permission",
    "PermissionEnum",
    "Volunteer",
    "HelpRequest",
    "AdminLog",
    "Feedback",
    "Request",
    "AnalyticsEvent",
    "ChatbotConversation",
    "PerformanceMetrics",
    "UserBehavior",
    "ChatMessage",
    "ChatParticipant",
    "ChatRoom",
    "RoleEnum",
    "UserRole",
    "utc_now",
]
