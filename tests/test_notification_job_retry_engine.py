from __future__ import annotations

import importlib
from datetime import timedelta

import pytest

from backend.models import db
from backend.models import NotificationJob, utc_now
from backend.helpchain_backend.src.services import notification_jobs as notification_jobs_service


@pytest.fixture
def retry_engine_app(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.delenv("HC_DB_PATH", raising=False)
    monkeypatch.delenv("SQLALCHEMY_DATABASE_URI", raising=False)

    import backend.helpchain_backend.src.config as config_module
    import backend.helpchain_backend.src.app as app_module

    importlib.reload(config_module)
    app_module = importlib.reload(app_module)

    create_app = app_module.create_app
    app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        import backend.models  # noqa: F401
        import backend.models_with_analytics  # noqa: F401

        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def retry_engine_session(retry_engine_app):
    with retry_engine_app.app_context():
        yield db.session


def _make_job(
    session,
    *,
    status: str = "pending",
    attempts: int = 0,
    max_attempts: int = 5,
    next_retry_at=None,
    payload_json: str | None = None,
    channel: str = "email",
    recipient: str = "notify@test.local",
    subject: str = "Test notification",
):
    now = utc_now()
    job = NotificationJob(
        channel=channel,
        event_type="test_event",
        recipient=recipient,
        subject=subject,
        payload_json=payload_json,
        status=status,
        attempts=attempts,
        max_attempts=max_attempts,
        next_retry_at=next_retry_at,
        locked_at=None,
        processed_at=None,
        sent_at=None,
        last_error=None,
        created_at=now,
        updated_at=now,
    )
    session.add(job)
    session.commit()
    return job


def test_enqueue_creates_due_pending_job(monkeypatch, retry_engine_session):
    def _noop_delivery(job):
        return False

    monkeypatch.setattr(notification_jobs_service, "deliver_notification_job", _noop_delivery)

    job, delivered = notification_jobs_service.enqueue_notification(
        channel="email",
        event_type="unit_test_event",
        recipient="pending@test.local",
        subject="Pending job",
        payload={"template": "emails/test.html", "context": {}, "purpose": "unit_test"},
        send_now=False,
    )

    retry_engine_session.refresh(job)
    assert delivered is False
    assert job.status == "pending"
    assert job.attempts == 0
    assert job.next_retry_at is not None
    assert job.locked_at is None
    assert job.processed_at is None


def test_success_marks_job_done(monkeypatch, retry_engine_session):
    monkeypatch.setattr(
        "backend.mail_service.send_notification_email",
        lambda *args, **kwargs: True,
    )
    job = _make_job(
        retry_engine_session,
        payload_json='{"template":"emails/test.html","context":{},"purpose":"unit_test"}',
    )
    job.status = "processing"
    job.locked_at = utc_now()
    retry_engine_session.commit()

    delivered = notification_jobs_service.deliver_notification_job(job)

    retry_engine_session.refresh(job)
    assert delivered is True
    assert job.status == "done"
    assert job.processed_at is not None
    assert job.locked_at is None
    assert job.last_error is None
    assert job.next_retry_at is None


def test_retryable_failure_reschedules_pending(monkeypatch, retry_engine_session):
    monkeypatch.setattr(
        "backend.mail_service.send_notification_email",
        lambda *args, **kwargs: False,
    )
    now = utc_now()
    job = _make_job(
        retry_engine_session,
        attempts=0,
        max_attempts=3,
        next_retry_at=now,
        payload_json='{"template":"emails/test.html","context":{},"purpose":"unit_test"}',
    )
    job.status = "processing"
    job.locked_at = now
    retry_engine_session.commit()

    delivered = notification_jobs_service.deliver_notification_job(job)

    retry_engine_session.refresh(job)
    assert delivered is False
    assert job.status == "pending"
    assert job.attempts == 1
    assert job.next_retry_at is not None
    assert job.next_retry_at.replace(tzinfo=None) > now.replace(tzinfo=None)
    assert job.last_error
    assert job.locked_at is None
    assert job.processed_at is None


def test_exhausted_failure_marks_dead_letter(monkeypatch, retry_engine_session):
    monkeypatch.setattr(
        "backend.mail_service.send_notification_email",
        lambda *args, **kwargs: False,
    )
    job = _make_job(
        retry_engine_session,
        attempts=2,
        max_attempts=3,
        next_retry_at=utc_now(),
        payload_json='{"template":"emails/test.html","context":{},"purpose":"unit_test"}',
    )
    job.status = "processing"
    job.locked_at = utc_now()
    retry_engine_session.commit()

    delivered = notification_jobs_service.deliver_notification_job(job)

    retry_engine_session.refresh(job)
    assert delivered is False
    assert job.status == "dead_letter"
    assert job.processed_at is not None
    assert job.next_retry_at is None
    assert job.locked_at is None


def test_processor_only_handles_due_jobs(monkeypatch, retry_engine_session):
    send_calls: list[str] = []

    def _fake_send(recipient, subject, template, context, **kwargs):
        send_calls.append(recipient)
        return True

    monkeypatch.setattr("backend.mail_service.send_notification_email", _fake_send)

    future_job = _make_job(
        retry_engine_session,
        recipient="future@test.local",
        next_retry_at=utc_now() + timedelta(hours=1),
        payload_json='{"template":"emails/test.html","context":{},"purpose":"unit_test"}',
    )
    due_job = _make_job(
        retry_engine_session,
        recipient="due@test.local",
        next_retry_at=utc_now(),
        payload_json='{"template":"emails/test.html","context":{},"purpose":"unit_test"}',
    )

    stats = notification_jobs_service.process_pending_notifications(limit=10)

    retry_engine_session.refresh(future_job)
    retry_engine_session.refresh(due_job)
    assert stats["scanned"] >= 1
    assert due_job.status == "done"
    assert future_job.status == "pending"
    assert future_job.attempts == 0
    assert "due@test.local" in send_calls
    assert "future@test.local" not in send_calls
