from __future__ import annotations

from datetime import UTC, datetime

from backend.extensions import db


class CaseParticipant(db.Model):
    __tablename__ = "case_participants"

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, index=True)
    participant_type = db.Column(db.String(40), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    professional_lead_id = db.Column(
        db.Integer, db.ForeignKey("professional_leads.id"), nullable=True, index=True
    )
    external_name = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(40), nullable=False, default="contributor", index=True)
    status = db.Column(db.String(30), nullable=False, default="active", index=True)
    added_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )

    case = db.relationship("Case", back_populates="participants", lazy="joined")
    user = db.relationship("User", foreign_keys=[user_id], lazy="joined")
    professional_lead = db.relationship(
        "ProfessionalLead", foreign_keys=[professional_lead_id], lazy="joined"
    )

    def __repr__(self) -> str:
        return (
            f"<CaseParticipant id={self.id} case_id={self.case_id} "
            f"type={self.participant_type} role={self.role}>"
        )

