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


class Request(db.Model):
    """Request model for helpchain_backend"""

    __tablename__ = "requests"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(100))
    category = db.Column(db.String(100))
    description = db.Column(db.Text)
    urgency = db.Column(db.String(50))
    status = db.Column(db.String(50), default="pending")
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<Request {self.name}>"


class RequestLog(db.Model):
    """Request log model for tracking status changes"""

    __tablename__ = "request_logs"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("requests.id"), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    new_status = db.Column(db.String(50), nullable=True)
    action = db.Column(db.String(100), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    changed_at = db.Column(db.DateTime, default=utc_now)

    def __repr__(self):
        return f"<RequestLog {self.request_id} status:{self.status}>"


class ChatRoom(db.Model):
    """Chat room model"""

    __tablename__ = "chat_rooms"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    room_type = db.Column(db.String(50), default="public")  # public, private
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    messages = db.relationship(
        "ChatMessage", back_populates="room", cascade="all, delete-orphan"
    )
    participants = db.relationship(
        "ChatParticipant", back_populates="room", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<ChatRoom {self.name}>"


class ChatParticipant(db.Model):
    """Chat participant model"""

    __tablename__ = "chat_participants"

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("chat_rooms.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    volunteer_id = db.Column(db.Integer, db.ForeignKey("volunteers.id"), nullable=True)
    participant_type = db.Column(
        db.String(50), nullable=False
    )  # user, volunteer, guest
    participant_name = db.Column(db.String(100), nullable=False)
    is_online = db.Column(db.Boolean, default=True)
    joined_at = db.Column(db.DateTime, default=utc_now)
    last_seen = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    room = db.relationship("ChatRoom", back_populates="participants")

    def __repr__(self):
        return f"<ChatParticipant {self.participant_name} in room {self.room_id}>"


class ChatMessage(db.Model):
    """Chat message model"""

    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("chat_rooms.id"), nullable=False)
    sender_id = db.Column(db.Integer, nullable=True)  # Can be user or volunteer ID
    sender_type = db.Column(db.String(50), nullable=False)  # user, volunteer, guest
    sender_name = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(50), default="text")  # text, file, image, etc.
    reply_to_id = db.Column(
        db.Integer, db.ForeignKey("chat_messages.id"), nullable=True
    )
    file_url = db.Column(db.String(500), nullable=True)
    file_name = db.Column(db.String(255), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    room = db.relationship("ChatRoom", back_populates="messages")
    replies = db.relationship(
        "ChatMessage",
        backref=db.backref("reply_to", remote_side=[id]),
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<ChatMessage {self.id} by {self.sender_name}>"


class Notification(db.Model):
    """Notification model for tracking sent notifications"""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(
        db.Integer, db.ForeignKey("notification_templates.id"), nullable=True
    )
    queue_id = db.Column(
        db.Integer, db.ForeignKey("notification_queue.id"), nullable=True
    )
    recipient_type = db.Column(db.String(50), nullable=False)  # user, volunteer, admin
    recipient_id = db.Column(db.Integer, nullable=True)
    recipient_email = db.Column(db.String(255), nullable=True)
    delivery_channel = db.Column(
        db.String(50), nullable=False
    )  # email, push, in_app, sms
    final_subject = db.Column(db.String(500), nullable=True)
    final_title = db.Column(db.String(255), nullable=True)
    final_content = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.String(50), default="sent"
    )  # sent, delivered, read, clicked, failed
    delivered_at = db.Column(db.DateTime, nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)
    clicked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    template = db.relationship("NotificationTemplate", back_populates="notifications")
    queue_item = db.relationship("NotificationQueue", back_populates="notifications")

    def __repr__(self):
        return f"<Notification {self.id} to {self.recipient_email}>"


class NotificationTemplate(db.Model):
    """Notification template model"""

    __tablename__ = "notification_templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    type = db.Column(db.String(50), nullable=False)  # email, push, in_app, sms
    category = db.Column(
        db.String(50), nullable=False
    )  # registration, feedback, system, etc.
    subject = db.Column(db.String(500), nullable=True)
    title = db.Column(db.String(255), nullable=True)
    content = db.Column(db.Text, nullable=False)
    content_type = db.Column(db.String(20), default="html")  # html, text
    is_active = db.Column(db.Boolean, default=True)
    priority = db.Column(db.String(20), default="normal")  # low, normal, high, urgent
    auto_send = db.Column(db.Boolean, default=False)
    variables = db.Column(db.Text, nullable=True)  # JSON array of variable names
    send_delay = db.Column(db.Integer, default=0)  # minutes
    expiry_hours = db.Column(db.Integer, default=24)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    notifications = db.relationship("Notification", back_populates="template")
    queue_items = db.relationship("NotificationQueue", back_populates="template")

    def __repr__(self):
        return f"<NotificationTemplate {self.name}>"


class NotificationQueue(db.Model):
    """Notification queue model"""

    __tablename__ = "notification_queue"

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(
        db.Integer, db.ForeignKey("notification_templates.id"), nullable=False
    )
    recipient_type = db.Column(db.String(50), nullable=False)  # user, volunteer, admin
    recipient_id = db.Column(db.Integer, nullable=True)
    recipient_email = db.Column(db.String(255), nullable=False)
    personalization_data = db.Column(db.Text, nullable=True)  # JSON
    priority = db.Column(db.String(20), default="normal")  # low, normal, high, urgent
    status = db.Column(
        db.String(50), default="pending"
    )  # pending, processing, sent, failed
    scheduled_for = db.Column(db.DateTime, default=utc_now)
    sent_at = db.Column(db.DateTime, nullable=True)
    attempts = db.Column(db.Integer, default=0)
    max_attempts = db.Column(db.Integer, default=3)
    last_attempt = db.Column(db.DateTime, nullable=True)
    next_retry = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    template = db.relationship("NotificationTemplate", back_populates="queue_items")
    notifications = db.relationship("Notification", back_populates="queue_item")

    def __repr__(self):
        return f"<NotificationQueue {self.id} to {self.recipient_email}>"


class NotificationPreference(db.Model):
    """User notification preferences model"""

    __tablename__ = "notification_preferences"

    id = db.Column(db.Integer, primary_key=True)
    volunteer_id = db.Column(db.Integer, db.ForeignKey("volunteers.id"), nullable=False)

    # Channel preferences
    email_enabled = db.Column(db.Boolean, default=True)
    push_enabled = db.Column(db.Boolean, default=True)
    in_app_enabled = db.Column(db.Boolean, default=True)
    sms_enabled = db.Column(db.Boolean, default=False)

    # Category preferences
    registration_notifications = db.Column(db.Boolean, default=True)
    feedback_notifications = db.Column(db.Boolean, default=True)
    system_notifications = db.Column(db.Boolean, default=True)
    marketing_notifications = db.Column(db.Boolean, default=False)
    reminder_notifications = db.Column(db.Boolean, default=True)

    # Quiet hours
    quiet_hours_start = db.Column(db.Time, default="22:00:00")
    quiet_hours_end = db.Column(db.Time, default="08:00:00")

    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    volunteer = db.relationship("Volunteer", backref="notification_preferences")

    def __repr__(self):
        return f"<NotificationPreference for volunteer {self.volunteer_id}>"


class PushSubscription(db.Model):
    """Push notification subscription model"""

    __tablename__ = "push_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    volunteer_id = db.Column(db.Integer, db.ForeignKey("volunteers.id"), nullable=False)
    endpoint = db.Column(db.String(500), nullable=False)
    p256dh_key = db.Column(db.String(100), nullable=False)
    auth_key = db.Column(db.String(50), nullable=False)
    user_agent = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    notifications_sent = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime, default=utc_now)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    volunteer = db.relationship("Volunteer", backref="push_subscriptions")

    def __repr__(self):
        return f"<PushSubscription for volunteer {self.volunteer_id}>"


class AnalyticsEvent(db.Model):
    """Analytics event tracking model"""

    __tablename__ = "analytics_events"

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(
        db.String(50), nullable=False, index=True
    )  # page_view, click, form_submit, etc.
    event_category = db.Column(db.String(100), nullable=True)
    event_action = db.Column(db.String(100), nullable=True)
    event_label = db.Column(db.String(200), nullable=True)
    event_value = db.Column(db.Float, nullable=True)
    user_session = db.Column(db.String(100), nullable=True, index=True)
    user_type = db.Column(db.String(20), default="guest")  # guest, volunteer, admin
    user_ip = db.Column(db.String(45), nullable=True)  # IPv4/IPv6
    user_agent = db.Column(db.Text, nullable=True)
    page_url = db.Column(db.String(500), nullable=True)
    page_title = db.Column(db.String(200), nullable=True)
    referrer = db.Column(db.String(500), nullable=True)
    load_time = db.Column(db.Float, nullable=True)  # page load time in seconds
    screen_resolution = db.Column(db.String(20), nullable=True)  # e.g., "1920x1080"
    device_type = db.Column(db.String(20), default="unknown")  # desktop, mobile, tablet
    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    def __repr__(self):
        return f"<AnalyticsEvent {self.event_type} at {self.created_at}>"


class PerformanceMetrics(db.Model):
    """Performance metrics tracking model"""

    __tablename__ = "performance_metrics"

    id = db.Column(db.Integer, primary_key=True)
    metric_type = db.Column(
        db.String(50), nullable=False, index=True
    )  # response_time, cpu_usage, memory_usage, etc.
    metric_name = db.Column(db.String(100), nullable=False)
    metric_value = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=True)  # seconds, percent, bytes, etc.
    endpoint = db.Column(db.String(200), nullable=True, index=True)
    user_agent = db.Column(db.Text, nullable=True)
    request_size = db.Column(db.Integer, nullable=True)  # bytes
    response_size = db.Column(db.Integer, nullable=True)  # bytes
    context_data = db.Column(
        db.Text, nullable=True
    )  # JSON string with additional context
    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    def __repr__(self):
        return (
            f"<PerformanceMetrics {self.metric_name}: {self.metric_value} {self.unit}>"
        )


