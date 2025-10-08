from sqlalchemy import func
import enum
from sqlalchemy.orm import relationship
from datetime import datetime
from .extensions import db

# Използваме db инстанцията от src.extensions (няма да създаваме новa SQLAlchemy())


class RoleEnum(str, enum.Enum):
    user = "user"
    moderator = "moderator"
    admin = "admin"
    superadmin = "superadmin"


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


class Volunteer(db.Model):
    __tablename__ = "volunteers"
    __table_args__ = {"extend_existing": True}
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    skills = db.Column(db.String(500), nullable=True)
    location = db.Column(db.String(100), nullable=True)
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
    actor = relationship("User", lazy="joined")


__all__ = ["db", "User", "Volunteer", "AuditLog"]
