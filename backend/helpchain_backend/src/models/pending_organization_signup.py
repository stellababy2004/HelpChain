from datetime import UTC, datetime

from backend.extensions import db


class PendingOrganizationSignup(db.Model):
    __tablename__ = "pending_organization_signups"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    contact_name = db.Column(db.String(160), nullable=False)
    organization_name = db.Column(db.String(255), nullable=False)
    organization_type = db.Column(db.String(64), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    verification_token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    consumed_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC))
