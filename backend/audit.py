
from sqlalchemy.orm import Session
from .models import AuditLog  # използваме централния модел от backend/models.py


def log_admin_action(
    db: Session,
    actor_user_id: int,
    action: str,
    target_type: str = None,
    target_id: str = None,
    outcome: str = None,
    metadata: dict = None,
):
    """Добавя запис в audit log (използва се от останалия код)."""
    if AuditLog is None:
        return None
    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        outcome=outcome,
        metadata_json=metadata or {},
    )
    db.add(entry)
    db.commit()
    return entry


def log_audit(
    session: Session,
    *,
    actor_user_id: int,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    outcome: str | None = None,
    metadata: dict | None = None,
):
    """Алтернативен helper, който приема Session като аргумент."""
    if AuditLog is None:
        return None
    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        outcome=outcome,
        metadata_json=metadata,
    )
    session.add(entry)
    session.commit()
    return entry
