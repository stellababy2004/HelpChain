from datetime import UTC, datetime

from backend.extensions import db


class MagicLinkToken(db.Model):
    __tablename__ = "magic_link_tokens"

    id = db.Column(db.Integer, primary_key=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    purpose = db.Column(db.String(32), nullable=False, index=True)  # request|volunteer
    email = db.Column(db.String(255), nullable=False, index=True)
    request_id = db.Column(db.Integer, nullable=True, index=True)

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    invalidated_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    invalidated_reason = db.Column(db.String(64), nullable=True)

    used_ip = db.Column(db.String(64), nullable=True)
    used_ua = db.Column(db.String(255), nullable=True)
