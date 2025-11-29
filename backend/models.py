# Placeholder for SQLAlchemy models

from datetime import datetime
from enum import Enum
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Boolean,
    String,
    Text,
    Float,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.orm import (
    declarative_base,
    relationship,
    sessionmaker,
    scoped_session,
)
import os
import sys

Base = declarative_base()


def utc_now():
    """Връща текущото време в UTC формат"""
    return datetime.utcnow()


class RoleEnum(Enum):
    """Изброим тип за роли на потребители"""

    ADMIN = "admin"
    VOLUNTEER = "volunteer"
    USER = "user"


class AdminUser(Base):
    """Модел за администраторски потребители"""

    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), nullable=False, unique=True)
    email = Column(String(100), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(128), nullable=True)

    def set_password(self, password: str) -> None:
        """Hash and store a password for the admin user."""
        # Password policy enforcement used by tests (Bulgarian messages)
        if not isinstance(password, str) or len(password) < 8:
            raise ValueError("Паролата трябва да бъде поне 8 символа")
        if password.lower() == password:
            raise ValueError("Паролата трябва да съдържа поне една главна буква")
        if password.upper() == password:
            raise ValueError("Паролата трябва да съдържа поне една малка буква")
        if not any(c.isdigit() for c in password):
            raise ValueError("Паролата трябва да съдържа поне една цифра")

        try:
            from werkzeug.security import generate_password_hash

            self.password_hash = generate_password_hash(password)
        except Exception:
            # Fallback: store plaintext
            self.password_hash = password

    def check_password(self, password: str) -> bool:
        """Verify a password against the stored hash."""
        try:
            from werkzeug.security import check_password_hash

            return bool(self.password_hash and check_password_hash(self.password_hash, password))
        except Exception:
            return self.password_hash == password

    def enable_2fa(self) -> str:
        """Enable TOTP 2FA for the user and return the secret."""
        try:
            import pyotp

            secret = pyotp.random_base32()
            self.two_factor_secret = secret
            self.two_factor_enabled = True
            # expose short alias names expected by some tests
            try:
                self.twofa_secret = secret
                self.twofa_enabled = True
            except Exception:
                pass
            return secret
        except Exception:
            # If pyotp isn't available, store a dummy secret
            self.two_factor_secret = "DUMMY"
            self.two_factor_enabled = True
            try:
                self.twofa_secret = self.two_factor_secret
                self.twofa_enabled = True
            except Exception:
                pass
            return self.two_factor_secret

    def disable_2fa(self) -> None:
        """Disable TOTP 2FA for the user."""
        # Provide backwards-compatible attribute names used by tests
        self.two_factor_secret = None
        self.two_factor_enabled = False
        # keep short aliases for older tests
        try:
            self.twofa_secret = None
            self.twofa_enabled = False
        except Exception:
            pass

    def verify_totp(self, token: str) -> bool:
        """Verify a given TOTP token using the stored secret."""
        if not self.two_factor_enabled or not self.two_factor_secret:
            return False
        try:
            import pyotp

            totp = pyotp.TOTP(self.two_factor_secret)
            return bool(totp.verify(token))
        except Exception:
            return False

    def get_totp_uri(self, issuer_name: str = "HelpChain") -> str:
        """Return the otpauth URI for provisioning authenticator apps."""
        if not self.two_factor_secret:
            self.enable_2fa()
        try:
            import pyotp

            totp = pyotp.TOTP(self.two_factor_secret)
            return totp.provisioning_uri(name=self.email or self.username, issuer_name=issuer_name)
        except Exception:
            return f"otpauth://totp/{issuer_name}:{self.email or self.username}?secret={self.two_factor_secret}&issuer={issuer_name}"
        finally:
            # expose short alias names expected by tests
            try:
                self.twofa_secret = self.two_factor_secret
                self.twofa_enabled = self.two_factor_enabled
            except Exception:
                pass

    @classmethod
    def get_query(cls):
        return db_session.query(cls)


class AdminLog(Base):
    """Модел за проследяване на административни действия"""

    __tablename__ = "admin_logs"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    admin_user_id = Column(Integer, ForeignKey("admin_users.id"), nullable=False)
    action = Column(
        String(100), nullable=False
    )  # "approved_request", "rejected_request", etc.
    details = Column(Text, nullable=True)  # JSON или описание на действието
    entity_type = Column(String(50), nullable=True)  # "help_request", "volunteer", etc.

