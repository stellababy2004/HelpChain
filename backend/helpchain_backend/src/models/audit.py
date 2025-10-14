from datetime import datetime
from ..extensions import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(
        db.String(64), nullable=False
    )  # e.g. "approve","reject","update"
    actor_id = db.Column(db.Integer, nullable=False)  # admin user id
    actor_name = db.Column(
        db.String(128), nullable=True
    )  # admin username (redundant but useful)
    target_type = db.Column(db.String(64), nullable=True)  # e.g. "help_request"
    target_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.JSON, nullable=True)  # extra context (note, payload)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
