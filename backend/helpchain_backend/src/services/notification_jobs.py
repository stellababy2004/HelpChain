import json
import logging
from datetime import timedelta

from backend.extensions import db
from backend.models import NotificationJob, current_structure, utc_now

logger = logging.getLogger(__name__)


def _safe_json_dumps(payload: dict | None) -> str | None:
    if payload is None:
        return None
    try:
        return json.dumps(payload, ensure_ascii=False)
    except Exception:
        return json.dumps({"raw": str(payload)})


def _safe_json_loads(payload_text: str | None) -> dict:
    if not payload_text:
        return {}
    try:
        return json.loads(payload_text)
    except Exception:
        return {}


def _next_retry_delay(attempts: int) -> timedelta:
    # Exponential-ish backoff: 5m, 15m, 45m, 2h, 6h, 12h (cap)
    schedule_minutes = [5, 15, 45, 120, 360, 720]
    idx = max(0, min(attempts - 1, len(schedule_minutes) - 1))
    return timedelta(minutes=schedule_minutes[idx])


def enqueue_notification(
    *,
    channel: str,
    event_type: str,
    recipient: str,
    subject: str | None = None,
    payload: dict | None = None,
    structure_id: int | None = None,
    max_attempts: int = 5,
    send_now: bool = False,
):
    if not recipient:
        raise ValueError("recipient is required")

    sid = structure_id
    if sid is None:
        try:
            s = current_structure()
            sid = getattr(s, "id", None)
        except Exception:
            sid = None

    job = NotificationJob(
        channel=(channel or "email"),
        event_type=(event_type or "generic")[:64],
        recipient=recipient,
        subject=subject,
        payload_json=_safe_json_dumps(payload),
        status="pending",
        attempts=0,
        max_attempts=max_attempts,
        next_retry_at=utc_now(),
        structure_id=sid,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.session.add(job)
    db.session.commit()

    delivered = False
    if send_now:
        delivered = deliver_notification_job(job)
    return job, delivered


def enqueue_email_notification(
    *,
    recipient: str,
    subject: str,
    template: str,
    context: dict | None = None,
    purpose: str | None = None,
    structure_id: int | None = None,
    max_attempts: int = 5,
    send_now: bool = False,
):
    payload = {
        "template": template,
        "context": context or {},
        "purpose": purpose or "generic",
    }
    return enqueue_notification(
        channel="email",
        event_type=purpose or "email",
        recipient=recipient,
        subject=subject,
        payload=payload,
        structure_id=structure_id,
        max_attempts=max_attempts,
        send_now=send_now,
    )


def deliver_notification_job(job: NotificationJob) -> bool:
    if not job:
        return False

    job.attempts = int(job.attempts or 0) + 1
    job.updated_at = utc_now()
    try:
        if job.channel != "email":
            job.status = "failed"
            job.last_error = f"channel_not_supported:{job.channel}"
            job.sent_at = None
            job.next_retry_at = None
            db.session.commit()
            logger.warning(
                "[NOTIFY] job=%s unsupported channel=%s",
                job.id,
                job.channel,
            )
            return False

        payload = _safe_json_loads(job.payload_json)
        template = payload.get("template")
        context = payload.get("context") or {}
        purpose = payload.get("purpose") or job.event_type or "generic"

        if not template:
            job.status = "failed"
            job.last_error = "missing_template"
            job.next_retry_at = None
            db.session.commit()
            logger.error("[NOTIFY] job=%s missing template", job.id)
            return False

        from backend.mail_service import send_notification_email

        ok = bool(
            send_notification_email(
                job.recipient,
                job.subject or "",
                template,
                context,
                purpose=purpose,
                structure_id=job.structure_id,
            )
        )
        if ok:
            job.status = "sent"
            job.sent_at = utc_now()
            job.last_error = None
            job.next_retry_at = None
            db.session.commit()
            logger.info("[NOTIFY] job=%s sent", job.id)
            return True

        job.status = "retry" if job.attempts < job.max_attempts else "failed"
        job.last_error = "send_failed"
        job.next_retry_at = (
            utc_now() + _next_retry_delay(job.attempts)
            if job.status == "retry"
            else None
        )
        job.sent_at = None
        db.session.commit()
        logger.error("[NOTIFY] job=%s send failed (attempt=%s)", job.id, job.attempts)
        return False
    except Exception as exc:
        db.session.rollback()
        job.status = "retry" if job.attempts < job.max_attempts else "failed"
        job.last_error = str(exc)[:512]
        job.next_retry_at = (
            utc_now() + _next_retry_delay(job.attempts)
            if job.status == "retry"
            else None
        )
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        logger.exception("[NOTIFY] job=%s delivery error", job.id)
        return False


def process_pending_notifications(limit: int = 50) -> dict:
    now = utc_now()
    jobs = (
        NotificationJob.query.filter(
            NotificationJob.status.in_(("pending", "retry")),
            (NotificationJob.next_retry_at == None)  # noqa: E711
            | (NotificationJob.next_retry_at <= now),
        )
        .order_by(NotificationJob.created_at.asc())
        .limit(int(limit))
        .all()
    )

    stats = {"scanned": 0, "sent": 0, "failed": 0, "retried": 0}
    for job in jobs:
        stats["scanned"] += 1
        try:
            job.status = "processing"
            job.updated_at = utc_now()
            db.session.commit()
        except Exception:
            db.session.rollback()
            stats["failed"] += 1
            continue

        ok = deliver_notification_job(job)
        if ok:
            stats["sent"] += 1
        else:
            if job.status == "retry":
                stats["retried"] += 1
            else:
                stats["failed"] += 1
    return stats
