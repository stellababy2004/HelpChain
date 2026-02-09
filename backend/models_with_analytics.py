from datetime import UTC, datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

from backend.models import AdminUser

db = SQLAlchemy()

from enum import Enum

# Import AdminUser and other models. Prefer the canonical package import
# (`backend.models`) and fall back to other possible module paths. This
# ensures the names AdminUser/Volunteer are present in this module's
# globals so string-based relationships (e.g. "AdminUser") resolve when
# mappers are configured.
AdminUser = None
User = None
Volunteer = None
try:
    from models import AdminUser, User, Volunteer
except Exception:
    AdminUser = User = Volunteer = None


# Try to import the Flask-SQLAlchemy `db` instance from common module names
# used across different test layouts. If unavailable, provide a lightweight
# fallback that exposes the same attributes (`Model`, `Column`, types, etc.)
# so model classes can be defined at import-time without failing.
db = None
try:
    # Prefer the canonical `backend.extensions` db instance first so all
    # modules reference the same SQLAlchemy() object during tests.
    from backend.extensions import db as _db

    db = _db
except Exception:
    try:
        # Fall back to legacy top-level `extensions` module if present
        from extensions import db as _db

        db = _db
    except Exception:
        db = None

if db is None:
    # Fallback: build a minimal db-like namespace using SQLAlchemy primitives
    try:
        from sqlalchemy import (
            Boolean,
            Column,
            DateTime,
            Float,
            ForeignKey,
            Integer,
            String,
            Text,
        )
        from sqlalchemy.orm import relationship

        class _FakeDB:
            Model = object
            Column = Column
            Integer = Integer
            String = String
            Text = Text
            Boolean = Boolean
            DateTime = DateTime
            Float = Float
            ForeignKey = ForeignKey
            relationship = staticmethod(relationship)

        db = _FakeDB()
    except Exception:
        db = None

# Ensure AdminUser is properly imported for relationships
if AdminUser is None or not hasattr(AdminUser, "__tablename__"):
    try:
        # Force import the real AdminUser class
        import os
        import sys

        # Prefer importing the canonical backend.models module to ensure
        # we reference the single shared AdminUser class object.
        try:
            from models import AdminUser as RealAdminUser

            AdminUser = RealAdminUser
        except Exception:
            # As a fallback, attempt the helpchain shim before legacy top-level
            try:
                from helpchain_backend.src.models import AdminUser as RealAdminUser

                AdminUser = RealAdminUser
            except Exception:
                # Final fallback: try old top-level layout if present
                try:
                    from models import AdminUser as RealAdminUser

                    AdminUser = RealAdminUser
                except Exception:
                    pass
    except ImportError:
        pass


def utc_now() -> datetime:
    """Return naive UTC timestamp without relying on datetime.utcnow."""
    return datetime.now(UTC).replace(tzinfo=None)


class AdminRole(Enum):
    """Роли в административната система"""

    SUPER_ADMIN = "super_admin"  # Пълен достъп до всичко
    ADMIN = "admin"  # Стандартен админ достъп
    MODERATOR = "moderator"  # Ограничен достъп само за модерация


# Import the canonical db and AdminUser from models.py
from datetime import datetime

from flask_login import UserMixin

from backend.extensions import db

# Import the single-source AdminUser model
from backend.models import AdminUser

# Ensure relationships reference the imported AdminUser


