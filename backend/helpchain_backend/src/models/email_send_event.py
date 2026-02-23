from __future__ import annotations

from datetime import UTC, datetime, timezone

from backend.extensions import db


class EmailSendEvent(db.Model):
    __tablename__ = "email_send_events"
    __table_args__ = (
        db.Index(
            "ix_email_send_events_hash_purpose_created",
            "email_hash",
            "purpose",
            "created_at",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )
    email_hash = db.Column(db.String(64), nullable=False, index=True)
    purpose = db.Column(db.String(64), nullable=False, index=True)
    outcome = db.Column(db.String(16), nullable=False)
    reason = db.Column(db.String(64), nullable=True)
    ip = db.Column(db.String(64), nullable=True)
    ua = db.Column(db.String(256), nullable=True)
