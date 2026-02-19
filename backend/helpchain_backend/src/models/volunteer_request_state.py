from datetime import datetime

from backend.extensions import db


class VolunteerRequestState(db.Model):
    __tablename__ = "volunteer_request_states"

    id = db.Column(db.Integer, primary_key=True)
    volunteer_id = db.Column(
        db.Integer, db.ForeignKey("volunteers.id"), nullable=False, index=True
    )
    request_id = db.Column(
        db.Integer, db.ForeignKey("requests.id"), nullable=False, index=True
    )
    notified_at = db.Column(db.DateTime, nullable=True, index=True)
    seen_at = db.Column(db.DateTime, nullable=True)
    dismissed_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "volunteer_id",
            "request_id",
            name="uq_volunteer_request_state",
        ),
    )