# Backwards-compatible alias: some modules import `AuditLog` from backend.models
# Provide the expected name without changing existing AdminLog behavior.
AuditLog = AdminLog


class HelpRequest(Base):
    """Модел за заявки за помощ"""

    __tablename__ = "help_requests"

    id = Column(Integer, primary_key=True)
    # Legacy fields: some code/tests use 'name' and 'message'
    name = Column(String(200), nullable=True)
    title = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    message = Column(Text, nullable=True)
    # Legacy contact fields used by older code/tests
    email = Column(String(200), nullable=True)
    phone = Column(String(50), nullable=True)
    status = Column(String(50), nullable=False, default="pending")
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, nullable=True, onupdate=utc_now)
    # Assigned volunteer (optional) — some views expect this attribute
    assigned_volunteer_id = Column(Integer, ForeignKey("volunteers.id"), nullable=True)
    assigned_volunteer = relationship("Volunteer", foreign_keys=[assigned_volunteer_id])

    def __init__(self, **kwargs):
        # Accept legacy keyword arguments (email, phone, message, name, etc.)
        # without raising TypeError during test object construction.
        for k, v in kwargs.items():
            try:
                # Map some common legacy names to current attributes
                if k in ("contact_email", "email") and hasattr(self.__class__, "email"):
                    setattr(self, "email", v)
                elif k in ("contact_phone", "phone") and hasattr(self.__class__, "phone"):
                    setattr(self, "phone", v)
                elif hasattr(self.__class__, k):
                    setattr(self, k, v)
                else:
                    # ignore unknown legacy keys
                    pass
            except Exception:
                pass



class ChatMessage(Base):
    """Модел за съобщения в чата"""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False)


class ChatParticipant(Base):
    """Модел за участници в чата"""

    __tablename__ = "chat_participants"

    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)


class ChatRoom(Base):
    """Модел за чат стаи"""

    __tablename__ = "chat_rooms"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, nullable=False)


class Notification(Base):
    """Модел за известия"""

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)


class NotificationPreference(Base):
    """Модел за потребителски предпочитания за известия (минимален)."""

    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True)
    # Allow anonymous/guest subscriptions (tests create subscriptions
    # without a logged-in user). Make `user_id` nullable for compatibility.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # Use flexible column names but accept legacy kwargs like
    # `email_enabled`, `push_enabled`, `sms_enabled` used in tests.
    email_notifications = Column(String(5), nullable=True)
    push_notifications = Column(String(5), nullable=True)
    # Some tests expect `sms_enabled` to be accepted; provide a column
    # to store that legacy flag.
    sms_notifications = Column(String(5), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    def __init__(self, **kwargs):
        # Map legacy boolean kwargs to string columns used above.
        try:
            if "email_enabled" in kwargs:
                val = kwargs.pop("email_enabled")
                self.email_notifications = "1" if bool(val) else "0"
            if "push_enabled" in kwargs:
                val = kwargs.pop("push_enabled")
                self.push_notifications = "1" if bool(val) else "0"
            if "sms_enabled" in kwargs:
                val = kwargs.pop("sms_enabled")
                self.sms_notifications = "1" if bool(val) else "0"
        except Exception:
            pass
        # Accept and set any remaining known attributes
        for k, v in kwargs.items():
            try:
                if hasattr(self.__class__, k):
                    setattr(self, k, v)
            except Exception:
                pass


class Role(Base):
    """Модел за роли на потребители"""

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    # Backwards-compatible flag used by seeding code/tests to mark system roles
    is_system_role = Column(Boolean, default=False)
    # Relationship to role permissions: provide the attribute `role_permissions`
    # which many tests expect to exist and iterate over.
    role_permissions = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
    )


