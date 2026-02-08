from datetime import datetime

from backend.extensions import db


class RefreshToken(db.Model):
    __tablename__ = "refresh_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("admin_users.id"), nullable=False, index=True)

    jti = db.Column(db.String(64), nullable=False, unique=True, index=True)
    issued_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    revoked_at = db.Column(db.DateTime, nullable=True)
    replaced_by_jti = db.Column(db.String(64), nullable=True)

    def is_active(self):
        return self.revoked_at is None and self.expires_at > datetime.utcnow()