class TwoFactorAuth(db.Model):
    """Модел за 2FA токени и сесии"""

    __tablename__ = "two_factor_auth"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(db.Integer, nullable=False)
    session_token = db.Column(db.String(128), unique=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationship to AdminUser intentionally omitted to avoid cross-registry
    # mapper configuration issues during test import/collection.
    admin_user = None


def is_expired(self):
    return utc_now() > self.expires_at


class AdminSession(db.Model):
    """Модел за следене на активни админ сесии"""

    __tablename__ = "admin_sessions"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(db.Integer, nullable=False)
    session_id = db.Column(db.String(128), unique=True, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    last_activity = db.Column(db.DateTime, default=utc_now)
    is_active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationship to AdminUser intentionally omitted to avoid cross-registry
    # mapper configuration issues during test import/collection.
    admin_user = None

    def update_activity(self):
        self.last_activity = utc_now()
        db.session.commit()


class AdminLog(db.Model):
    """Audit log for admin actions."""

    __tablename__ = "admin_logs"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(
        db.Integer, db.ForeignKey("admin_users.id"), nullable=False
    )
    action = db.Column(db.String(120), nullable=False)
    details = db.Column(db.Text, nullable=True)
    entity_type = db.Column(db.String(80), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    admin_user = db.relationship("AdminUser", back_populates="logs")


class Feedback(db.Model):
    __tablename__ = "feedback"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=utc_now)

    # Sentiment analysis fields
    sentiment_score = db.Column(
        db.Float, nullable=True
    )  # -1.0 to 1.0 (negative to positive)
    sentiment_label = db.Column(
        db.String(20), nullable=True
    )  # positive, negative, neutral
    sentiment_confidence = db.Column(db.Float, nullable=True)  # 0.0 to 1.0
    ai_processed = db.Column(db.Boolean, default=False)
    ai_processing_time = db.Column(db.Float, nullable=True)  # in seconds
    ai_provider = db.Column(db.String(20), nullable=True)  # openai, gemini

    # Additional metadata
    user_type = db.Column(db.String(20), default="guest")  # guest, volunteer, admin
    user_id = db.Column(db.Integer, nullable=True)  # if logged in
    page_url = db.Column(db.String(500), nullable=True)  # page where feedback was given
    user_agent = db.Column(db.String(500), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)

    def __repr__(self):
        return f"<Feedback {self.id} - {self.sentiment_label} ({self.sentiment_score})>"


class SuccessStory(db.Model):
    __tablename__ = "success_stories"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=utc_now)


# class VideoChatSession(db.Model):
#     """Модел за видео чат сесии между потребители"""

#     __tablename__ = "video_chat_sessions"
#     __table_args__ = {"extend_existing": True}

#     id = db.Column(db.Integer, primary_key=True)
#     session_id = db.Column(
#         db.String(128), unique=True, nullable=False
#     )  # WebRTC session ID
#     initiator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
#     participant_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
#     status = db.Column(
#         db.String(50), default="pending"
#     )  # pending, active, completed, cancelled
#     started_at = db.Column(db.DateTime, nullable=True)
#     ended_at = db.Column(db.DateTime, nullable=True)
#     duration = db.Column(db.Integer, nullable=True)  # в секунди
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)
#     updated_at = db.Column(
#         db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
#     )

#     # Relationships
#     initiator = db.relationship(
#         "User", foreign_keys=[initiator_id], backref="initiated_video_chats"
#     )
#     participant = db.relationship(
#         "User", foreign_keys=[participant_id], backref="participated_video_chats"
#     )

#     def __repr__(self):
#         return f"<VideoChatSession {self.session_id}>"


class AnalyticsEvent(db.Model):
    """Модел за проследяване на събития за аналитика"""

    __tablename__ = "analytics_events"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(
        db.String(100), nullable=False
    )  # page_view, button_click, etc.
    event_category = db.Column(
        db.String(100), nullable=True
    )  # navigation, engagement, etc.
    event_action = db.Column(db.String(100), nullable=True)  # specific action
    event_label = db.Column(db.String(255), nullable=True)  # additional info
    event_value = db.Column(db.Integer, nullable=True)  # numeric value

    # User context
    user_session = db.Column(db.String(128), nullable=True)  # session identifier
    user_type = db.Column(db.String(50), default="guest")  # guest, volunteer, admin
    user_ip = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)

    # Page context
    page_url = db.Column(db.String(500), nullable=True)
    page_title = db.Column(db.String(255), nullable=True)
    referrer = db.Column(db.String(500), nullable=True)

    # Technical data
    load_time = db.Column(db.Float, nullable=True)  # page load time in seconds
    screen_resolution = db.Column(db.String(20), nullable=True)  # e.g., "1920x1080"
    device_type = db.Column(db.String(50), nullable=True)  # desktop, mobile, tablet

    # Timestamp
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<AnalyticsEvent {self.event_type}>"


