from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from backend.helpchain_backend.src.services.quality_signals import (
    compute_quality_signals,
)


def _request(**overrides):
    values = {
        "id": 1,
        "status": "open",
        "deleted_at": None,
        "is_archived": False,
        "owner_id": 10,
        "created_at": datetime(2026, 10, 25, tzinfo=UTC),
        "updated_at": datetime(2026, 10, 25, tzinfo=UTC),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_normal_request_has_no_quality_signal():
    result = compute_quality_signals(_request(), now=datetime(2026, 10, 25, tzinfo=UTC))
    assert result["level"] == "normal"
    assert result["signals"] == []


def test_unassigned_request_is_attention():
    result = compute_quality_signals(
        _request(owner_id=None), now=datetime(2026, 10, 25, tzinfo=UTC)
    )
    assert result["level"] == "attention"
    assert result["signals"] == ["unassigned"]


def test_stale_unassigned_request_is_high_attention():
    now = datetime(2026, 10, 25, tzinfo=UTC)
    result = compute_quality_signals(
        _request(owner_id=None),
        now=now,
        last_activity_at=now - timedelta(hours=73),
    )
    assert result["level"] == "high_attention"
    assert "no_recent_activity" in result["signals"]
    assert "possible_followup_break" in result["signals"]


def test_overdue_request_is_high_attention():
    result = compute_quality_signals(
        _request(), now=datetime(2026, 10, 25, tzinfo=UTC), overdue=True
    )
    assert result["level"] == "high_attention"
    assert result["signals"] == ["overdue"]


def test_closed_archived_and_deleted_requests_are_excluded():
    now = datetime(2026, 10, 25, tzinfo=UTC)
    for request_obj in (
        _request(status="closed"),
        _request(is_archived=True),
        _request(deleted_at=now),
    ):
        result = compute_quality_signals(request_obj, now=now, overdue=True)
        assert result["level"] == "normal"
        assert result["signals"] == []
