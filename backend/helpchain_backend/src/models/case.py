from __future__ import annotations

from datetime import UTC, datetime

from backend.extensions import db
from sqlalchemy import Index


class Case(db.Model):
    __tablename__ = "cases"
    __table_args__ = (
        Index("ix_cases_coordinates", "latitude", "longitude"),
    )

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(
        db.Integer, db.ForeignKey("requests.id"), nullable=False, unique=True, index=True
    )
    structure_id = db.Column(db.Integer, db.ForeignKey("structures.id"), nullable=True, index=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"), nullable=True, index=True)
    assigned_professional_lead_id = db.Column(
        db.Integer, db.ForeignKey("professional_leads.id"), nullable=True, index=True
    )

    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    status = db.Column(db.String(30), nullable=False, default="new", index=True)
    priority = db.Column(db.String(20), nullable=False, default="normal", index=True)
    risk_score = db.Column(db.Integer, nullable=True)

    opened_at = db.Column(db.DateTime(timezone=True), nullable=True)
    assigned_at = db.Column(db.DateTime(timezone=True), nullable=True)
    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_activity_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
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

    request = db.relationship("Request", lazy="joined")
    structure = db.relationship("Structure", lazy="joined")
    owner_user = db.relationship("AdminUser", foreign_keys=[owner_user_id], lazy="joined")
    assigned_professional_lead = db.relationship(
        "ProfessionalLead", foreign_keys=[assigned_professional_lead_id], lazy="joined"
    )
    participants = db.relationship(
        "CaseParticipant",
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="select",
    )

    @property
    def is_critical(self) -> bool:
        return int(self.risk_score or 0) >= 80

    @property
    def requires_attention(self) -> bool:
        score = int(self.risk_score or 0)
        if score >= 90:
            return True
        created_at = getattr(self, "created_at", None)
        if not created_at:
            return False
        now = datetime.now(UTC)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        age_hours = (now - created_at).total_seconds() / 3600.0
        status = (self.status or "").strip().lower()
        return age_hours >= 72 and status not in {"closed", "cancelled"}

    def __repr__(self) -> str:
        return f"<Case id={self.id} request_id={self.request_id} status={self.status}>"
