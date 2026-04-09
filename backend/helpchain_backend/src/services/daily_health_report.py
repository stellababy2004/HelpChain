from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, text

from backend.extensions import db
from backend.models import (
    AdminAuditEvent,
    AdminLoginAttempt,
    AdminUser,
    NotificationJob,
    RequestActivity,
    canonical_role,
)

from .notification_jobs import enqueue_email_notification
from .request_sla import (
    SLA_INACTIVITY_ESCALATION_SENT,
    SLA_INACTIVITY_REMINDER_SENT,
    SLA_OWNER_REMINDER_SENT,
    find_inactive_escalation_candidates,
    find_inactive_owned_requests_due,
    find_unowned_requests_due,
)


def _to_utc_naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(UTC).replace(tzinfo=None)


def _now_naive(now: datetime | None = None) -> datetime:
    if now is not None:
        return _to_utc_naive(now) or datetime.now(UTC).replace(tzinfo=None)
    return datetime.now(UTC).replace(tzinfo=None)


def _collect_db_latency_ms() -> int | None:
    started = datetime.now(UTC)
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return None
    ended = datetime.now(UTC)
    return max(0, int(round((ended - started).total_seconds() * 1000.0)))


def collect_queue_health(now: datetime | None = None) -> dict:
    now_naive = _now_naive(now)
    out: dict[str, int | None] = {
        "pending": 0,
        "processing": 0,
        "done": 0,
        "dead_letter": 0,
        "dead_letter_15m": 0,
        "oldest_pending_min": None,
    }

    status_expr = func.lower(NotificationJob.status)
    pending_filter = status_expr.in_(("pending", "retry"))
    processing_filter = status_expr == "processing"
    done_filter = status_expr.in_(("done", "sent"))
    dead_letter_filter = status_expr.in_(("dead_letter", "failed"))
    recent_cutoff = now_naive - timedelta(minutes=15)

    query = NotificationJob.query
    out["pending"] = int(query.filter(pending_filter).count() or 0)
    out["processing"] = int(query.filter(processing_filter).count() or 0)
    out["done"] = int(query.filter(done_filter).count() or 0)
    out["dead_letter"] = int(query.filter(dead_letter_filter).count() or 0)
    out["dead_letter_15m"] = int(
        query.filter(dead_letter_filter, NotificationJob.updated_at >= recent_cutoff).count()
        or 0
    )

    oldest_due = (
        query.with_entities(NotificationJob.next_retry_at, NotificationJob.created_at)
        .filter(
            or_(
                status_expr == "retry",
                and_(status_expr == "pending", NotificationJob.attempts > 0),
                and_(status_expr == "pending", NotificationJob.next_retry_at.is_(None)),
                and_(status_expr == "pending", NotificationJob.next_retry_at <= now_naive),
            )
        )
        .order_by(
            NotificationJob.next_retry_at.asc().nullsfirst(),
            NotificationJob.created_at.asc(),
        )
        .first()
    )
    if oldest_due and (oldest_due[0] or oldest_due[1]):
        oldest_ts = _to_utc_naive(oldest_due[0] or oldest_due[1])
        if oldest_ts is not None:
            out["oldest_pending_min"] = max(
                0, int((now_naive - oldest_ts).total_seconds() // 60)
            )
    return out


def collect_sla_health(now: datetime | None = None) -> dict:
    now_naive = _now_naive(now)
    since_24h = now_naive - timedelta(hours=24)

    out = {
        "unowned_due": 0,
        "inactive_due": 0,
        "escalation_due": 0,
        "owner_reminders_24h": 0,
        "inactivity_reminders_24h": 0,
        "inactivity_escalations_24h": 0,
    }

    out["unowned_due"] = len(find_unowned_requests_due(now=now_naive))
    out["inactive_due"] = len(find_inactive_owned_requests_due(now=now_naive))
    out["escalation_due"] = len(find_inactive_escalation_candidates(now=now_naive))
    out["owner_reminders_24h"] = int(
        RequestActivity.query.filter(
            RequestActivity.action == SLA_OWNER_REMINDER_SENT,
            RequestActivity.created_at >= since_24h,
        ).count()
        or 0
    )
    out["inactivity_reminders_24h"] = int(
        RequestActivity.query.filter(
            RequestActivity.action == SLA_INACTIVITY_REMINDER_SENT,
            RequestActivity.created_at >= since_24h,
        ).count()
        or 0
    )
    out["inactivity_escalations_24h"] = int(
        RequestActivity.query.filter(
            RequestActivity.action == SLA_INACTIVITY_ESCALATION_SENT,
            RequestActivity.created_at >= since_24h,
        ).count()
        or 0
    )
    return out


def collect_admin_security_health(now: datetime | None = None) -> dict:
    now_dt = now or datetime.now(UTC)
    since_24h = now_dt - timedelta(hours=24)
    since_1h = now_dt - timedelta(hours=1)
    risky_actions = (
        "request.archive",
        "request.assign_owner",
        "request.unassign_owner",
        "request.unlock",
        "interest.approve",
        "interest.reject",
    )
    admin_login_max_fails = 5

    out = {
        "admin_logins_success_24h": 0,
        "admin_logins_failed_24h": 0,
        "admin_logins_failed_1h": 0,
        "distinct_failed_ips_24h": 0,
        "distinct_failed_usernames_24h": 0,
        "lockout_buckets_24h": 0,
        "denied_actions_24h": 0,
        "denied_actions_1h": 0,
        "risky_actions_24h": 0,
    }

    out["admin_logins_success_24h"] = int(
        db.session.query(func.count(AdminLoginAttempt.id))
        .filter(
            AdminLoginAttempt.created_at >= since_24h,
            AdminLoginAttempt.success.is_(True),
        )
        .scalar()
        or 0
    )
    out["admin_logins_failed_24h"] = int(
        db.session.query(func.count(AdminLoginAttempt.id))
        .filter(
            AdminLoginAttempt.created_at >= since_24h,
            AdminLoginAttempt.success.is_(False),
        )
        .scalar()
        or 0
    )
    out["admin_logins_failed_1h"] = int(
        db.session.query(func.count(AdminLoginAttempt.id))
        .filter(
            AdminLoginAttempt.created_at >= since_1h,
            AdminLoginAttempt.success.is_(False),
        )
        .scalar()
        or 0
    )
    out["distinct_failed_ips_24h"] = int(
        db.session.query(func.count(func.distinct(AdminLoginAttempt.ip)))
        .filter(
            AdminLoginAttempt.created_at >= since_24h,
            AdminLoginAttempt.success.is_(False),
            AdminLoginAttempt.ip.isnot(None),
            AdminLoginAttempt.ip != "",
        )
        .scalar()
        or 0
    )
    out["distinct_failed_usernames_24h"] = int(
        db.session.query(func.count(func.distinct(AdminLoginAttempt.username)))
        .filter(
            AdminLoginAttempt.created_at >= since_24h,
            AdminLoginAttempt.success.is_(False),
            AdminLoginAttempt.username.isnot(None),
            AdminLoginAttempt.username != "",
        )
        .scalar()
        or 0
    )

    username_expr = func.coalesce(AdminLoginAttempt.username, "")
    fail_buckets = (
        db.session.query(
            AdminLoginAttempt.ip.label("ip"),
            username_expr.label("username"),
            func.count(AdminLoginAttempt.id).label("fails"),
        )
        .filter(
            AdminLoginAttempt.created_at >= since_24h,
            AdminLoginAttempt.success.is_(False),
        )
        .group_by(AdminLoginAttempt.ip, username_expr)
        .having(func.count(AdminLoginAttempt.id) >= admin_login_max_fails)
        .subquery()
    )
    out["lockout_buckets_24h"] = int(
        db.session.query(func.count()).select_from(fail_buckets).scalar() or 0
    )
    out["denied_actions_24h"] = int(
        db.session.query(func.count(AdminAuditEvent.id))
        .filter(
            AdminAuditEvent.created_at >= since_24h,
            AdminAuditEvent.action == "security.denied_action",
        )
        .scalar()
        or 0
    )
    out["denied_actions_1h"] = int(
        db.session.query(func.count(AdminAuditEvent.id))
        .filter(
            AdminAuditEvent.created_at >= since_1h,
            AdminAuditEvent.action == "security.denied_action",
        )
        .scalar()
        or 0
    )
    out["risky_actions_24h"] = int(
        db.session.query(func.count(AdminAuditEvent.id))
        .filter(
            AdminAuditEvent.created_at >= since_24h,
            AdminAuditEvent.action.in_(risky_actions),
        )
        .scalar()
        or 0
    )
    return out


def collect_daily_health_report(now: datetime | None = None) -> dict:
    now_naive = _now_naive(now)
    return {
        "generated_at": now_naive.isoformat(timespec="seconds"),
        "queue": collect_queue_health(now=now_naive),
        "sla": collect_sla_health(now=now_naive),
        "security": collect_admin_security_health(now=now_naive),
        "system": {
            "db_latency_ms": _collect_db_latency_ms(),
        },
    }


def render_daily_health_report_text(report: dict, now: datetime | None = None) -> str:
    now_naive = _now_naive(now)
    queue = report.get("queue") or {}
    sla = report.get("sla") or {}
    security = report.get("security") or {}
    system = report.get("system") or {}

    lines = [
        "HelpChain Daily Health Report",
        f"Date: {now_naive.date().isoformat()}",
        "",
        "Queue",
        f"- pending: {int(queue.get('pending') or 0)}",
        f"- processing: {int(queue.get('processing') or 0)}",
        f"- done: {int(queue.get('done') or 0)}",
        f"- dead_letter: {int(queue.get('dead_letter') or 0)}",
        f"- dead_letter_15m: {int(queue.get('dead_letter_15m') or 0)}",
        f"- oldest_pending_min: {queue.get('oldest_pending_min') if queue.get('oldest_pending_min') is not None else 'n/a'}",
        "",
        "SLA",
        f"- unowned_due: {int(sla.get('unowned_due') or 0)}",
        f"- inactive_due: {int(sla.get('inactive_due') or 0)}",
        f"- escalation_due: {int(sla.get('escalation_due') or 0)}",
        f"- owner_reminders_24h: {int(sla.get('owner_reminders_24h') or 0)}",
        f"- inactivity_reminders_24h: {int(sla.get('inactivity_reminders_24h') or 0)}",
        f"- inactivity_escalations_24h: {int(sla.get('inactivity_escalations_24h') or 0)}",
        "",
        "Security",
        f"- admin_logins_success_24h: {int(security.get('admin_logins_success_24h') or 0)}",
        f"- admin_logins_failed_24h: {int(security.get('admin_logins_failed_24h') or 0)}",
        f"- admin_logins_failed_1h: {int(security.get('admin_logins_failed_1h') or 0)}",
        f"- distinct_failed_ips_24h: {int(security.get('distinct_failed_ips_24h') or 0)}",
        f"- distinct_failed_usernames_24h: {int(security.get('distinct_failed_usernames_24h') or 0)}",
        f"- lockout_buckets_24h: {int(security.get('lockout_buckets_24h') or 0)}",
        f"- denied_actions_24h: {int(security.get('denied_actions_24h') or 0)}",
        f"- denied_actions_1h: {int(security.get('denied_actions_1h') or 0)}",
        f"- risky_actions_24h: {int(security.get('risky_actions_24h') or 0)}",
        "",
        "System",
        f"- db_latency_ms: {system.get('db_latency_ms') if system.get('db_latency_ms') is not None else 'n/a'}",
    ]
    return "\n".join(lines)


def get_daily_health_report_recipients() -> list[str]:
    rows = (
        AdminUser.query.filter(AdminUser.is_active.is_(True))
        .filter(AdminUser.email.isnot(None))
        .all()
    )
    out: list[str] = []
    seen: set[str] = set()
    for admin in rows:
        role = canonical_role(getattr(admin, "role", None))
        if role != "superadmin":
            continue
        if getattr(admin, "structure_id", None) is not None:
            continue
        email = (getattr(admin, "email", None) or "").strip()
        if not email or email in seen:
            continue
        seen.add(email)
        out.append(email)
    return out


def enqueue_daily_health_report(now: datetime | None = None) -> dict:
    now_naive = _now_naive(now)
    report = collect_daily_health_report(now=now_naive)
    recipients = get_daily_health_report_recipients()
    subject = f"[HelpChain] Daily Health Report - {now_naive.date().isoformat()}"
    body = render_daily_health_report_text(report, now=now_naive)

    result = {
        "subject": subject,
        "recipient_count": len(recipients),
        "enqueued": 0,
        "errors": 0,
        "recipients": recipients,
        "report": report,
        "body": body,
    }
    if not recipients:
        return result

    for recipient in recipients:
        try:
            enqueue_email_notification(
                recipient=recipient,
                subject=subject,
                # Reuse an existing operational template in this pass because
                # the user asked for no template/UI changes. The plain-text
                # report body is placed in the template's message field.
                template="emails/professional_lead_notify.html",
                context={
                    "lead_id": 0,
                    "profession": "daily_health_report",
                    "email": recipient,
                    "full_name": "HelpChain Daily Health Report",
                    "organization": "platform",
                    "message": body,
                    "admin_url": None,
                    "created_at": report.get("generated_at") or "",
                },
                purpose="daily_health_report",
                structure_id=None,
            )
            result["enqueued"] += 1
        except Exception:
            result["errors"] += 1
    return result
