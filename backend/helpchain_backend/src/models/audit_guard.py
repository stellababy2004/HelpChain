from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Session

from backend.models import AdminAuditEvent

_ADMIN_AUDIT_GUARD_INSTALLED = False


def install_admin_audit_append_only_guard() -> None:
    """Install a global SQLAlchemy guard to keep admin audit events immutable."""
    global _ADMIN_AUDIT_GUARD_INSTALLED
    if _ADMIN_AUDIT_GUARD_INSTALLED:
        return

    @event.listens_for(Session, "before_flush")
    def _prevent_admin_audit_mutations(session: Session, flush_context, instances):
        for obj in session.dirty:
            if isinstance(obj, AdminAuditEvent):
                raise RuntimeError(
                    "AdminAuditEvent is append-only: UPDATE is not allowed"
                )
        for obj in session.deleted:
            if isinstance(obj, AdminAuditEvent):
                raise RuntimeError(
                    "AdminAuditEvent is append-only: DELETE is not allowed"
                )

    _ADMIN_AUDIT_GUARD_INSTALLED = True

