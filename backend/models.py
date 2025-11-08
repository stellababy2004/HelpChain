from datetime import datetime


# Request model (moved from helpchain_backend/src/models.py)
def utc_now() -> datetime:
    """Return naive UTC timestamp without relying on datetime.utcnow."""
    from datetime import UTC
    from datetime import datetime as dt

    return dt.now(UTC).replace(tzinfo=None)


try:
    # When the package is imported as `backend.*` prefer package-relative imports.
    from .extensions import db
except Exception:
    # Fall back to top-level import to remain compatible with other import styles.
    from extensions import db


class Request(db.Model):
    __tablename__ = "requests"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    location = db.Column(db.String(100))
    category = db.Column(db.String(50))
    description = db.Column(db.Text)
    urgency = db.Column(db.String(20), default="normal")
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)


import enum
from datetime import UTC, datetime

import pyotp
from flask_login import UserMixin
from sqlalchemy import func
from sqlalchemy.orm import relationship
from werkzeug.security import check_password_hash, generate_password_hash


def utc_now() -> datetime:
    """Return naive UTC timestamp without using deprecated datetime.utcnow."""
    return datetime.now(UTC).replace(tzinfo=None)


# --- Achievements Model ---


# Import Task model for relationships (defined in models_with_analytics)
# Removed circular import - Task relationship uses string reference

# Използваме db инстанцията от extensions (няма да създаваме нова SQLAlchemy())


def utc_now() -> datetime:
    """Return naive UTC timestamp without using deprecated datetime.utcnow."""
    return datetime.now(UTC).replace(tzinfo=None)


# --- Achievements Model ---


class RoleEnum(str, enum.Enum):
    user = "user"
    volunteer = "volunteer"
    moderator = "moderator"
    admin = "admin"
    superadmin = "superadmin"


class AdminRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"  # Пълен достъп до всичко
    ADMIN = "admin"  # Стандартен админ достъп
    MODERATOR = "moderator"  # Ограничен достъп само за модерация


class PermissionEnum(str, enum.Enum):
    # User permissions
    VIEW_PROFILE = "view_profile"
    EDIT_PROFILE = "edit_profile"

    # Volunteer permissions
    VIEW_VOLUNTEERS = "view_volunteers"
    MANAGE_VOLUNTEERS = "manage_volunteers"
    VIEW_REQUESTS = "view_requests"
    MANAGE_REQUESTS = "manage_requests"
    USE_VIDEO_CHAT = "use_video_chat"

    # Moderator permissions
    MODERATE_CONTENT = "moderate_content"
    VIEW_ANALYTICS = "view_analytics"
    MANAGE_CATEGORIES = "manage_categories"

    # Admin permissions
    ADMIN_ACCESS = "admin_access"
    MANAGE_USERS = "manage_users"
    MANAGE_ROLES = "manage_roles"
    SYSTEM_SETTINGS = "system_settings"
    VIEW_AUDIT_LOGS = "view_audit_logs"

    # Super admin permissions
    SUPER_ADMIN = "super_admin"


class PriorityEnum(str, enum.Enum):
    low = "low"
    normal = "normal"
    urgent = "urgent"


class NotificationTypeEnum(str, enum.Enum):
    """Типове нотификации"""

    system = "system"  # Системни съобщения
    request = "request"  # Нови заявки за помощ
    task = "task"  # Задачи и assignments
    message = "message"  # Чат съобщения
    achievement = "achievement"  # Постижения
    reminder = "reminder"  # Напомняния
    alert = "alert"  # Важни предупреждения


class NotificationChannelEnum(str, enum.Enum):
    """Канали за изпращане на нотификации"""

    email = "email"
    app = "app"  # In-app notifications
    push = "push"  # Push notifications


