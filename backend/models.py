from sqlalchemy import func
import enum
from sqlalchemy.orm import relationship
from datetime import datetime

# Try multiple import strategies for extensions
try:
    from .extensions import db
except ImportError:
    try:
        from extensions import db
    except ImportError:
        # Last resort - create a new db instance (for testing)
        from flask_sqlalchemy import SQLAlchemy

        db = SQLAlchemy()

from flask_login import UserMixin
import pyotp
from werkzeug.security import generate_password_hash, check_password_hash

# Import Task model for relationships (defined in models_with_analytics)
try:
    from .models_with_analytics import Task
except ImportError:
    # For testing environments where models_with_analytics might not be available
    Task = None

# Използваме db инстанцията от extensions (няма да създаваме нова SQLAlchemy())


class RoleEnum(str, enum.Enum):
    user = "user"
    volunteer = "volunteer"
    moderator = "moderator"
    admin = "admin"
    superadmin = "superadmin"


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


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(200), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(RoleEnum), default=RoleEnum.user, nullable=False)
    twofa_secret_encrypted = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships
    audit_logs = relationship("AuditLog", back_populates="actor")


class AdminUser(db.Model, UserMixin):
    __tablename__ = "admin_users"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True)
    email = db.Column(db.String(120), unique=True)
    password_hash = db.Column(db.String(128))
    twofa_secret = db.Column(db.String(32))
    twofa_enabled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
        self.twofa_enabled = True

    def disable_2fa(self):
        self.twofa_enabled = False
        self.twofa_secret = None

    def verify_totp(self, token):
        """Проверява TOTP токен"""
        if not self.twofa_secret or not self.twofa_enabled:
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
    is_system_role = db.Column(db.Boolean, default=False, nullable=False)  # Cannot be deleted
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    role_permissions = relationship(
        "RolePermission", back_populates="role", cascade="all, delete-orphan"
    )


class Permission(db.Model):
    __tablename__ = "permissions"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    codename = db.Column(db.String(100), unique=True, nullable=False)  # For programmatic checks
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), nullable=True)  # Group permissions by category
    is_system_permission = db.Column(db.Boolean, default=False, nullable=False)  # Cannot be deleted
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="user_roles", foreign_keys=[user_id])
    assigner = relationship("User", foreign_keys=[assigned_by], backref="assigned_user_roles")
    role = relationship("Role", backref="user_roles")


class RolePermission(db.Model):
    __tablename__ = "role_permissions"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey("permissions.id"), nullable=False)
    granted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    granted_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    location = db.Column(db.String(100), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Геймификация полета
    points = db.Column(db.Integer, default=0, nullable=False)
    level = db.Column(db.Integer, default=1, nullable=False)
    experience = db.Column(db.Integer, default=0, nullable=False)
    total_tasks_completed = db.Column(db.Integer, default=0, nullable=False)
    total_hours_volunteered = db.Column(db.Float, default=0.0, nullable=False)
    rating = db.Column(db.Float, default=0.0, nullable=False)
    rating_count = db.Column(db.Integer, default=0, nullable=False)
    achievements = db.Column(db.JSON, default=list, nullable=False)  # List of achievement IDs
    badges = db.Column(db.JSON, default=list, nullable=False)  # List of badge IDs
    streak_days = db.Column(db.Integer, default=0, nullable=False)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    rank = db.Column(db.Integer, default=0, nullable=False)  # Leaderboard rank

    # Relationships
    # assigned_tasks relationship defined in models_with_analytics.py when Task model is available
    assigned_tasks = db.relationship("Task", back_populates="volunteer", lazy=True)

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
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        if self.last_activity:
            # Конвертираме last_activity към UTC ако не е timezone-aware
            if self.last_activity.tzinfo is None:
                last_activity_utc = self.last_activity.replace(tzinfo=timezone.utc)
            else:
                last_activity_utc = self.last_activity.astimezone(timezone.utc)

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
            self.points * 0.4 + self.total_tasks_completed * 10 + self.rating * 20 + self.level * 50
        )


class Achievement(db.Model):
    __tablename__ = "achievements"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.String(50), primary_key=True)  # Unique achievement ID
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    icon = db.Column(db.String(50), nullable=False)  # FontAwesome icon class
    category = db.Column(db.String(50), nullable=False)  # tasks, rating, streak, etc.
    points_reward = db.Column(db.Integer, default=100, nullable=False)
    requirement_type = db.Column(db.String(50), nullable=False)  # count, value, streak
    requirement_value = db.Column(db.Integer, nullable=False)
    rarity = db.Column(
        db.String(20), default="common", nullable=False
    )  # common, rare, epic, legendary
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


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
    status = db.Column(db.String(50), default="Pending")
    priority = db.Column(db.Enum(PriorityEnum), default=PriorityEnum.normal, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    message = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)


class ChatRoom(db.Model):
    __tablename__ = "chat_rooms"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, default="Обща стая")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship("ChatMessage", back_populates="room", lazy=True)
    participants = db.relationship("ChatParticipant", back_populates="room", lazy=True)


class ChatParticipant(db.Model):
    __tablename__ = "chat_participants"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("chat_rooms.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    volunteer_id = db.Column(db.Integer, db.ForeignKey("volunteers.id"), nullable=True)
    participant_type = db.Column(db.String(20), nullable=False)  # user, volunteer, admin
    participant_name = db.Column(db.String(100), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    is_online = db.Column(db.Boolean, default=True)

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
    sender_type = db.Column(db.String(20), nullable=False)  # user, volunteer, admin, system
    sender_name = db.Column(db.String(100), nullable=False)
    message_type = db.Column(db.String(20), default="text")  # text, file, image, system
    content = db.Column(db.Text, nullable=False)
    file_url = db.Column(db.String(500), nullable=True)  # For file messages
    file_name = db.Column(db.String(255), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)  # Size in bytes
    reply_to_id = db.Column(db.Integer, db.ForeignKey("chat_messages.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    edited_at = db.Column(db.DateTime, nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)

    # Relationships
    room = relationship("ChatRoom", back_populates="messages")
    reply_to = relationship("ChatMessage", remote_side=[id], backref="replies")
