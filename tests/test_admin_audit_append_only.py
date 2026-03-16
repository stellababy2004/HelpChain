import pytest

from backend.models import AdminAuditEvent


def _create_event(session) -> AdminAuditEvent:
    event = AdminAuditEvent(
        admin_user_id=1,
        admin_username="admin",
        action="STATUS_CHANGE",
        target_type="Request",
        target_id=1001,
        ip="127.0.0.1",
        payload={"old": {"status": "open"}, "new": {"status": "in_progress"}},
    )
    session.add(event)
    session.commit()
    return event


def test_admin_audit_append_only_allows_insert(session):
    event = _create_event(session)
    assert event.id is not None


def test_admin_audit_append_only_blocks_update(session):
    event = _create_event(session)
    event.action = "request.archive"
    with pytest.raises(RuntimeError, match="append-only"):
        session.commit()
    session.rollback()


def test_admin_audit_append_only_blocks_delete(session):
    event = _create_event(session)
    session.delete(event)
    with pytest.raises(RuntimeError, match="append-only"):
        session.commit()
    session.rollback()

