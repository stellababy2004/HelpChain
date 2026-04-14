from __future__ import annotations

from datetime import UTC, datetime

from backend.extensions import db


class CaseParticipant(db.Model):
    __tablename__ = "case_participants"

    id = db.Column(db.Integer, primary_key=True)

    case_id = db.Column(
        db.Integer,
        db.ForeignKey("cases.id"),
        nullable=False,
        index=True,
    )

    # --- Identity layer ---
    participant_type = db.Column(db.String(40), nullable=False, index=True)

    # Legacy / generic user (users.id)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    # NEW: Admin identity (admin_users.id)
    admin_user_id = db.Column(
        db.Integer,
        db.ForeignKey("admin_users.id"),
        nullable=True,
        index=True,
    )

    # Professional
    professional_lead_id = db.Column(
        db.Integer,
        db.ForeignKey("professional_leads.id"),
        nullable=True,
        index=True,
    )

    # External participant (no account)
    external_name = db.Column(db.String(255), nullable=True)

    # Optional explicit actor typing (future-proof)
    actor_type = db.Column(db.String(32), nullable=True, index=True)

    # --- Role / state ---
    role = db.Column(
        db.String(40),
        nullable=False,
        default="contributor",
        index=True,
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="active",
        index=True,
    )

    added_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )

    case = db.relationship("Case", back_populates="participants", lazy="joined")

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        lazy="joined",
    )

    admin_user = db.relationship(
        "AdminUser",
        foreign_keys=[admin_user_id],
        lazy="joined",
    )

    professional_lead = db.relationship(
        "ProfessionalLead",
        foreign_keys=[professional_lead_id],
        lazy="joined",
    )

    # --- Debug / repr ---
    def __repr__(self) -> str:
        actor = (
            f"user:{self.user_id}" if self.user_id
            else f"admin:{self.admin_user_id}" if self.admin_user_id
            else f"lead:{self.professional_lead_id}" if self.professional_lead_id
            else "external"
        )
        return (
            f"<CaseParticipant id={self.id} case_id={self.case_id} "
            f"type={self.participant_type} role={self.role} actor={actor}>"
        )