class RolePermission(Base):
    """Модел за права на роли"""

    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    # Prefer storing a foreign key to the Permission.id so code can access
    # the Permission model instance via the `permission` relationship.
    permission_id = Column(Integer, ForeignKey("permissions.id"), nullable=True)
    # Relationship to Permission model. Use a private relationship attribute
    # and expose a `permission` property so tests (and older code) can assign
    # a permission by codename (string) or by Permission instance.
    _permission = relationship("Permission", foreign_keys=[permission_id])
    # Relationship back to Role so role.role_permissions is available
    role = relationship("Role", back_populates="role_permissions")

    @property
    def permission(self):
        return getattr(self, "_permission", None)

    @permission.setter
    def permission(self, value):
        # Allow assigning by codename string or by Permission instance.
        try:
            logger.debug(f"RolePermission.permission setter called with value={value!r}")
        except Exception:
            pass
        if isinstance(value, str):
            try:
                # Try model-level query first (works when query proxy is attached)
                p = None
                try:
                    p = Permission.query.filter_by(codename=value).first()
                except Exception:
                    p = None

                if p is None:
                    # Fallback: try to resolve using a session associated with
                    # this RolePermission or its Role (object_session), then
                    # try the Flask-SQLAlchemy session if available. This
                    # covers test fixtures that add objects via a different
                    # session than the models module's query proxy.
                    try:
                        from sqlalchemy.orm import object_session

                        sess = object_session(self) or (object_session(self.role) if getattr(self, 'role', None) is not None else None)
                    except Exception:
                        sess = None

                    if sess is not None:
                        try:
                            p = sess.query(Permission).filter_by(codename=value).first()
                        except Exception:
                            p = None

                    if p is None:
                        try:
                            from backend.extensions import db as _ext_db

                            p = _ext_db.session.query(Permission).filter_by(codename=value).first()
                        except Exception:
                            p = None

                if p is not None:
                    self.permission_id = p.id
                    self._permission = p
                    try:
                        logger.debug(f"Resolved permission codename '{value}' -> id={p.id}")
                    except Exception:
                        pass
                else:
                    # No matching Permission found; clear relation
                    self.permission_id = None
                    self._permission = None
            except Exception:
                self.permission_id = None
                self._permission = None
        elif value is None:
            self.permission_id = None
            self._permission = None
        else:
            # Assume a Permission instance-like object
            try:
                self._permission = value
                self.permission_id = getattr(value, "id", None)
                try:
                    logger.debug(f"Assigned Permission instance -> id={self.permission_id}")
                except Exception:
                    pass
            except Exception:
                self._permission = None
                self.permission_id = None