class UserBehavior(db.Model):
    """User behavior tracking model"""

    __tablename__ = "user_behaviors"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False, unique=True, index=True)
    user_type = db.Column(db.String(20), default="guest")  # guest, volunteer, admin
    entry_page = db.Column(db.String(500), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv4/IPv6
    user_agent = db.Column(db.Text, nullable=True)
    device_info = db.Column(db.String(50), nullable=True)  # browser, os, device type
    location = db.Column(db.String(100), nullable=True)  # country, city
    pages_visited = db.Column(db.Integer, default=0)
    last_activity = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    exit_page = db.Column(db.String(500), nullable=True)
    bounce_rate = db.Column(db.Boolean, default=False)  # True if only visited one page
    pages_sequence = db.Column(db.Text, nullable=True)  # JSON array of visited pages
    session_start = db.Column(db.DateTime, default=utc_now, index=True)
    total_time_spent = db.Column(db.Float, default=0.0)  # total session time in seconds
    conversion_action = db.Column(
        db.String(50), nullable=True
    )  # registration, help_request, etc.

    def __repr__(self):
        return f"<UserBehavior session {self.session_id}>"


class ChatbotConversation(db.Model):
    """Chatbot conversation tracking model"""

    __tablename__ = "chatbot_conversations"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=True, index=True)
    user_message = db.Column(db.Text, nullable=False)
    ai_response = db.Column(db.Text, nullable=False)
    response_type = db.Column(db.String(20), nullable=False)  # ai, template, fallback
    ai_confidence = db.Column(db.Float, nullable=True)  # AI confidence score 0-1
    processing_time = db.Column(db.Float, nullable=True)  # response time in seconds
    ai_tokens_used = db.Column(db.Integer, nullable=True)  # tokens used for AI response
    user_rating = db.Column(db.Integer, nullable=True)  # 1-5 rating
    created_at = db.Column(db.DateTime, default=utc_now, index=True)

    def __repr__(self):
        return f"<ChatbotConversation {self.response_type} at {self.created_at}>"


# Export all models
__all__ = [
    "AdminRole",
    "AdminUser",
    "AnalyticsEvent",
    "ChatMessage",
    "ChatParticipant",
    "ChatRoom",
    "ChatbotConversation",
    "HelpRequest",
    "Notification",
    "NotificationPreference",
    "NotificationQueue",
    "NotificationTemplate",
    "PerformanceMetrics",
    "Permission",
    "PermissionEnum",
    "PriorityEnum",
    "PushSubscription",
    "Request",
    "RequestLog",
    "Role",
    "RoleEnum",
    "RolePermission",
    "User",
    "UserBehavior",
    "UserRole",
    "Volunteer",
]