class UserBehavior(db.Model):
    """Модел за проследяване на потребителското поведение"""

    __tablename__ = "user_behaviors"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(128), unique=True, nullable=False)

    # User info
    user_type = db.Column(db.String(50), default="guest")
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    device_info = db.Column(db.String(100), nullable=True)  # browser, OS, device
    location = db.Column(db.String(100), nullable=True)  # city, country

    # Session data
    session_start = db.Column(db.DateTime, default=utc_now)
    last_activity = db.Column(db.DateTime, default=utc_now)
    total_time_spent = db.Column(db.Integer, default=0)  # in seconds
    pages_visited = db.Column(db.Integer, default=1)

    # Entry/Exit points
    entry_page = db.Column(db.String(500), nullable=True)
    exit_page = db.Column(db.String(500), nullable=True)

    # Behavior flags
    bounce_rate = db.Column(db.Boolean, default=False)  # left after one page
    conversion_action = db.Column(
        db.String(100), nullable=True
    )  # registration, request_help, etc.

    # Page sequence (JSON array of visited pages)
    pages_sequence = db.Column(db.Text, nullable=True)  # JSON string

    def __repr__(self):
        return f"<UserBehavior {self.session_id}>"


class PerformanceMetrics(db.Model):
    """Модел за метрики на производителността"""

    __tablename__ = "performance_metrics"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    metric_type = db.Column(
        db.String(100), nullable=False
    )  # response_time, db_query_time, etc.
    metric_name = db.Column(db.String(100), nullable=False)  # specific metric name
    metric_value = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), nullable=True)  # ms, seconds, bytes, etc.

    # Context
    endpoint = db.Column(db.String(255), nullable=True)  # API endpoint or page URL
    user_agent = db.Column(db.String(500), nullable=True)
    request_size = db.Column(db.Integer, nullable=True)  # request size in bytes
    response_size = db.Column(db.Integer, nullable=True)  # response size in bytes

    # Additional metadata
    context_data = db.Column(db.Text, nullable=True)  # JSON string with extra data

    # Timestamp
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<PerformanceMetrics {self.metric_name}: {self.metric_value}>"


class ChatbotConversation(db.Model):
    """Модел за разговори с чатбота"""

    __tablename__ = "chatbot_conversations"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(128), nullable=False)

    # Message data
    user_message = db.Column(db.Text, nullable=False)
    bot_response = db.Column(db.Text, nullable=True)
    response_type = db.Column(db.String(50), nullable=True)  # ai, fallback, static

    # AI metadata
    ai_provider = db.Column(db.String(50), nullable=True)  # openai, gemini
    ai_model = db.Column(db.String(100), nullable=True)
    ai_confidence = db.Column(db.Float, nullable=True)  # confidence score 0-1
    ai_tokens_used = db.Column(db.Integer, nullable=True)
    processing_time = db.Column(db.Float, nullable=True)  # in seconds

    # User feedback
    user_rating = db.Column(db.Integer, nullable=True)  # 1-5 stars
    user_feedback = db.Column(db.Text, nullable=True)

    # Context
    page_url = db.Column(db.String(500), nullable=True)
    user_type = db.Column(db.String(50), default="guest")

    # Timestamp
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    def __repr__(self):
        return f"<ChatbotConversation {self.session_id}>"