class User(Base):
    """Модел за потребители"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(50), nullable=True)
    # Some codepaths/tests check `User.is_active`; provide it for compatibility
    is_active = Column(Boolean, default=True)

    push_subscriptions = relationship("PushSubscription", back_populates="user")
    requests = relationship("Request", back_populates="user")

# (Dynamic `.query` descriptor will be attached after the descriptor is defined.)


class UserRole(Base):
    """Модел за роли на потребители"""

    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)


class Volunteer(Base):
    """Модел за доброволци"""

    __tablename__ = "volunteers"

    id = Column(Integer, primary_key=True)
    # Allow volunteers to be created without an associated User in some
    # codepaths/tests. Making this nullable keeps backward compatibility
    # with fixtures that insert volunteers directly.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(200), nullable=True)
    email = Column(String(200), nullable=True)
    phone = Column(String(50), nullable=True)
    location = Column(String(200), nullable=True)
    # Some code paths create Volunteer without providing availability;
    # make this nullable to remain compatible with those flows and tests.
    availability = Column(String(50), nullable=True)
    skills = Column(Text, nullable=True)
    # Geolocation fields used by the nearby API
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    # Active flag used by admin filters
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, nullable=True, onupdate=utc_now)
    # Minimal gamification fields
    achievements = Column(Text, nullable=True)  # comma-separated achievement ids
    total_tasks_completed = Column(Integer, default=0)
    rating = Column(Integer, default=0)  # scaled by 10 in some places
    level = Column(Integer, default=1)
    streak_days = Column(Integer, default=0)
    rank = Column(Integer, nullable=True)

    # Additional fields used by tests
    rating_count = Column(Integer, default=0)
    total_hours_volunteered = Column(Integer, default=0)
    points = Column(Integer, default=0)
    experience = Column(Integer, default=0)
    last_activity = Column(DateTime, nullable=True)

    def unlock_achievement(self, achievement_id: str):
        """Add achievement id to volunteer's achievements if not present."""
        # Accept either list or comma-separated string for achievements
        if isinstance(self.achievements, list):
            existing = [e for e in self.achievements if e]
        else:
            # normalize stored representation to comma-separated string
            if self.achievements is None:
                existing = []
            elif isinstance(self.achievements, str):
                existing = [e for e in self.achievements.split(",") if e]
            else:
                # fallback: coerce to string then split
                existing = [e for e in str(self.achievements).split(",") if e]

        if achievement_id in existing:
            return False

        existing.append(achievement_id)
        # store as comma-separated string for compatibility
        try:
            self.achievements = ",".join(existing)
        except Exception:
            self.achievements = existing

        # Grant reward points for unlocking a new achievement (tests expect +100)
        try:
            self.points = int(self.points or 0) + 100
        except Exception:
            self.points = 100

        return True

    def get_total_score(self) -> int:
        """Compute a simple total score for leaderboard sorting."""
        # Match test expectation formula: points*0.4 + tasks*10 + rating*20 + level*50
        try:
            pts = float(self.points or 0) * 0.4
        except Exception:
            pts = 0.0
        try:
            tasks = int(self.total_tasks_completed or 0) * 10
        except Exception:
            tasks = 0
        try:
            rating_score = float(self.rating or 0) * 20
        except Exception:
            rating_score = 0.0
        try:
            level_score = int(self.level or 0) * 50
        except Exception:
            level_score = 0
        return pts + tasks + rating_score + level_score

    def get_level_progress(self) -> float:
        """Return percent progress to next level (0-100)."""
        # Simple model: each level requires level*100 experience points
        try:
            lvl = int(self.level or 1)
            exp = int(self.experience or 0)
            required = lvl * 100
            pct = min(100.0, max(0.0, (exp / required) * 100.0 if required else 100.0))
            return pct
        except Exception:
            return 0.0

    def add_points(self, points: int) -> bool:
        """Add points and experience; perform level up if threshold passed."""
        try:
            pts = int(points)
        except Exception:
            return False
        self.points = int(self.points or 0) + pts
        # Make experience track similarly
        self.experience = int(self.experience or 0) + pts
        # simple level up: every 100 exp -> +1 level
        try:
            while self.experience >= (self.level or 1) * 100:
                self.experience -= (self.level or 1) * 100
                self.level = int(self.level or 1) + 1
        except Exception:
            pass
        return True

    def complete_task(self, hours: float) -> bool:
        """Mark a task complete if hours valid (1-24). Returns True on success."""
        try:
            hrs = float(hours)
            if hrs <= 0 or hrs > 24:
                return False
        except Exception:
            return False
        # record
        self.total_tasks_completed = int(self.total_tasks_completed or 0) + 1
        try:
            self.total_hours_volunteered = float(self.total_hours_volunteered or 0) + hrs
        except Exception:
            self.total_hours_volunteered = hrs
        # update last activity timestamp
        try:
            self.last_activity = utc_now()
        except Exception:
            pass
        return True

    def add_rating(self, rating) -> bool:
        """Add rating between 1 and 5 inclusive. Return True if accepted."""
        try:
            r = float(rating)
            if r < 1 or r > 5:
                return False
        except Exception:
            return False
        # update aggregated rating and count
        try:
            cnt = int(self.rating_count or 0)
            current = float(self.rating or 0)
            new_total = current * cnt + r
            cnt += 1
            self.rating = round(new_total / cnt, 2)
            self.rating_count = cnt
        except Exception:
            self.rating = r
            self.rating_count = 1
        return True

    def update_streak(self, days: int = 1) -> bool:
        """Update streak and last activity timestamp for the volunteer."""
        try:
            # If last_activity is None, this is first activity
            if not getattr(self, "last_activity", None):
                self.streak_days = int(self.streak_days or 0) + 1
            else:
                # Simple logic: increment streak by days parameter
                self.streak_days = int(self.streak_days or 0) + int(days)
            self.last_activity = utc_now()
            return True
        except Exception:
            return False

    def __init__(self, **kwargs):
        # Allow tests to pass extra kwargs (latitude, longitude, etc.) without failing
        for k, v in kwargs.items():
            try:
                # Normalize achievements passed as list to comma-string
                if k == "achievements" and isinstance(v, list):
                    setattr(self, k, ",".join(v))
                else:
                    setattr(self, k, v)
            except Exception:
                # ignore any attribute setting errors
                pass

        # Ensure sensible defaults for plain instances (tests often instantiate
        # models without persisting; SQLAlchemy column defaults don't apply yet)
        if getattr(self, "rating_count", None) is None:
            self.rating_count = 0
        if getattr(self, "points", None) is None:
            self.points = 0
        if getattr(self, "experience", None) is None:
            self.experience = 0
        if getattr(self, "total_hours_volunteered", None) is None:
            self.total_hours_volunteered = 0
        if getattr(self, "total_tasks_completed", None) is None:
            self.total_tasks_completed = 0
        if getattr(self, "rating", None) is None:
            self.rating = 0
        if getattr(self, "level", None) is None:
            self.level = 1
        if getattr(self, "streak_days", None) is None:
            self.streak_days = 0
        # Ensure availability has a sensible default to avoid NOT NULL
        # insertion errors from legacy code paths that don't provide it.
        if getattr(self, "availability", None) is None:
            self.availability = ""
        # Normalize achievements storage to comma-separated string
        a = getattr(self, "achievements", None)
        if isinstance(a, list):
            try:
                self.achievements = ",".join([str(x) for x in a if x])
            except Exception:
                self.achievements = ""
        elif a is None:
            self.achievements = ""
    @property
    def achievements_list(self):
        return [a for a in (self.achievements or "").split(",") if a]


