from __future__ import annotations

from datetime import UTC, datetime

from backend.extensions import db


class CalendarEvent(db.Model):
    __tablename__ = "calendar_events"

    id = db.Column(db.Integer, primary_key=True)

    structure_id = db.Column(
        db.Integer,
        db.ForeignKey("structures.id"),
        nullable=False,
        index=True,
    )

    case_id = db.Column(
        db.Integer,
        db.ForeignKey("cases.id"),
        nullable=True,
        index=True,
    )

    request_id = db.Column(
        db.Integer,
        db.ForeignKey("requests.id"),
        nullable=True,
        index=True,
    )

    assigned_user_id = db.Column(
        db.Integer,
        db.ForeignKey("admin_users.id"),
        nullable=True,
        index=True,
    )

    created_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("admin_users.id"),
        nullable=True,
        index=True,
    )

    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)

    event_type = db.Column(
        db.String(40),
        nullable=False,
        default="meeting",
        index=True,
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="scheduled",
        index=True,
    )

    starts_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    ends_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    all_day = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )

    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    structure = db.relationship("Structure", lazy="joined")
    case = db.relationship("Case", lazy="joined")
    request = db.relationship("Request", lazy="joined")

    assigned_user = db.relationship(
        "AdminUser",
        foreign_keys=[assigned_user_id],
        lazy="joined",
    )

    created_by_user = db.relationship(
        "AdminUser",
        foreign_keys=[created_by_user_id],
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            f"<CalendarEvent id={self.id} structure_id={self.structure_id} "
            f"type={self.event_type} starts_at={self.starts_at}>"
        )
