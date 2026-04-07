from __future__ import annotations

from datetime import UTC, datetime

from backend.extensions import db


class ProfessionalLeadActivity(db.Model):
    __tablename__ = "professional_lead_activities"

    id = db.Column(db.Integer, primary_key=True)
    professional_lead_id = db.Column(
        db.Integer, db.ForeignKey("professional_leads.id"), nullable=False, index=True
    )
    admin_user_id = db.Column(
        db.Integer, db.ForeignKey("admin_users.id"), nullable=True, index=True
    )
    action = db.Column(db.String(64), nullable=False, index=True)
    payload_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<ProfessionalLeadActivity id={self.id} "
            f"lead_id={self.professional_lead_id} action={self.action}>"
        )
