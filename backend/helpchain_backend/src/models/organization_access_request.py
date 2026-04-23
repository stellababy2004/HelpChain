from __future__ import annotations

from datetime import UTC, datetime

from backend.extensions import db


class OrganizationAccessRequest(db.Model):
    __tablename__ = "organization_access_requests"

    id = db.Column(db.Integer, primary_key=True)

    organization_name = db.Column(db.String(255), nullable=False)
    contact_name = db.Column(db.String(160), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(50), nullable=True)
    city = db.Column(db.String(120), nullable=True, index=True)
    org_type = db.Column(db.String(80), nullable=True, index=True)
    estimated_users = db.Column(db.Integer, nullable=True)
    message = db.Column(db.Text, nullable=True)

    status = db.Column(
        db.String(30),
        nullable=False,
        default="new",
        server_default="new",
        index=True,
    )
    reviewed_by_admin_id = db.Column(
        db.Integer, db.ForeignKey("admin_users.id"), nullable=True, index=True
    )
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    internal_notes = db.Column(db.Text, nullable=True)
    next_action_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    next_action_note = db.Column(db.String(255), nullable=True)

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

    __table_args__ = (
        db.Index("ix_org_access_requests_status_created_at", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<OrganizationAccessRequest id={self.id} "
            f"organization_name={self.organization_name!r} status={self.status!r}>"
        )
