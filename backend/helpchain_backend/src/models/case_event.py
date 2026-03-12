from __future__ import annotations

from datetime import UTC, datetime

from backend.extensions import db


class CaseEvent(db.Model):
    __tablename__ = "case_events"

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, index=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"), nullable=True, index=True)
    event_type = db.Column(db.String(60), nullable=False, index=True)
    message = db.Column(db.Text, nullable=True)
    metadata_json = db.Column(db.Text, nullable=True)
    visibility = db.Column(db.String(20), nullable=False, default="internal", index=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )

    case = db.relationship("Case", lazy="joined")
    actor_user = db.relationship("AdminUser", foreign_keys=[actor_user_id], lazy="joined")

    def __repr__(self) -> str:
        return f"<CaseEvent id={self.id} case_id={self.case_id} type={self.event_type}>"

