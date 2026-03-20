from __future__ import annotations

from datetime import UTC, datetime

from backend.extensions import db


class CaseCollaborator(db.Model):
    __tablename__ = "case_collaborators"

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("cases.id"), nullable=False, index=True)
    structure_id = db.Column(
        db.Integer, db.ForeignKey("structures.id"), nullable=False, index=True
    )
    role = db.Column(db.String(32), nullable=False, default="viewer", index=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )

    case = db.relationship("Case", lazy="joined")
    structure = db.relationship("Structure", lazy="joined")

    def __repr__(self) -> str:
        return f"<CaseCollaborator id={self.id} case_id={self.case_id} structure_id={self.structure_id}>"