class Task(db.Model):
    """Модел за задачи в Smart Matching System"""

    __tablename__ = "tasks"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(
        db.String(100), nullable=True
    )  # здраве, образование, социална помощ, etc.
    priority = db.Column(db.String(20), default="medium")  # low, medium, high, urgent
    status = db.Column(
        db.String(50), default="open"
    )  # open, assigned, in_progress, completed, cancelled

    # Location requirements
    location_required = db.Column(db.Boolean, default=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    location_text = db.Column(db.String(255), nullable=True)

    # Skills requirements
    required_skills = db.Column(db.Text, nullable=True)  # JSON array of required skills
    preferred_skills = db.Column(
        db.Text, nullable=True
    )  # JSON array of preferred skills

    # Time requirements
    estimated_hours = db.Column(db.Integer, nullable=True)
    deadline = db.Column(db.DateTime, nullable=True)
    start_date = db.Column(db.DateTime, nullable=True)

    # Assignment tracking
    # assigned_to = db.Column(db.Integer, db.ForeignKey("volunteers.id"), nullable=True)
    assigned_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    # Metadata
    # Store creator id as plain integer to avoid cross-registry FK resolution
    created_by = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    # volunteer relationship may be defined later to avoid circular imports
    # volunteer = db.relationship(Volunteer, backref="assigned_tasks")
    # Relationship to AdminUser omitted to avoid cross-registry join resolution
    # during test collection. Store creator id in `created_by` instead.
    creator = None

    def __repr__(self):
        return f"<Task {self.title} - {self.status}>"


class TaskAssignment(db.Model):
    """Модел за проследяване на task assignments и matching scores"""

    __tablename__ = "task_assignments"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False)
    # volunteer_id = db.Column(db.Integer, db.ForeignKey("volunteers.id"), nullable=False)

    # Matching scores (0-100)
    skill_match_score = db.Column(db.Float, default=0.0)
    location_match_score = db.Column(db.Float, default=0.0)
    availability_match_score = db.Column(db.Float, default=0.0)
    performance_match_score = db.Column(db.Float, default=0.0)
    overall_match_score = db.Column(db.Float, default=0.0)

    # Assignment details
    assigned_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(
        db.String(50), default="suggested"
    )  # suggested, assigned, rejected, completed
    assigned_by = db.Column(db.String(50), default="auto")  # auto, manual, admin

    # Feedback and ratings
    volunteer_rating = db.Column(db.Integer, nullable=True)  # 1-5 stars
    volunteer_feedback = db.Column(db.Text, nullable=True)
    admin_rating = db.Column(db.Integer, nullable=True)  # 1-5 stars
    admin_feedback = db.Column(db.Text, nullable=True)

    # Metadata
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    task = db.relationship("Task", backref="assignments")
    # volunteer = db.relationship(Volunteer, backref="task_assignments")

    def __repr__(self):
        return f"<TaskAssignment Task:{self.task_id} -> Volunteer:{self.volunteer_id} Score:{self.overall_match_score}>"


class TaskPerformance(db.Model):
    """Модел за проследяване на task performance metrics"""

    __tablename__ = "task_performance"
    __table_args__ = {"extend_existing": True}

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False)
    # volunteer_id = db.Column(db.Integer, db.ForeignKey("volunteers.id"), nullable=False)

    # Performance metrics
    time_taken_hours = db.Column(db.Float, nullable=True)
    quality_rating = db.Column(db.Integer, nullable=True)  # 1-5
    timeliness_rating = db.Column(db.Integer, nullable=True)  # 1-5
    communication_rating = db.Column(db.Integer, nullable=True)  # 1-5

    # Task outcome
    task_completed = db.Column(db.Boolean, default=False)
    completion_notes = db.Column(db.Text, nullable=True)

    # Analytics data
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    task = db.relationship("Task", backref="performance_records")
    # volunteer = db.relationship(Volunteer, backref="performance_records")

    def __repr__(self):
        return f"<TaskPerformance Task:{self.task_id} Volunteer:{self.volunteer_id} Completed:{self.task_completed}>"
