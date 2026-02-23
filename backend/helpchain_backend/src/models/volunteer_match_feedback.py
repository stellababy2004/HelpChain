from datetime import datetime

from backend.helpchain_backend.src.models import db


class VolunteerMatchFeedback(db.Model):
    __tablename__ = "volunteer_match_feedback"

    id = db.Column(db.Integer, primary_key=True)
    volunteer_id = db.Column(
        db.Integer, db.ForeignKey("volunteers.id"), nullable=False, index=True
    )
    request_id = db.Column(
        db.Integer, db.ForeignKey("requests.id"), nullable=False, index=True
    )

    # seen / dismissed
    action = db.Column(db.String(20), nullable=False)
    # used only for dismissed
    expires_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("volunteer_id", "request_id", name="uq_vol_req_feedback"),
    )
