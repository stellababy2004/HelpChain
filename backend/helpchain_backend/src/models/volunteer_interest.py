from datetime import datetime

from backend.extensions import db


class VolunteerInterest(db.Model):
    __tablename__ = "volunteer_interests"

    id = db.Column(db.Integer, primary_key=True)
    volunteer_id = db.Column(db.Integer, db.ForeignKey("volunteers.id"), nullable=False, index=True)
    request_id = db.Column(db.Integer, db.ForeignKey("requests.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("volunteer_id", "request_id", name="uq_volunteer_request_interest"),)
