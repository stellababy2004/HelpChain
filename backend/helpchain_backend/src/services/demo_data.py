from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _admin(username: str) -> SimpleNamespace:
    return SimpleNamespace(username=username)


def _request(
    *,
    request_id: int,
    title: str,
    city: str,
    category: str,
    status: str,
    priority: str,
    owner_name: str | None,
    created_delta_hours: int,
    updated_delta_hours: int,
) -> SimpleNamespace:
    now = _now()
    owner = _admin(owner_name) if owner_name else None
    return SimpleNamespace(
        id=request_id,
        title=title,
        city=city,
        category=category,
        status=status,
        priority=priority,
        owner=owner,
        owner_id=(1 if owner_name else None),
        created_at=now - timedelta(hours=created_delta_hours),
        updated_at=now - timedelta(hours=updated_delta_hours),
        risk_score=92 if priority == "high" else 68 if priority == "medium" else 35,
    )


def _case(
    *,
    case_id: int,
    request_row: SimpleNamespace,
    status: str,
    priority: str,
    owner_name: str | None,
    last_activity_hours: int,
    risk_score: int,
) -> SimpleNamespace:
    now = _now()
    owner = _admin(owner_name) if owner_name else None
    return SimpleNamespace(
        id=case_id,
        request_id=request_row.id,
        request=request_row,
        status=status,
        priority=priority,
        owner_user=owner,
        owner_user_id=(case_id if owner_name else None),
        last_activity_at=now - timedelta(hours=last_activity_hours),
        updated_at=now - timedelta(hours=last_activity_hours),
        created_at=request_row.created_at,
        risk_score=risk_score,
        assigned_professional_lead=None,
    )


def _notification(
    *,
    job_id: int,
    status: str,
    event_type: str,
    recipient: str,
    channel: str = "email",
    attempts: int = 0,
    max_attempts: int = 5,
    created_delta_hours: int = 1,
    retry_delta_hours: int | None = None,
    sent_delta_hours: int | None = None,
    last_error: str | None = None,
) -> SimpleNamespace:
    now = _now()
    return SimpleNamespace(
        id=job_id,
        channel=channel,
        event_type=event_type,
        recipient=recipient,
        status=status,
        attempts=attempts,
        max_attempts=max_attempts,
        created_at=now - timedelta(hours=created_delta_hours),
        next_retry_at=(now + timedelta(hours=retry_delta_hours))
        if retry_delta_hours is not None
        else None,
        sent_at=(now - timedelta(hours=sent_delta_hours))
        if sent_delta_hours is not None
        else None,
        last_error=last_error,
    )


def get_demo_kpis() -> dict[str, int]:
    return {
        "critical": 2,
        "unassigned": 3,
        "relance": 1,
        "notifications_failed": 1,
        "updated_today": 4,
    }


def get_demo_requests() -> list[SimpleNamespace]:
    return [
        _request(
            request_id=101,
            title="Femme isolée sans ressources",
            city="Paris",
            category="social",
            status="open",
            priority="high",
            owner_name=None,
            created_delta_hours=6,
            updated_delta_hours=2,
        ),
        _request(
            request_id=102,
            title="Demande logement urgente",
            city="Boulogne",
            category="logement",
            status="in_progress",
            priority="high",
            owner_name="Marie Dupont",
            created_delta_hours=26,
            updated_delta_hours=24,
        ),
        _request(
            request_id=103,
            title="Signalement social critique",
            city="Lyon",
            category="social",
            status="open",
            priority="high",
            owner_name=None,
            created_delta_hours=72,
            updated_delta_hours=72,
        ),
        _request(
            request_id=104,
            title="Orientation vers un hébergement temporaire",
            city="Paris",
            category="logement",
            status="in_progress",
            priority="medium",
            owner_name="Nadia Bernard",
            created_delta_hours=18,
            updated_delta_hours=7,
        ),
    ]


