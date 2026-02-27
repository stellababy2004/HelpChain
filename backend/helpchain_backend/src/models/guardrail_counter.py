from datetime import datetime, timezone

from backend.extensions import db


class GuardrailCounter(db.Model):
    __tablename__ = "guardrail_counters"

    key = db.Column(db.Text, primary_key=True)
    value = db.Column(db.BigInteger, nullable=False, default=0)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