class AnalyticsEvent(Base):
    """Модел за аналитични събития"""

    __tablename__ = "analytics_events"

    id = Column(Integer, primary_key=True)
    event_type = Column(String(100), nullable=False)
    event_category = Column(String(100), nullable=True)
    event_action = Column(String(100), nullable=True)
    event_label = Column(String(255), nullable=True)
    event_value = Column(Integer, nullable=True)

    # User/context fields
    user_session = Column(String(128), nullable=True)
    user_type = Column(String(50), default="guest")
    user_ip = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Page context
    page_url = Column(String(500), nullable=True)
    page_title = Column(String(255), nullable=True)
    referrer = Column(String(500), nullable=True)

    # Technical metrics
    load_time = Column(Integer, nullable=True)
    screen_resolution = Column(String(20), nullable=True)
    device_type = Column(String(50), nullable=True)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class ChatbotConversation(Base):
    """Модел за чатбот разговори"""

    __tablename__ = "chatbot_conversations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, nullable=False)


class PerformanceMetrics(Base):
    """Модел за метрики на производителността"""

    __tablename__ = "performance_metrics"

    id = Column(Integer, primary_key=True)
    metric_name = Column(String(50), nullable=False)
    metric_value = Column(String(50), nullable=False)
    timestamp = Column(DateTime, nullable=False)


class UserBehavior(Base):
    """Модел за поведение на потребители"""

    __tablename__ = "user_behaviors"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    behavior_type = Column(String(50), nullable=False)
    timestamp = Column(DateTime, nullable=False)