def get_demo_queue_reasons() -> dict[int, list[str]]:
    return {
        101: ["Critique", "Sans responsable"],
        102: ["À vérifier"],
        103: ["Critique", "Sans action récente"],
        104: ["Coordination à suivre"],
    }


def get_demo_ops_priority_levels() -> dict[int, str]:
    return {
        101: "critique",
        102: "élevé",
        103: "critique",
        104: "normal",
    }


def get_demo_cases() -> list[SimpleNamespace]:
    requests = {req.id: req for req in get_demo_requests()}
    return [
        _case(
            case_id=201,
            request_row=requests[101],
            status="new",
            priority="critical",
            owner_name=None,
            last_activity_hours=2,
            risk_score=92,
        ),
        _case(
            case_id=202,
            request_row=requests[102],
            status="in_progress",
            priority="high",
            owner_name="Marie Dupont",
            last_activity_hours=24,
            risk_score=84,
        ),
        _case(
            case_id=203,
            request_row=requests[103],
            status="assigned",
            priority="critical",
            owner_name=None,
            last_activity_hours=73,
            risk_score=95,
        ),
    ]


def get_demo_case_signals() -> dict[int, list[str]]:
    return {
        201: ["URGENT", "NON ASSIGNÉ"],
        202: ["À VÉRIFIER"],
        203: ["CRITIQUE", "NOTIF. ÉCHEC"],
    }


def get_demo_notifications() -> list[SimpleNamespace]:
    return [
        _notification(
            job_id=301,
            status="pending",
            event_type="contact_exchange",
            recipient="orientation@ccas-paris.fr",
            attempts=0,
            created_delta_hours=1,
            retry_delta_hours=1,
        ),
        _notification(
            job_id=302,
            status="failed",
            event_type="email_send",
            recipient="pilotage@territoire.fr",
            attempts=3,
            max_attempts=5,
            created_delta_hours=5,
            retry_delta_hours=2,
            last_error="SMTP timeout lors du dernier envoi",
        ),
        _notification(
            job_id=303,
            status="pending",
            event_type="reminder",
            recipient="coordination@boulogne.fr",
            attempts=1,
            created_delta_hours=3,
            retry_delta_hours=1,
        ),
    ]


def get_demo_notification_summary() -> dict[str, int]:
    return {
        "pending": 2,
        "processing": 0,
        "done": 0,
        "dead_letter": 1,
        "retry": 1,
        "failed": 1,
        "sent": 0,
    }


def get_demo_notification_channels() -> list[str]:
    return ["email"]


def get_demo_sla_payload() -> dict[str, object]:
    now = _now()
    rows = [
        {
            "id": 101,
            "title": "Femme isolée sans ressources",
            "category": "social",
            "status": "open",
            "created_at": now - timedelta(days=3, hours=2),
            "owner_id": None,
            "assigned_volunteer_id": None,
            "overdue_hours": 26.0,
            "breach_type": "owner_assign",
        },
        {
            "id": 102,
            "title": "Demande logement urgente",
            "category": "logement",
            "status": "in_progress",
            "created_at": now - timedelta(days=2, hours=5),
            "owner_id": 1,
            "assigned_volunteer_id": None,
            "overdue_hours": 11.5,
            "breach_type": "resolve",
        },
        {
            "id": 103,
            "title": "Signalement social critique",
            "category": "social",
            "status": "open",
            "created_at": now - timedelta(days=4),
            "owner_id": None,
            "assigned_volunteer_id": None,
            "overdue_hours": 38.0,
            "breach_type": "owner_assign",
        },
    ]
    return {
        "breach_label": "SLA assignation owner",
        "resolve_count": 1,
        "owner_assign_count": 2,
        "volunteer_assign_count": 0,
        "prediction_counts": {
            "resolution_overdue": 1,
            "owner_assignment_overdue": 2,
            "volunteer_assignment_overdue": 0,
        },
        "rows": rows,
    }
