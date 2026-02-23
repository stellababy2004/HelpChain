from datetime import datetime

from backend.extensions import db


class MagicLinkToken(db.Model):
    __tablename__ = "magic_link_tokens"

    id = db.Column(db.Integer, primary_key=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    purpose = db.Column(db.String(32), nullable=False, index=True)  # request|volunteer
    email = db.Column(db.String(255), nullable=False, index=True)
    request_id = db.Column(db.Integer, nullable=True, index=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    used_at = db.Column(db.DateTime, nullable=True, index=True)

    used_ip = db.Column(db.String(64), nullable=True)
    used_ua = db.Column(db.String(255), nullable=True)