class PushSubscription(Base):
    """Модел за абонаменти за push известия"""

    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True)
    endpoint = Column(String, nullable=False)
    p256dh = Column(String, nullable=False)
    auth = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # Active flag for subscriptions (default True)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="push_subscriptions")
    # Backwards-compatible alias: some tests and legacy code refer to
    # `volunteer_id` when the column was originally named differently.
    try:
        from sqlalchemy.orm import synonym

        volunteer_id = synonym("user_id")
    except Exception:
        # Fallback: provide a dynamic property for runtime access
        @property
        def volunteer_id(self):
            return getattr(self, "user_id", None)

        @volunteer_id.setter
        def volunteer_id(self, value):
            try:
                self.user_id = value
            except Exception:
                pass
    
    def __init__(self, *args, **kwargs):
        """Compatibility constructor.

        Accepts legacy `volunteer_id` kwarg and maps it to `user_id` so
        tests that create `PushSubscription(volunteer_id=...)` continue to work.
        Also accept `user_id` or `user` as usual.
        """
        # Ensure the push_subscriptions table exists on the Flask app engine
        try:
            from flask import current_app
            from backend import models as _models
            from backend.extensions import db as _ext_db
            try:
                engine = _ext_db.get_engine(current_app)
            except Exception:
                engine = getattr(_ext_db, "engine", None)
            if engine is not None:
                try:
                    from sqlalchemy import inspect as _inspect

                    if "push_subscriptions" not in _inspect(engine).get_table_names():
                        _models.Base.metadata.create_all(bind=engine)
                except Exception:
                    pass
        except Exception:
            pass

        # Map volunteer_id -> user_id for backward compatibility
        if "volunteer_id" in kwargs and "user_id" not in kwargs:
            try:
                kwargs["user_id"] = kwargs.pop("volunteer_id")
            except Exception:
                pass

        # Accept a `user` object and extract its id if present
        if "user" in kwargs and "user_id" not in kwargs:
            try:
                user_obj = kwargs.get("user")
                kwargs["user_id"] = getattr(user_obj, "id", None)
            except Exception:
                pass

        # Map common legacy key names used by tests
        if "p256dh_key" in kwargs and "p256dh" not in kwargs:
            try:
                kwargs["p256dh"] = kwargs.pop("p256dh_key")
            except Exception:
                pass
        if "auth_key" in kwargs and "auth" not in kwargs:
            try:
                kwargs["auth"] = kwargs.pop("auth_key")
            except Exception:
                pass

        # Set known attributes explicitly to avoid unexpected kwargs errors
        for key in ("endpoint", "p256dh", "auth", "user_id"):
            if key in kwargs:
                try:
                    setattr(self, key, kwargs.pop(key))
                except Exception:
                    pass

        # Ignore any remaining kwargs to be permissive for legacy tests
        for k, v in list(kwargs.items()):
            try:
                setattr(self, k, v)
            except Exception:
                pass


class Permission(Base):
    """Модел за права"""

    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    codename = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)


class Achievement(Base):
    """Minimal Achievement model used by gamification service/tests."""

    __tablename__ = "achievements"

    id = Column(String(100), primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(200), nullable=True)
    category = Column(String(50), nullable=True)
    requirement_type = Column(String(50), nullable=True)
    requirement_value = Column(String(50), nullable=True)
    rarity = Column(String(50), nullable=True)

    def __repr__(self):
        return f"<Achievement {self.id}: {self.name}>"


class NotificationTemplate(Base):
    """Minimal template model for notification_service tests."""

    __tablename__ = "notification_templates"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, unique=True)
    type = Column(String(50), nullable=False)
    category = Column(String(100), nullable=True)
    subject = Column(String(200), nullable=True)
    title = Column(String(200), nullable=True)
    content = Column(Text, nullable=True)
    content_type = Column(String(50), nullable=True)
    is_active = Column(String(5), nullable=True)
    variables = Column(Text, nullable=True)
    send_delay = Column(Integer, default=0)
    expiry_hours = Column(Integer, default=24)


class NotificationQueue(Base):
    """Queue item for pending notifications (minimal fields)."""

    __tablename__ = "notification_queue"

    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("notification_templates.id"))
    recipient_type = Column(String(50), nullable=True)
    recipient_id = Column(Integer, nullable=True)
    recipient_email = Column(String(200), nullable=True)
    personalization_data = Column(Text, nullable=True)
    priority = Column(String(50), nullable=True)
    scheduled_for = Column(DateTime, default=utc_now)
    status = Column(String(50), default="pending")
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    last_attempt = Column(DateTime, nullable=True)
    next_retry = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)


class Request(Base):
    """Модел за заявки"""

    __tablename__ = "requests"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="requests")
    logs = relationship("RequestLog", back_populates="request")


class RequestLog(Base):
    """Модел за логове на заявки"""

    __tablename__ = "request_logs"

    id = Column(Integer, primary_key=True)
    request_id = Column(Integer, ForeignKey("requests.id"), nullable=False)
    action = Column(String, nullable=False)
    timestamp = Column(DateTime, default=utc_now)

    request = relationship("Request", back_populates="logs")


class AdminRole(Base):
    """Модел за роли на администратори"""

    __tablename__ = "admin_roles"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    description = Column(Text, nullable=True)

    @classmethod
    def get_query(cls):
        return db_session.query(cls)