class NotificationStatusEnum(str, enum.Enum):
    """Статус на нотификация"""

    pending = "pending"  # Очаква изпращане
    sent = "sent"  # Изпратена успешно
    delivered = "delivered"  # Доставена (за push/app)
    read = "read"  # Прочетена от потребителя
    failed = "failed"  # Неуспешно изпращане
    cancelled = "cancelled"  # Отменена


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(200), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.Enum(RoleEnum), default=RoleEnum.user, nullable=False, index=True
    )
    twofa_secret_encrypted = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships
    audit_logs = relationship("AuditLog", back_populates="actor")

    def set_password(self, password: str):
        """Set a password hash on the user.

        Minimal validation is applied to avoid creating trivially weak
        passwords programmatically; callers that need stricter rules can
        enforce them before calling this method.
        """
        if not password or len(password) < 8:
            raise ValueError("Паролата трябва да бъде поне 8 символа")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify a plaintext password against the stored hash."""
        try:
            return check_password_hash(self.password_hash, password)
        except Exception:
            return False


class AdminUser(db.Model, UserMixin):
    __tablename__ = "admin_users"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True)
    email = db.Column(db.String(120), unique=True)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.Enum(AdminRole), nullable=False, default=AdminRole.MODERATOR)
    twofa_secret = db.Column(db.String(32))
    backup_codes = db.Column(db.Text, nullable=True)  # JSON масив с backup кодове
    two_factor_enabled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    last_login = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

    @property
    def is_admin(self):
        return True

    def set_password(self, password):
        """Задава парола с валидация"""
        if not password or len(password) < 8:
            raise ValueError("Паролата трябва да бъде поне 8 символа")
        if not any(c.isupper() for c in password):
            raise ValueError("Паролата трябва да съдържа поне една главна буква")
        if not any(c.islower() for c in password):
            raise ValueError("Паролата трябва да съдържа поне една малка буква")
        if not any(c.isdigit() for c in password):
            raise ValueError("Паролата трябва да съдържа поне една цифра")

        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def enable_2fa(self):
        if not self.twofa_secret:
            self.twofa_secret = pyotp.random_base32()
        self.two_factor_enabled = True

    def disable_2fa(self):
        self.two_factor_enabled = False
        self.twofa_secret = None

    @property
    def twofa_enabled(self):
        """Backward compatible alias for two_factor_enabled."""
        return bool(self.two_factor_enabled)

    @twofa_enabled.setter
    def twofa_enabled(self, value):
        self.two_factor_enabled = bool(value)

    def verify_totp(self, token):
        """Проверява TOTP токен"""
        if not self.twofa_secret or not self.two_factor_enabled:
            return False

        try:
            # Валидираме че token е 6 цифри
            if not token or not token.isdigit() or len(token) != 6:
                return False

            totp = pyotp.TOTP(self.twofa_secret)
            return totp.verify(token, valid_window=1)  # 30 секунди tolerance
        except Exception:
            return False

    def get_totp_uri(self):
        if not self.twofa_secret:
            self.twofa_secret = pyotp.random_base32()
        totp = pyotp.TOTP(self.twofa_secret)
        return totp.provisioning_uri(name=self.username, issuer_name="HelpChain")


class Role(db.Model):
    __tablename__ = "roles"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_system_role = db.Column(
        db.Boolean, default=False, nullable=False
    )  # Cannot be deleted
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    role_permissions = relationship(
        "RolePermission", back_populates="role", cascade="all, delete-orphan"
    )


class Permission(db.Model):
    __tablename__ = "permissions"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    codename = db.Column(
        db.String(100), unique=True, nullable=False
    )  # For programmatic checks
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=True)  # Group permissions by category
    is_system_permission = db.Column(
        db.Boolean, default=False, nullable=False
    )  # Cannot be deleted
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    role_permissions = relationship(
        "RolePermission", back_populates="permission", cascade="all, delete-orphan"
    )


class UserRole(db.Model):
    __tablename__ = "user_roles"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    assigned_at = db.Column(db.DateTime, default=utc_now)

    # Relationships
    user = relationship("User", backref="user_roles", foreign_keys=[user_id])
    assigner = relationship(
        "User", foreign_keys=[assigned_by], backref="assigned_user_roles"
    )
    role = relationship("Role", backref="user_roles")


class RolePermission(db.Model):
    __tablename__ = "role_permissions"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    permission_id = db.Column(
        db.Integer, db.ForeignKey("permissions.id"), nullable=False
    )
    granted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    granted_at = db.Column(db.DateTime, default=utc_now)

    # Relationships
    role = relationship("Role", back_populates="role_permissions")
    permission = relationship("Permission", back_populates="role_permissions")
    granter = relationship("User", backref="granted_permissions")


class Volunteer(db.Model):
    __tablename__ = "volunteers"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    skills = db.Column(db.String(500), nullable=True)
    location = db.Column(db.String(100), nullable=True, index=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Геймификация полета
    points = db.Column(db.Integer, default=0, nullable=False)
    level = db.Column(db.Integer, default=1, nullable=False)
    experience = db.Column(db.Integer, default=0, nullable=False)
    total_tasks_completed = db.Column(db.Integer, default=0, nullable=False)
    total_hours_volunteered = db.Column(db.Float, default=0.0, nullable=False)
    rating = db.Column(db.Float, default=0.0, nullable=False)
    rating_count = db.Column(db.Integer, default=0, nullable=False)
    achievements = db.Column(
        db.JSON, default=list, nullable=False
    )  # List of achievement IDs
    badges = db.Column(db.JSON, default=list, nullable=False)  # List of badge IDs
    streak_days = db.Column(db.Integer, default=0, nullable=False)
    last_activity = db.Column(db.DateTime, default=utc_now)
    rank = db.Column(db.Integer, default=0, nullable=False)  # Leaderboard rank

    # Relationships
    # assigned_tasks relationship defined in models_with_analytics.py when Task model is available

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Инициализираме defaults за тестове
        if self.points is None:
            self.points = 0
        if self.level is None:
            self.level = 1
        if self.experience is None:
            self.experience = 0
        if self.total_tasks_completed is None:
            self.total_tasks_completed = 0
        if self.total_hours_volunteered is None:
            self.total_hours_volunteered = 0.0
        if self.rating is None:
            self.rating = 0.0
        if self.rating_count is None:
            self.rating_count = 0
        if self.achievements is None:
            self.achievements = []
        if self.badges is None:
            self.badges = []
        if self.streak_days is None:
            self.streak_days = 0
        if self.rank is None:
            self.rank = 0


class RequestLog(db.Model):
    __tablename__ = "request_logs"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    # request foreign key may point to help_requests or requests depending on
    # legacy schema; use help_requests as canonical table name used elsewhere.
    request_id = db.Column(db.Integer, db.ForeignKey("help_requests.id"))
    action = db.Column(db.String(50))
    old_status = db.Column(db.String(50), nullable=True)
    new_status = db.Column(db.String(50), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())


class Feedback(db.Model):
    __tablename__ = "feedbacks"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    # Геймификация методи
    def add_points(self, points):
        """Добавя точки и проверява за level up"""
        self.points += points
        self.experience += points
        self.check_level_up()

    def check_level_up(self):
        """Проверява дали има level up"""
        required_exp = self.level * 100  # 100 точки за level
        while self.experience >= required_exp:
            self.level += 1
            self.experience -= required_exp
            required_exp = self.level * 100

    def add_rating(self, rating):
        """Добавя рейтинг"""
        try:
            rating = float(rating)
            if 1 <= rating <= 5:
                total_rating = self.rating * self.rating_count
                self.rating_count += 1
                self.rating = round((total_rating + rating) / self.rating_count, 2)
                return True
            return False
        except (ValueError, TypeError):
            return False

    def complete_task(self, hours=1):
        """Завършва задача с валидация"""
        try:
            hours = float(hours)
            if hours <= 0 or hours > 24:  # Максимум 24 часа на задача
                return False

            self.total_tasks_completed += 1
            self.total_hours_volunteered += hours
            self.add_points(50)  # 50 точки за завършена задача
            self.update_streak()
            return True
        except (ValueError, TypeError):
            return False

    def update_streak(self):
        """Обновява streak на активност"""
        now = datetime.now(UTC)
        if self.last_activity:
            # Конвертираме last_activity към UTC ако не е timezone-aware
            if self.last_activity.tzinfo is None:
                last_activity_utc = self.last_activity.replace(tzinfo=UTC)
            else:
                last_activity_utc = self.last_activity.astimezone(UTC)

            days_diff = (now.date() - last_activity_utc.date()).days

            if days_diff == 1:
                self.streak_days += 1
            elif days_diff > 1:
                self.streak_days = 1
            # Ако days_diff == 0, не правим нищо (днес вече е активен)
        else:
            self.streak_days = 1

        self.last_activity = now

    def unlock_achievement(self, achievement_id):
        """Отключва постижение"""
        if achievement_id not in self.achievements:
            self.achievements.append(achievement_id)
            self.add_points(100)  # 100 точки за постижение

    def get_level_progress(self):
        """Връща прогрес към следващия level като процент"""
        required_exp = self.level * 100
        return min(100, (self.experience / required_exp) * 100)

    def get_total_score(self):
        """Връща общ резултат за leaderboard"""
        return (
            self.points * 0.4
            + self.total_tasks_completed * 10
            + self.rating * 20
            + self.level * 50
        )


# --- Achievements Model ---
class Achievement(db.Model):
    __tablename__ = "achievements"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    icon = db.Column(db.String(255), nullable=True)
    category = db.Column(db.String(64), nullable=True)
    points_reward = db.Column(db.Integer, default=0)
    requirement_type = db.Column(db.String(64), nullable=True)
    requirement_value = db.Column(db.String(255), nullable=True)
    rarity = db.Column(db.String(32), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action = db.Column(db.String, nullable=False)
    target_type = db.Column(db.String, nullable=True)
    target_id = db.Column(db.String, nullable=True)
    outcome = db.Column(db.String, nullable=True)
    # metadata е резервирано име в Declarative API — използваме metadata_json вместо това
    metadata_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    actor = relationship("User", back_populates="audit_logs")


class HelpRequest(db.Model):
    __tablename__ = "help_requests"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default="pending", index=True)
    priority = db.Column(
        db.Enum(PriorityEnum), default=PriorityEnum.normal, nullable=False
    )
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    message = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    location_text = db.Column(db.String(255), nullable=True, index=True)
    city = db.Column(db.String(100), nullable=True, index=True)
    region = db.Column(db.String(100), nullable=True, index=True)
    assigned_volunteer_id = db.Column(
        db.Integer, db.ForeignKey("volunteers.id"), nullable=True, index=True
    )
    completed_at = db.Column(db.DateTime, nullable=True, index=True)
    source_channel = db.Column(db.String(50), nullable=True, index=True)

    # Relationships
    assigned_volunteer = relationship(
        "Volunteer",
        backref=db.backref("assigned_help_requests", lazy="dynamic"),
        foreign_keys=[assigned_volunteer_id],
    )

    @property
    def request_type(self):
        """Alias for legacy code using title as request type."""
        return self.title

    @request_type.setter
    def request_type(self, value):
        self.title = value

    @property
    def problem(self):
        """Provide compatibility with code expecting a problem field."""
        return self.message or self.description

    @problem.setter
    def problem(self, value):
        self.message = value
        self.description = value

    @property
    def location(self):
        """Alias used by legacy code pathways."""
        return self.location_text

    @location.setter
    def location(self, value):
        self.location_text = value

    def mark_completed(self, when=None):
        """Mark request as completed and track completion time."""
        self.status = "completed"
        self.completed_at = when or utc_now()


class ChatRoom(db.Model):
    __tablename__ = "chat_rooms"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, default="Обща стая")
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    messages = db.relationship("ChatMessage", back_populates="room", lazy=True)
    participants = db.relationship("ChatParticipant", back_populates="room", lazy=True)


class ChatParticipant(db.Model):
    __tablename__ = "chat_participants"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("chat_rooms.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    volunteer_id = db.Column(db.Integer, db.ForeignKey("volunteers.id"), nullable=True)
    participant_type = db.Column(
        db.String(20), nullable=False
    )  # user, volunteer, admin
    participant_name = db.Column(db.String(100), nullable=False)
    joined_at = db.Column(db.DateTime, default=utc_now)
    last_seen = db.Column(db.DateTime, default=utc_now)
    is_online = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    room = relationship("ChatRoom", back_populates="participants")
    user = relationship("User", backref="chat_participations")
    volunteer = relationship("Volunteer", backref="chat_participations")


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("chat_rooms.id"), nullable=False)
    sender_id = db.Column(db.Integer, nullable=True)  # Can be user_id or volunteer_id
    sender_type = db.Column(
        db.String(20), nullable=False
    )  # user, volunteer, admin, system
    sender_name = db.Column(db.String(100), nullable=False)
    message_type = db.Column(db.String(20), default="text")  # text, file, image, system
    content = db.Column(db.Text, nullable=False)
    file_url = db.Column(db.String(500), nullable=True)  # For file messages
    file_name = db.Column(db.String(255), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)  # Size in bytes
    reply_to_id = db.Column(
        db.Integer, db.ForeignKey("chat_messages.id"), nullable=True
    )
    created_at = db.Column(db.DateTime, default=utc_now)
    edited_at = db.Column(db.DateTime, nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    room = relationship("ChatRoom", back_populates="messages")
    reply_to = relationship("ChatMessage", remote_side=[id], backref="replies")


class Notification(db.Model):
    """Модел за нотификации (email, app, push) за админи и доброволци"""

    __tablename__ = "notifications"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # Основна информация
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(
        db.Enum(NotificationTypeEnum),
        default=NotificationTypeEnum.system,
        nullable=False,
    )

    # Получател
    recipient_id = db.Column(db.Integer, nullable=False)  # user_id or admin_user_id
    recipient_type = db.Column(
        db.String(20), nullable=False
    )  # "user", "admin", "volunteer"

    # Канали за изпращане
    channels = db.Column(
        db.JSON, default=list, nullable=False
    )  # ["email", "app", "push"]

    # Статус по канал
    email_status = db.Column(
        db.Enum(NotificationStatusEnum), default=NotificationStatusEnum.pending
    )
    app_status = db.Column(
        db.Enum(NotificationStatusEnum), default=NotificationStatusEnum.pending
    )
    push_status = db.Column(
        db.Enum(NotificationStatusEnum), default=NotificationStatusEnum.pending
    )

    # Приоритет и настройки
    priority = db.Column(
        db.Enum(PriorityEnum), default=PriorityEnum.normal, nullable=False
    )
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime, nullable=True)

    # Свързани обекти (опционално)
    related_type = db.Column(
        db.String(50), nullable=True
    )  # "help_request", "task", etc.
    related_id = db.Column(db.Integer, nullable=True)  # ID на свързания обект

    # Notification service fields
    template_id = db.Column(
        db.Integer, db.ForeignKey("notification_templates.id"), nullable=True
    )
    queue_id = db.Column(
        db.Integer, db.ForeignKey("notification_queue.id"), nullable=True
    )
    delivery_channel = db.Column(db.String(20), nullable=True)  # email, push, in_app
    final_subject = db.Column(db.String(200), nullable=True)
    final_title = db.Column(db.String(200), nullable=True)
    final_content = db.Column(db.Text, nullable=True)

    # Допълнителни данни
    extra_data = db.Column(db.JSON, nullable=True)  # Допълнителна информация
    action_url = db.Column(db.String(500), nullable=True)  # URL за действие

    # Технически полета
    scheduled_at = db.Column(db.DateTime, nullable=True)  # За планирани нотификации
    sent_at = db.Column(db.DateTime, nullable=True)  # Кога е изпратена
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Индекси за производителност
    __table_args__ = (
        db.Index("idx_notifications_recipient", "recipient_id", "recipient_type"),
        db.Index("idx_notifications_type", "notification_type"),
        db.Index(
            "idx_notifications_status", "email_status", "app_status", "push_status"
        ),
        db.Index("idx_notifications_created", "created_at"),
        {"extend_existing": True},
    )

    # Relationships
    template = db.relationship("NotificationTemplate", backref="notifications")

    def __repr__(self):
        return f"<Notification {self.id}: {self.title} -> {self.recipient_type}:{self.recipient_id} ({self.notification_type})>"

    @property
    def is_sent(self):
        """Проверява дали нотификацията е изпратена по всички канали"""
        sent_channels = []
        if (
            "email" in self.channels
            and self.email_status == NotificationStatusEnum.sent
        ):
            sent_channels.append("email")
        if "app" in self.channels and self.app_status == NotificationStatusEnum.sent:
            sent_channels.append("app")
        if "push" in self.channels and self.push_status == NotificationStatusEnum.sent:
            sent_channels.append("push")
        return len(sent_channels) == len(self.channels)

    @property
    def is_delivered(self):
        """Проверява дали нотификацията е доставена по всички канали"""
        delivered_channels = []
        if "email" in self.channels and self.email_status in [
            NotificationStatusEnum.sent,
            NotificationStatusEnum.delivered,
        ]:
            delivered_channels.append("email")
        if "app" in self.channels and self.app_status in [
            NotificationStatusEnum.sent,
            NotificationStatusEnum.delivered,
        ]:
            delivered_channels.append("app")
        if "push" in self.channels and self.push_status in [
            NotificationStatusEnum.sent,
            NotificationStatusEnum.delivered,
        ]:
            delivered_channels.append("push")
        return len(delivered_channels) == len(self.channels)

    def mark_as_read(self):
        """Отбелязва нотификацията като прочетена"""
        self.is_read = True
        self.read_at = utc_now()
        db.session.commit()

    def update_channel_status(self, channel, status):
        """Обновява статуса за конкретен канал"""
        if channel == "email":
            self.email_status = status
        elif channel == "app":
            self.app_status = status
        elif channel == "push":
            self.push_status = status

        # Ако всички канали са изпратени, задаваме sent_at
        if self.is_sent and not self.sent_at:
            self.sent_at = utc_now()

        db.session.commit()

    @classmethod
    def create_notification(
        cls,
        title,
        message,
        recipient_id,
        recipient_type,
        notification_type=NotificationTypeEnum.system,
        channels=None,
        priority=PriorityEnum.normal,
        related_type=None,
        related_id=None,
        extra_data=None,
        action_url=None,
        scheduled_at=None,
    ):
        """Създава нова нотификация"""
        if channels is None:
            channels = ["app"]  # Default to in-app notifications

        notification = cls(
            title=title,
            message=message,
            recipient_id=recipient_id,
            recipient_type=recipient_type,
            notification_type=notification_type,
            channels=channels,
            priority=priority,
            related_type=related_type,
            related_id=related_id,
            extra_data=extra_data or {},
            action_url=action_url,
            scheduled_at=scheduled_at,
        )

        db.session.add(notification)
        db.session.commit()
        return notification

    @classmethod
    def get_unread_count(cls, recipient_id, recipient_type):
        """Връща броя непрочетени нотификации за потребител"""
        return cls.query.filter_by(
            recipient_id=recipient_id, recipient_type=recipient_type, is_read=False
        ).count()

    @classmethod
    def get_user_notifications(cls, recipient_id, recipient_type, limit=50, offset=0):
        """Връща нотификациите за потребител"""
        return (
            cls.query.filter_by(
                recipient_id=recipient_id, recipient_type=recipient_type
            )
            .order_by(cls.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    @classmethod
    def mark_all_as_read(cls, recipient_id, recipient_type):
        """Отбелязва всички нотификации като прочетени"""
        cls.query.filter_by(
            recipient_id=recipient_id, recipient_type=recipient_type, is_read=False
        ).update({"is_read": True, "read_at": utc_now()})
        db.session.commit()


class NotificationTemplate(db.Model):
    """Шаблони за нотификации с поддръжка за различни канали"""

    __tablename__ = "notification_templates"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    category = db.Column(
        db.String(50), nullable=False
    )  # system, user, volunteer, admin
    type = db.Column(db.String(50), nullable=False)  # email, push, app, sms

    # Съдържание
    subject = db.Column(db.String(200), nullable=True)  # За email
    title = db.Column(db.String(200), nullable=True)  # За push/app
    content = db.Column(db.Text, nullable=False)  # Основно съдържание
    html_body = db.Column(db.Text, nullable=True)  # За email

    # Настройки
    content_type = db.Column(db.String(20), default="html")  # html, text
    is_active = db.Column(db.Boolean, default=True)
    priority = db.Column(db.Enum(PriorityEnum), default=PriorityEnum.normal)
    auto_send = db.Column(db.Boolean, default=False)  # Автоматично изпращане
    send_delay = db.Column(db.Integer, default=0)  # Закъснение в минути
    expiry_hours = db.Column(db.Integer, default=24)  # Изтичане в часове

    # Променливи (JSON с placeholder-и)
    variables = db.Column(db.JSON, default=list)

    # Метаданни
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<NotificationTemplate {self.name} ({self.category}:{self.type})>"


class NotificationQueue(db.Model):
    """Опашка за нотификации за асинхронна обработка"""

    __tablename__ = "notification_queue"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # Шаблон и получател
    template_id = db.Column(db.Integer, db.ForeignKey("notification_templates.id"))
    recipient_type = db.Column(db.String(20), nullable=False)  # user, admin, volunteer
    recipient_id = db.Column(db.Integer, nullable=True)  # ID на получателя
    recipient_email = db.Column(db.String(255), nullable=False)

    # Персонализация
    personalization_data = db.Column(db.JSON, default=dict)

    # Статус
    status = db.Column(
        db.String(20), default="pending"
    )  # pending, processing, sent, failed
    priority = db.Column(db.Integer, default=0)  # 0=normal, 1=high, 2=urgent

    # Опити за изпращане
    attempts = db.Column(db.Integer, default=0)
    max_attempts = db.Column(db.Integer, default=3)
    last_attempt_at = db.Column(db.DateTime, nullable=True)
    next_attempt_at = db.Column(db.DateTime, nullable=True)

    # Резултати
    sent_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)
    clicked_at = db.Column(db.DateTime, nullable=True)

    # Грешки
    error_message = db.Column(db.Text, nullable=True)

    # Време
    scheduled_for = db.Column(db.DateTime, default=utc_now)

    # Метаданни
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    template = db.relationship("NotificationTemplate", backref="queue_items")

    def __repr__(self):
        return f"<NotificationQueue {self.template.name if self.template else 'unknown'} -> {self.recipient_email} ({self.status})>"


class NotificationPreference(db.Model):
    """Потребителски предпочитания за нотификации"""

    __tablename__ = "notification_preferences"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Категории нотификации
    system_notifications = db.Column(db.Boolean, default=True)
    help_request_notifications = db.Column(db.Boolean, default=True)
    volunteer_notifications = db.Column(db.Boolean, default=True)
    admin_notifications = db.Column(db.Boolean, default=True)
    registration_notifications = db.Column(db.Boolean, default=True)
    feedback_notifications = db.Column(db.Boolean, default=True)
    marketing_notifications = db.Column(db.Boolean, default=False)
    reminder_notifications = db.Column(db.Boolean, default=True)

    # Канали
    email_enabled = db.Column(db.Boolean, default=True)
    push_enabled = db.Column(db.Boolean, default=True)
    app_enabled = db.Column(db.Boolean, default=True)
    sms_enabled = db.Column(db.Boolean, default=False)
    in_app_enabled = db.Column(db.Boolean, default=True)

    # Честота
    frequency = db.Column(
        db.String(20), default="immediate"
    )  # immediate, daily, weekly

    # Quiet hours
    quiet_hours_start = db.Column(db.Time, nullable=True)  # 22:00
    quiet_hours_end = db.Column(db.Time, nullable=True)  # 08:00

    # Метаданни
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    user = db.relationship("User", backref="notification_preferences")

    def __repr__(self):
        return f"<NotificationPreference user={self.user_id} email={self.email_enabled} push={self.push_enabled}>"


class UserActivityTypeEnum(str, enum.Enum):
    """Типове потребителски активности за анализ"""

    # Навигация и преглед
    PAGE_VIEW = "page_view"
    PAGE_EXIT = "page_exit"
    SCROLL = "scroll"
    TIME_SPENT = "time_spent"

    # Взаимодействия
    BUTTON_CLICK = "button_click"
    FORM_SUBMIT = "form_submit"
    FORM_START = "form_start"
    LINK_CLICK = "link_click"
    SEARCH_QUERY = "search_query"

    # Помощ и заявки
    HELP_REQUEST_CREATED = "help_request_created"
    HELP_REQUEST_VIEWED = "help_request_viewed"
    HELP_REQUEST_UPDATED = "help_request_updated"

    # Задачи и доброволци
    TASK_VIEWED = "task_viewed"
    TASK_ACCEPTED = "task_accepted"
    TASK_COMPLETED = "task_completed"
    VOLUNTEER_PROFILE_VIEWED = "volunteer_profile_viewed"

    # Чат и комуникация
    CHAT_MESSAGE_SENT = "chat_message_sent"
    CHAT_ROOM_JOINED = "chat_room_joined"
    VIDEO_CHAT_STARTED = "video_chat_started"

    # Аутентикация
    LOGIN = "login"
    LOGOUT = "logout"
    PASSWORD_RESET = "password_reset"

    # Геймификация
    ACHIEVEMENT_UNLOCKED = "achievement_unlocked"
    POINTS_EARNED = "points_earned"
    LEVEL_UP = "level_up"

    # Грешки и проблеми
    ERROR_OCCURRED = "error_occurred"
    PAGE_NOT_FOUND = "page_not_found"
    FORM_VALIDATION_ERROR = "form_validation_error"

    # Конверсии
    REGISTRATION_COMPLETED = "registration_completed"
    HELP_REQUEST_ASSIGNED = "help_request_assigned"
    TASK_ASSIGNED = "task_assigned"


class UserActivity(db.Model):
    """Модел за проследяване на потребителски активности за AI поведенчески анализ"""

    __tablename__ = "user_activities"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)

    # Потребителска информация
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    session_id = db.Column(db.String(128), nullable=False, index=True)
    user_type = db.Column(
        db.String(20), default="guest"
    )  # guest, user, volunteer, admin

    # Активност
    activity_type = db.Column(db.Enum(UserActivityTypeEnum), nullable=False, index=True)
    activity_description = db.Column(db.String(255), nullable=True)  # Човешко описание

    # Данни за активността (JSON за гъвкавост)
    activity_data = db.Column(db.JSON, nullable=True)

    # Технически детайли
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    device_type = db.Column(db.String(50), nullable=True)  # desktop, mobile, tablet
    browser = db.Column(db.String(100), nullable=True)
    os = db.Column(db.String(100), nullable=True)
    screen_resolution = db.Column(db.String(20), nullable=True)  # 1920x1080

    # Страница и контекст
    page_url = db.Column(db.String(500), nullable=True)
    page_title = db.Column(db.String(255), nullable=True)
    referrer = db.Column(db.String(500), nullable=True)
    referrer_domain = db.Column(db.String(255), nullable=True)

    # Време и продължителност
    timestamp = db.Column(db.DateTime, default=utc_now, index=True)
    duration_ms = db.Column(db.Integer, nullable=True)  # Продължителност в милисекунди
    time_on_page = db.Column(db.Integer, nullable=True)  # Време на страницата в секунди

    # Свързани обекти
    related_type = db.Column(
        db.String(50), nullable=True
    )  # help_request, task, chat_room, etc.
    related_id = db.Column(db.Integer, nullable=True)  # ID на свързания обект

    # Геолокация (опционално)
    country = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    # AI и аналитика
    ai_processed = db.Column(db.Boolean, default=False)  # Дали е обработено от AI
    ai_insights = db.Column(db.JSON, nullable=True)  # AI извлечени прозрения
    sentiment_score = db.Column(
        db.Float, nullable=True
    )  # -1 до 1 за емоционален анализ
    engagement_score = db.Column(db.Float, nullable=True)  # 0-100 за ангажираност

    # A/B тестване и експерименти
    experiment_id = db.Column(db.String(100), nullable=True)
    experiment_variant = db.Column(db.String(100), nullable=True)

    # Допълнителни метаданни
    activity_metadata = db.Column(db.JSON, nullable=True)

    # Индекси за производителност
    __table_args__ = (
        db.Index("idx_user_activities_user_session", "user_id", "session_id"),
        db.Index("idx_user_activities_type_timestamp", "activity_type", "timestamp"),
        db.Index("idx_user_activities_page", "page_url"),
        db.Index("idx_user_activities_related", "related_type", "related_id"),
        {"extend_existing": True},
    )

    def __repr__(self):
        return f"<UserActivity {self.activity_type.value} by {self.user_type}:{self.user_id or 'guest'} at {self.timestamp}>"

    @classmethod
    def log_activity(
        cls,
        user_id=None,
        session_id=None,
        activity_type=None,
        activity_description=None,
        activity_data=None,
        page_url=None,
        related_type=None,
        related_id=None,
        duration_ms=None,
        user_type="guest",
        ip_address=None,
        user_agent=None,
        referrer=None,
        experiment_id=None,
        experiment_variant=None,
        activity_metadata=None,
    ):
        """Логва потребителска активност"""

        # Извличане на технически детайли от user_agent
        device_info = cls._parse_user_agent(user_agent) if user_agent else {}

        # Извличане на domain от referrer
        referrer_domain = None
        if referrer and referrer.strip():
            try:
                from urllib.parse import urlparse

                parsed = urlparse(referrer.strip())
                referrer_domain = parsed.netloc or None
            except (TypeError, ValueError, AttributeError) as e:
                # Логване на грешка при неуспешно парсване на referrer
                try:
                    from flask import current_app

                    current_app.logger.warning(
                        "Could not parse referrer domain from value %r: %s",
                        referrer,
                        e,
                        exc_info=True,
                    )
                except (ImportError, RuntimeError):
                    # Fallback to module logger if Flask context not available
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.warning(
                        "Could not parse referrer domain from value %r: %s",
                        referrer,
                        e,
                        exc_info=True,
                    )
                referrer_domain = None

        activity = cls(
            user_id=user_id,
            session_id=session_id,
            user_type=user_type,
            activity_type=activity_type,
            activity_description=activity_description,
            activity_data=activity_data or {},
            ip_address=ip_address,
            user_agent=user_agent,
            device_type=device_info.get("device_type"),
            browser=device_info.get("browser"),
            os=device_info.get("os"),
            page_url=page_url,
            referrer=referrer,
            referrer_domain=referrer_domain,
            duration_ms=duration_ms,
            related_type=related_type,
            related_id=related_id,
            experiment_id=experiment_id,
            experiment_variant=experiment_variant,
            activity_metadata=activity_metadata or {},
        )

        db.session.add(activity)
        db.session.commit()
        return activity

    @classmethod
    def log_page_view(
        cls,
        user_id=None,
        session_id=None,
        page_url=None,
        page_title=None,
        referrer=None,
        user_type="guest",
        ip_address=None,
        user_agent=None,
        screen_resolution=None,
    ):
        """Логва преглед на страница"""
        return cls.log_activity(
            user_id=user_id,
            session_id=session_id,
            activity_type=UserActivityTypeEnum.PAGE_VIEW,
            activity_description=f"Page view: {page_title or page_url}",
            activity_data={
                "page_title": page_title,
                "screen_resolution": screen_resolution,
            },
            page_url=page_url,
            page_title=page_title,
            referrer=referrer,
            user_type=user_type,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @classmethod
    def log_button_click(
        cls,
        user_id=None,
        session_id=None,
        button_id=None,
        button_text=None,
        page_url=None,
        user_type="guest",
    ):
        """Логва кликване на бутон"""
        return cls.log_activity(
            user_id=user_id,
            session_id=session_id,
            activity_type=UserActivityTypeEnum.BUTTON_CLICK,
            activity_description=f"Button click: {button_text or button_id}",
            activity_data={"button_id": button_id, "button_text": button_text},
            page_url=page_url,
            user_type=user_type,
        )

    @classmethod
    def log_form_submit(
        cls,
        user_id=None,
        session_id=None,
        form_id=None,
        form_type=None,
        page_url=None,
        success=True,
        user_type="guest",
    ):
        """Логва изпращане на форма"""
        return cls.log_activity(
            user_id=user_id,
            session_id=session_id,
            activity_type=UserActivityTypeEnum.FORM_SUBMIT,
            activity_description=f"Form submit: {form_type or form_id}",
            activity_data={
                "form_id": form_id,
                "form_type": form_type,
                "success": success,
            },
            page_url=page_url,
            user_type=user_type,
        )

    @classmethod
    def log_help_request_created(
        cls,
        user_id=None,
        session_id=None,
        request_id=None,
        category=None,
        urgency=None,
        page_url=None,
        user_type="user",
    ):
        """Логва създаване на заявка за помощ"""
        return cls.log_activity(
            user_id=user_id,
            session_id=session_id,
            activity_type=UserActivityTypeEnum.HELP_REQUEST_CREATED,
            activity_description=f"Help request created: {category}",
            activity_data={"category": category, "urgency": urgency},
            page_url=page_url,
            related_type="help_request",
            related_id=request_id,
            user_type=user_type,
        )

    @classmethod
    def log_task_completed(
        cls,
        user_id=None,
        session_id=None,
        task_id=None,
        task_title=None,
        duration_hours=None,
        page_url=None,
        user_type="volunteer",
    ):
        """Логва завършване на задача"""
        return cls.log_activity(
            user_id=user_id,
            session_id=session_id,
            activity_type=UserActivityTypeEnum.TASK_COMPLETED,
            activity_description=f"Task completed: {task_title}",
            activity_data={"task_title": task_title, "duration_hours": duration_hours},
            page_url=page_url,
            related_type="task",
            related_id=task_id,
            user_type=user_type,
        )

    @classmethod
    def log_error(
        cls,
        user_id=None,
        session_id=None,
        error_type=None,
        error_message=None,
        page_url=None,
        user_type="guest",
    ):
        """Логва грешка"""
        return cls.log_activity(
            user_id=user_id,
            session_id=session_id,
            activity_type=UserActivityTypeEnum.ERROR_OCCURRED,
            activity_description=f"Error: {error_type}",
            activity_data={"error_type": error_type, "error_message": error_message},
            page_url=page_url,
            user_type=user_type,
        )

    @staticmethod
    def _parse_user_agent(user_agent):
        """Извлича информация от User-Agent string"""
        if not user_agent:
            return {}

        info = {"device_type": "desktop", "browser": "unknown", "os": "unknown"}

        ua_lower = user_agent.lower()

        # Device type detection
        if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
            info["device_type"] = "mobile"
        elif "tablet" in ua_lower or "ipad" in ua_lower:
            info["device_type"] = "tablet"

        # Browser detection
        if "chrome" in ua_lower and "edg" not in ua_lower:
            info["browser"] = "chrome"
        elif "firefox" in ua_lower:
            info["browser"] = "firefox"
        elif "safari" in ua_lower and "chrome" not in ua_lower:
            info["browser"] = "safari"
        elif "edg" in ua_lower:
            info["browser"] = "edge"

        # OS detection
        if "windows" in ua_lower:
            info["os"] = "windows"
        elif "mac" in ua_lower or "os x" in ua_lower:
            info["os"] = "macos"
        elif "linux" in ua_lower:
            info["os"] = "linux"
        elif "android" in ua_lower:
            info["os"] = "android"
        elif "ios" in ua_lower or "iphone" in ua_lower:
            info["os"] = "ios"

        return info

    @classmethod
    def get_user_session_activities(cls, user_id=None, session_id=None, limit=100):
        """Връща активности за потребителска сесия"""
        query = cls.query
        if user_id:
            query = query.filter_by(user_id=user_id)
        if session_id:
            query = query.filter_by(session_id=session_id)

        return query.order_by(cls.timestamp.desc()).limit(limit).all()

    @classmethod
    def get_page_analytics(cls, page_url, start_date=None, end_date=None):
        """Връща аналитика за конкретна страница"""
        query = cls.query.filter_by(page_url=page_url)

        if start_date:
            query = query.filter(cls.timestamp >= start_date)
        if end_date:
            query = query.filter(cls.timestamp <= end_date)

        return query.all()

    @classmethod
    def get_conversion_funnel(cls, user_id=None, session_id=None):
        """Анализира conversion funnel за потребител"""
        activities = cls.get_user_session_activities(user_id, session_id, limit=1000)

        funnel = {
            "page_views": 0,
            "form_starts": 0,
            "form_submits": 0,
            "help_requests_created": 0,
            "tasks_completed": 0,
        }

        for activity in activities:
            if activity.activity_type == UserActivityTypeEnum.PAGE_VIEW:
                funnel["page_views"] += 1
            elif activity.activity_type == UserActivityTypeEnum.FORM_START:
                funnel["form_starts"] += 1
            elif activity.activity_type == UserActivityTypeEnum.FORM_SUBMIT:
                funnel["form_submits"] += 1
            elif activity.activity_type == UserActivityTypeEnum.HELP_REQUEST_CREATED:
                funnel["help_requests_created"] += 1
            elif activity.activity_type == UserActivityTypeEnum.TASK_COMPLETED:
                funnel["tasks_completed"] += 1

        return funnel

    @classmethod
    def get_user_engagement_score(cls, user_id, days=30):
        """Изчислява engagement score за потребител"""
        from datetime import timedelta

        start_date = utc_now() - timedelta(days=days)

        activities = cls.query.filter(
            cls.user_id == user_id, cls.timestamp >= start_date
        ).all()

        if not activities:
            return 0.0

        # Пресмятане на engagement score базирано на различни фактори
        score = 0.0
        weights = {
            UserActivityTypeEnum.PAGE_VIEW: 1,
            UserActivityTypeEnum.BUTTON_CLICK: 2,
            UserActivityTypeEnum.FORM_SUBMIT: 5,
            UserActivityTypeEnum.HELP_REQUEST_CREATED: 10,
            UserActivityTypeEnum.TASK_COMPLETED: 15,
            UserActivityTypeEnum.CHAT_MESSAGE_SENT: 3,
            UserActivityTypeEnum.ACHIEVEMENT_UNLOCKED: 8,
        }

        for activity in activities:
            weight = weights.get(activity.activity_type, 1)
            # По-висока тежест за скорошни активности
            days_since = (utc_now() - activity.timestamp).days
            recency_multiplier = max(0.1, 1 - (days_since / days))
            score += weight * recency_multiplier

        # Нормализиране към 0-100
        max_possible_score = (
            sum(weights.values()) * days * 0.5
        )  # Приблизителна максимална стойност
        normalized_score = min(100.0, (score / max_possible_score) * 100)

        return round(normalized_score, 2)


# =============================================================================
# PUSH NOTIFICATIONS
# =============================================================================


class PushSubscription(db.Model):
    """Push notification subscriptions for volunteers"""

    __tablename__ = "push_subscriptions"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    volunteer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    endpoint = db.Column(db.String(500), nullable=False, unique=True)
    p256dh_key = db.Column(db.String(200), nullable=False)
    auth_key = db.Column(db.String(200), nullable=False)
    user_agent = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    notifications_sent = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utc_now)
    last_used = db.Column(db.DateTime, default=utc_now)

    # Relationships
    volunteer = db.relationship(
        "User", backref=db.backref("push_subscriptions", lazy=True)
    )

    def __repr__(self):
        return f"<PushSubscription volunteer={self.volunteer_id} endpoint={self.endpoint[:50]}...>"

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "volunteer_id": self.volunteer_id,
            "endpoint": self.endpoint,
            "is_active": self.is_active,
            "notifications_sent": self.notifications_sent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_used": self.last_used.isoformat() if self.last_used else None,
        }


class FailedEmail(db.Model):
    """Model for storing failed emails in dead letter queue"""

    __tablename__ = "failed_emails"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(255), nullable=False, index=True)
    subject = db.Column(db.String(500), nullable=False)
    template = db.Column(db.String(255), nullable=False)
    context = db.Column(db.Text, nullable=True)  # JSON string of template context
    error_message = db.Column(db.Text, nullable=False)
    retry_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    last_attempt_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<FailedEmail id={self.id} recipient={self.recipient} subject={self.subject[:50]}...>"

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "recipient": self.recipient,
            "subject": self.subject,
            "template": self.template,
            "context": self.context,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_attempt_at": (
                self.last_attempt_at.isoformat() if self.last_attempt_at else None
            ),
        }
