from __future__ import annotations

from datetime import UTC, datetime, timezone

from backend.extensions import db


class ProfessionalLead(db.Model):
    __tablename__ = "professional_leads"

    id = db.Column(db.Integer, primary_key=True)

    # Core
    email = db.Column(db.String(255), nullable=False, index=True)
    full_name = db.Column(db.String(160), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    city = db.Column(db.String(120), nullable=True, index=True)
    profession = db.Column(db.String(120), nullable=False, index=True)

    # Optional qualifiers
    organization = db.Column(db.String(160), nullable=True)
    availability = db.Column(db.String(80), nullable=True)
    message = db.Column(db.Text, nullable=True)

    # Meta
    source = db.Column(db.String(80), nullable=True, default="professionnels/pilote")
    locale = db.Column(db.String(10), nullable=True)  # fr/bg/en
    ip = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="new", index=True)
    notes = db.Column(db.Text, nullable=True)
    contacted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return (
            f"<ProfessionalLead id={self.id} email={self.email} "
            f"profession={self.profession}>"
        )