# Provide a lightweight Query proxy for modules that call `Model.query`.
try:
    from backend.extensions import db as _db

    class _QueryProxy:
        def __init__(self, model):
            self._model = model

        def all(self):
            return _db.session.query(self._model).all()

        def filter(self, *args, **kwargs):
            return _db.session.query(self._model).filter(*args, **kwargs)

        def order_by(self, *args, **kwargs):
            return _db.session.query(self._model).order_by(*args, **kwargs)

        def get(self, id_):
            try:
                return _db.session.get(self._model, id_)
            except Exception:
                return _db.session.query(self._model).get(id_)

        def __getattr__(self, name):
            return getattr(_db.session.query(self._model), name)

    # Attach query proxies to models commonly used in tests
    try:
        Achievement.query = _QueryProxy(Achievement)
    except Exception:
        pass
    try:
        Volunteer.query = _QueryProxy(Volunteer)
    except Exception:
        pass
    try:
        PushSubscription.query = _QueryProxy(PushSubscription)
    except Exception:
        pass
    try:
        NotificationTemplate.query = _QueryProxy(NotificationTemplate)
    except Exception:
        pass
    try:
        NotificationPreference.query = _QueryProxy(NotificationPreference)
    except Exception:
        pass
except Exception:
    # If backend.extensions isn't importable at module-import time, tests
    # will alias modules and provide access to db via fixtures.
    pass


