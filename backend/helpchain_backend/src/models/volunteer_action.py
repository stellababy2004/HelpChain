from datetime import datetime

from backend.extensions import db


class VolunteerAction(db.Model):
    __tablename__ = "volunteer_actions"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("requests.id"), nullable=False, index=True)
    volunteer_id = db.Column(db.Integer, db.ForeignKey("volunteers.id"), nullable=False, index=True)
    action = db.Column(db.String(20), nullable=False, index=True)  # CAN_HELP | CANT_HELP
    note = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (db.UniqueConstraint("request_id", "volunteer_id", name="uq_volunteer_action_request_volunteer"),)