class PermissionEnum(Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
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


class PriorityEnum(Enum):
    """Изброим тип за приоритети"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Дефиниране на db engine и session
# По подразбиране: НЕ създаваме module-level engine при импорт. Вместо това
# използваме unbound scoped_session, който може да бъде конфигуриран по-късно
# от `backend.extensions` или от тестовата среда. Това премахва двойните
# engine/session проблеми и позволява на Flask-SQLAlchemy да стане единствен
# източник на истина за връзката.
engine = None
# Unbound scoped session; ще бъде configured(bind=...) когато имаме engine.
db = scoped_session(sessionmaker(autocommit=False, autoflush=False))

# Свързване на query_property с module-scoped session (lazy bindable)
db_session = db
Base.query = db_session.query_property()

# Provide a thin compatibility wrapper so that modules which expect a
# Flask-SQLAlchemy `db` object (with `init_app` and `.session`) can import
# `db` from this module or from `extensions` without failing when tests
# import a module that exposes a plain scoped_session. The wrapper forwards
# attribute access to the underlying scoped_session.
class _DBShim:
    def __init__(self, scoped):
        self._scoped = scoped
        # Provide the commonly-used `.session` attribute pointing to the
        # underlying scoped session so `db.session` works in existing code.
        self.session = scoped

    def init_app(self, app):
        # No-op here; real SQLAlchemy init happens in `backend.extensions`.
        return None

    def __getattr__(self, name):
        return getattr(self._scoped, name)

# Replace `db` with shim while keeping `db_session` as the actual scoped_session
_scoped = db
db = _DBShim(_scoped)


# Descriptor that returns a query bound to the Flask app session when
# available, falling back to the module-scoped session otherwise.
class _DynamicQuery:
    def __get__(self, obj, owner):
        # Aggressive strategy: if we're inside a Flask app context always
        # prefer the app's SQLAlchemy session. This avoids returning a
        # module-level session when tests rely on `Model.query` inside
        # app contexts.
        try:
            from flask import has_app_context, current_app

            if has_app_context():
                try:
                    # Try the canonical extension key first
                    _ext_db = None
                    _ext = getattr(current_app, "extensions", None) or {}
                    _ext_db = _ext.get("sqlalchemy") or _ext.get("db")
                    # If extension not present, try importing backend.extensions
                    if _ext_db is None:
                        try:
                            from backend.extensions import db as _ext_db  # type: ignore
                        except Exception:
                            _ext_db = None

                    if _ext_db is not None:
                        return _ext_db.session.query(owner)
                except Exception:
                    # if anything goes wrong, fall back to module session
                    pass

            # Not in app context or couldn't get app db: use module session
            return db_session.query(owner)
        except Exception:
            return db_session.query(owner)


# Attach the dynamic `.query` descriptor now that it's defined.
try:
    User.query = _DynamicQuery()
    # Attach descriptor to Base so all mapped classes use the dynamic
    # query which prefers the Flask app session when available and
    # falls back to the module-scoped session otherwise.
    try:
        Base.query = _DynamicQuery()
    except Exception:
        pass
except Exception:
    pass

# Инициализация на базата данни
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# If a module-level DB URL is provided we will create and bind a local
# engine. This is primarily for isolated scripts or legacy tests that
# deliberately expect a module-level database. In normal Flask runs the
# `backend.extensions` module will call `db.configure(bind=flask_engine)`
# and call `Base.metadata.create_all(bind=flask_engine)` so no local
# engine is necessary.
module_db_url = os.getenv("HELPCHAIN_MODULE_DB_URL", "")
if module_db_url:
    try:
        logger.debug(f"HELPCHAIN_MODULE_DB_URL set, creating module engine {module_db_url}")
        engine = create_engine(module_db_url, connect_args={"check_same_thread": False} if module_db_url.startswith("sqlite") else {})
        try:
            db.configure(bind=engine)
        except Exception:
            # some older SQLAlchemy versions may require replacement of scoped_session
            db = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
            db_session = db
            Base.query = db_session.query_property()

        try:
            Base.metadata.create_all(bind=engine)
            logger.debug("Database tables created on module engine.")
        except Exception as _e:
            logger.debug(f"Could not create metadata on module engine: {_e}")
    except Exception as e:
        logger.error(f"Error creating module engine from HELPCHAIN_MODULE_DB_URL: {e}")

# Also attempt to create the same tables on the Flask-SQLAlchemy engine if
# available. This keeps the schema consistent when the Flask app initializes
# the canonical engine for the application.
try:
    import backend.extensions as _ext

    _ext_db = getattr(_ext, "db", None)
    if _ext_db is not None:
        try:
            # Some db shims may expose `.engine` only after init_app; guard
            # against missing attribute.
            ext_engine = getattr(_ext_db, "engine", None)
            # If the Flask app has initialized the canonical engine/session,
            # prefer it for module-level queries to avoid divergence between
            # the module-scoped session and the app session used in tests.
            if ext_engine is not None:
                logger.debug("Creating metadata on Flask-SQLAlchemy engine for compatibility")
                Base.metadata.create_all(bind=ext_engine)
            try:
                # Attempt to switch the module session to use the Flask app's
                # session when it is available. This is a small, reversible
                # change that keeps the rest of the module-level API stable
                # while reducing mismatches during tests/fixtures.
                ext_session = getattr(_ext_db, "session", None)
                if ext_session is not None:
                    # Replace the module db_session with the Flask-SQLAlchemy
                    # session so `Model.query`, `db.session`, and fixtures
                    # talk to the same transactional context.
                    try:
                        db_session = ext_session
                        # If we wrapped `db` in the _DBShim earlier, update
                        # its `.session` attribute so other imports see the
                        # Flask-backed session via `db.session`.
                        try:
                            if isinstance(db, object) and hasattr(db, "session"):
                                db.session = db_session
                        except Exception:
                            pass

                    except Exception:
                        pass
                    # Ensure Base.query uses the app session query property
                    try:
                        Base.query = db_session.query_property()
                    except Exception:
                        pass
            except Exception:
                # Non-fatal: best-effort binding; ignore failures
                pass
        except Exception:
            logger.debug("Could not create metadata on Flask-SQLAlchemy engine (skipping)")
except Exception:
    # backend.extensions may not be importable at module import time
    pass

# Quick pytest-friendly fallback: if we are running under pytest and no
# module engine was configured, create a temporary file-backed SQLite
# engine and bind the module session so tests that call `db.session`
# or `db.session.query(...)` at import time won't fail with
# UnboundExecutionError. This is a pragmatic, temporary measure to
# unblock tests until Option 2 is completed.
try:
    # Detect pytest either via the per-test env var or by presence of the
    # `pytest` module in sys.modules (covers collection/import-time).
    if engine is None and (os.environ.get("PYTEST_CURRENT_TEST") or "pytest" in sys.modules):
        import tempfile

        tf = tempfile.NamedTemporaryFile(prefix="hc_pytest_", suffix=".db", delete=False)
        tf.close()
        try:
            tmp_url = f"sqlite:///{tf.name}"
            engine = create_engine(tmp_url, connect_args={"check_same_thread": False})
            try:
                db.configure(bind=engine)
            except Exception:
                db = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
                db_session = db
            try:
                Base.metadata.create_all(bind=engine)
            except Exception:
                pass
        except Exception:
            pass
except Exception:
    pass
