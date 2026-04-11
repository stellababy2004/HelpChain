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


SCENARIOS = {"pilot_ccas", "crise_sociale", "surcharge_hiver"}


def _login_attempt(*, hours_ago: int, username: str, ip: str, success: bool) -> SimpleNamespace:
    return SimpleNamespace(
        created_at=_now() - timedelta(hours=hours_ago),
        username=username,
        ip=ip,
        success=success,
    )


def _audit_event(
    *,
    hours_ago: int,
    action: str,
    admin_username: str,
    target_type: str,
    target_id: int,
    ip: str,
    payload: dict[str, object] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        created_at=_now() - timedelta(hours=hours_ago),
        action=action,
        admin_username=admin_username,
        admin_user_id=1,
        target_type=target_type,
        target_id=target_id,
        ip=ip,
        payload=payload or {},
    )


def _pagination(total: int) -> SimpleNamespace:
    return SimpleNamespace(page=1, pages=1, total=total, has_prev=False, has_next=False)


def _base_actions() -> list[str]:
    return [
        "ROLE_CHANGE",
        "STRUCTURE_CREATED",
        "STRUCTURE_ADMIN_ASSIGNED",
        "STATUS_CHANGE",
        "ASSIGN_OPERATOR",
        "CREATE_REQUEST",
    ]


def get_demo_scenario_name(scenario: str | None) -> str:
    normalized = (scenario or "").strip().lower()
    if normalized in SCENARIOS:
        return normalized
    return "pilot_ccas"


def _build_pilot_ccas_payload() -> dict[str, object]:
    requests = [
        _request(request_id=101, title="Femme isolee sans ressources", city="Paris", category="social", status="open", priority="high", owner_name=None, created_delta_hours=6, updated_delta_hours=2),
        _request(request_id=102, title="Demande logement urgente", city="Boulogne", category="logement", status="in_progress", priority="high", owner_name="Marie Dupont", created_delta_hours=26, updated_delta_hours=24),
        _request(request_id=103, title="Signalement social critique", city="Lyon", category="social", status="open", priority="high", owner_name=None, created_delta_hours=72, updated_delta_hours=72),
        _request(request_id=104, title="Orientation vers un hebergement temporaire", city="Paris", category="logement", status="in_progress", priority="medium", owner_name="Nadia Bernard", created_delta_hours=18, updated_delta_hours=7),
    ]
    request_map = {req.id: req for req in requests}
    cases = [
        _case(case_id=201, request_row=request_map[101], status="new", priority="critical", owner_name=None, last_activity_hours=2, risk_score=92),
        _case(case_id=202, request_row=request_map[102], status="in_progress", priority="high", owner_name="Marie Dupont", last_activity_hours=24, risk_score=84),
        _case(case_id=203, request_row=request_map[103], status="assigned", priority="critical", owner_name=None, last_activity_hours=73, risk_score=95),
    ]
    notifications = [
        _notification(job_id=301, status="pending", event_type="contact_exchange", recipient="orientation@ccas-paris.fr", attempts=0, created_delta_hours=1, retry_delta_hours=1),
        _notification(job_id=302, status="failed", event_type="email_send", recipient="pilotage@territoire.fr", attempts=3, max_attempts=5, created_delta_hours=5, retry_delta_hours=2, last_error="SMTP timeout sur la derniere tentative"),
        _notification(job_id=303, status="pending", event_type="reminder", recipient="coordination@boulogne.fr", attempts=1, created_delta_hours=3, retry_delta_hours=1),
    ]
    audit_rows = [
        _audit_event(
            hours_ago=2,
            action="admin_login_failure",
            admin_username="ops.paris",
            target_type="AdminUser",
            target_id=8,
            ip="203.0.113.18",
            payload={"route": "login", "reason": "invalid_credentials"},
        ),
        _audit_event(
            hours_ago=4,
            action="ASSIGN_OPERATOR",
            admin_username="admin.ccas",
            target_type="Request",
            target_id=102,
            ip="198.51.100.9",
            payload={"old": "none", "new": "Marie Dupont"},
        ),
        _audit_event(
            hours_ago=7,
            action="security.denied_action",
            admin_username="ops.lyon",
            target_type="Request",
            target_id=103,
            ip="203.0.113.27",
            payload={"attempted_action": "POST /admin/requests/103/delete"},
        ),
    ]
    return {
        "scenario_meta": {
            "label": "Pilot CCAS",
            "short_description": "Environnement pilote equilibre avec quelques signaux de vigilance.",
        },
        "workspace_kpis": {
            "critical": 2,
            "unassigned": 3,
            "relance": 1,
            "notifications_failed": 1,
            "updated_today": 4,
            "retry_notifications": 1,
        },
        "workspace_rows": requests,
        "workspace_queue_reasons": {
            101: ["Critique", "Sans responsable"],
            102: ["A verifier"],
            103: ["Critique", "Sans action recente"],
            104: ["Coordination a suivre"],
        },
        "workspace_priority_levels": {
            101: "critique",
            102: "eleve",
            103: "critique",
            104: "normal",
        },
        "cases_kpis": {"critical": 2, "attention": 1, "no_owner": 2, "stale": 1},
        "cases_rows": cases,
        "cases_signals": {
            201: ["URGENT", "NON ASSIGNE"],
            202: ["A VERIFIER"],
            203: ["CRITIQUE", "NOTIF. ECHEC"],
        },
        "cases_priority_levels": {201: "critique", 202: "eleve", 203: "critique"},
        "notifications_kpis": {
            "pending": 2,
            "processing": 0,
            "done": 0,
            "dead_letter": 1,
            "retry": 1,
            "failed": 1,
            "sent": 0,
        },
        "notification_rows": notifications,
        "notification_channels": ["email"],
        "security_kpis": {
            "success_24h": 9,
            "failed_24h": 5,
            "distinct_failed_ips_24h": 2,
            "distinct_failed_usernames_24h": 2,
            "lockout_buckets_24h": 1,
            "risky_actions_24h": 2,
            "denied_24h": 3,
        },
        "security_anomalies": {
            "spike_failed_logins": False,
            "repeated_fails_by_ip": False,
            "repeated_fails_by_username": False,
            "failed_1h": 1,
            "avg_hourly": 0.21,
            "spike_threshold": 10.0,
            "top_ip": "203.0.113.18",
            "top_ip_fails": 3,
            "top_username": "ops.paris",
            "top_username_fails": 2,
            "denied_spike": False,
            "repeated_denied": False,
            "denied_1h": 1,
            "avg_denied_hourly": 0.12,
            "top_denied_ip": "203.0.113.18",
            "top_denied_ip_count": 2,
            "top_denied_username": "ops.paris",
            "top_denied_username_count": 2,
        },
        "security_recent_attempts": {
            "recent_logins": [
                _login_attempt(hours_ago=1, username="ops.paris", ip="203.0.113.18", success=False),
                _login_attempt(hours_ago=2, username="admin.ccas", ip="198.51.100.9", success=True),
                _login_attempt(hours_ago=4, username="ops.lyon", ip="203.0.113.27", success=False),
            ],
            "recent_risky": [
                _audit_event(hours_ago=3, action="ROLE_CHANGE", admin_username="admin.ccas", target_type="AdminUser", target_id=14, ip="198.51.100.9", payload={"old": "readonly", "new": "ops"})
            ],
            "recent_denied": [
                _audit_event(hours_ago=1, action="security.denied_action", admin_username="ops.paris", target_type="Request", target_id=101, ip="203.0.113.18", payload={"attempted_action": "POST /admin/requests/101/assign"})
            ],
            "recent_sensitive": [
                _audit_event(hours_ago=5, action="STRUCTURE_ADMIN_ASSIGNED", admin_username="superadmin", target_type="Structure", target_id=7, ip="198.51.100.4")
            ],
            "top_ips": [("203.0.113.18", 3), ("203.0.113.27", 2)],
            "top_usernames": [("ops.paris", 2), ("ops.lyon", 2)],
            "top_denied_ips": [("203.0.113.18", 2), ("203.0.113.27", 1)],
            "top_denied_usernames": [("ops.paris", 2), ("ops.lyon", 1)],
            "risky_actions": _base_actions(),
        },
        "audit_rows": audit_rows,
        "audit_filters": {"action": "", "admin": "", "target_type": "", "target_id": "", "days": "7"},
        "audit_actions": ["admin_login_failure", "ASSIGN_OPERATOR", "security.denied_action"],
        "audit_target_types": ["AdminUser", "Request"],
        "sla_kpis": {
            "breach_label": "SLA assignation owner",
            "resolve_count": 1,
            "owner_assign_count": 2,
            "volunteer_assign_count": 0,
            "prediction_counts": {
                "resolution_overdue": 1,
                "owner_assignment_overdue": 2,
                "volunteer_assignment_overdue": 0,
            },
        },
        "sla_rows": [
            {"id": 101, "title": "Femme isolee sans ressources", "category": "social", "status": "open", "created_at": _now() - timedelta(days=3, hours=2), "owner_id": None, "assigned_volunteer_id": None, "overdue_hours": 26.0, "breach_type": "owner_assign"},
            {"id": 102, "title": "Demande logement urgente", "category": "logement", "status": "in_progress", "created_at": _now() - timedelta(days=2, hours=5), "owner_id": 1, "assigned_volunteer_id": None, "overdue_hours": 11.5, "breach_type": "resolve"},
        ],
    }


def _build_crise_sociale_payload() -> dict[str, object]:
    now = _now()
    requests = [
        _request(request_id=111, title="Famille sans hebergement immediat", city="Paris", category="logement", status="open", priority="high", owner_name=None, created_delta_hours=4, updated_delta_hours=1),
        _request(request_id=112, title="Sortie d'hospitalisation sans relais", city="Lyon", category="sante", status="open", priority="high", owner_name=None, created_delta_hours=11, updated_delta_hours=9),
        _request(request_id=113, title="Demande alimentaire urgente", city="Paris", category="social", status="in_progress", priority="high", owner_name="Marie Dupont", created_delta_hours=19, updated_delta_hours=17),
        _request(request_id=114, title="Signalement expulsion imminente", city="Boulogne", category="logement", status="open", priority="high", owner_name=None, created_delta_hours=53, updated_delta_hours=53),
        _request(request_id=115, title="Coordination aide sociale de crise", city="Lyon", category="social", status="in_progress", priority="medium", owner_name="Nadia Bernard", created_delta_hours=30, updated_delta_hours=8),
    ]
    request_map = {req.id: req for req in requests}
    return {
        "scenario_meta": {"label": "Crise sociale", "short_description": "Pression elevee sur les files, les notifications et les delais."},
        "workspace_kpis": {"critical": 4, "unassigned": 4, "relance": 3, "notifications_failed": 3, "updated_today": 6, "retry_notifications": 3},
        "workspace_rows": requests,
        "workspace_queue_reasons": {111: ["Critique", "Sans responsable"], 112: ["Critique", "A verifier"], 113: ["Coordination a suivre"], 114: ["Critique", "Sans action recente"], 115: ["Volume eleve"]},
        "workspace_priority_levels": {111: "critique", 112: "critique", 113: "eleve", 114: "critique", 115: "eleve"},
        "cases_kpis": {"critical": 3, "attention": 2, "no_owner": 3, "stale": 2},
        "cases_rows": [
            _case(case_id=201, request_row=request_map[111], status="new", priority="critical", owner_name=None, last_activity_hours=1, risk_score=97),
            _case(case_id=202, request_row=request_map[112], status="new", priority="critical", owner_name=None, last_activity_hours=9, risk_score=91),
            _case(case_id=203, request_row=request_map[114], status="assigned", priority="critical", owner_name=None, last_activity_hours=73, risk_score=98),
        ],
        "cases_signals": {201: ["URGENT", "NON ASSIGNE"], 202: ["CRITIQUE", "A VERIFIER"], 203: ["CRITIQUE", "SANS ACTION 72H"]},
        "cases_priority_levels": {201: "critique", 202: "eleve", 203: "critique"},
        "notifications_kpis": {"pending": 1, "processing": 0, "done": 0, "dead_letter": 2, "retry": 3, "failed": 3, "sent": 1},
        "notification_rows": [
            _notification(job_id=311, status="pending", event_type="contact_exchange", recipient="urgence@paris.fr", attempts=0, created_delta_hours=1, retry_delta_hours=1),
            _notification(job_id=312, status="failed", event_type="email_send", recipient="astreinte@lyon.fr", attempts=4, max_attempts=5, created_delta_hours=6, retry_delta_hours=2, last_error="Timeout SMTP sur la passerelle regionale"),
            _notification(job_id=313, status="failed", event_type="reminder", recipient="orientation@boulogne.fr", attempts=3, max_attempts=5, created_delta_hours=8, retry_delta_hours=1, last_error="Boite distante indisponible"),
            _notification(job_id=314, status="retry", event_type="owner_alert", recipient="pilotage@territoire.fr", attempts=2, max_attempts=5, created_delta_hours=2, retry_delta_hours=1),
        ],
        "notification_channels": ["email"],
        "security_kpis": {"success_24h": 14, "failed_24h": 27, "distinct_failed_ips_24h": 6, "distinct_failed_usernames_24h": 5, "lockout_buckets_24h": 4, "risky_actions_24h": 6, "denied_24h": 11},
        "security_anomalies": {"spike_failed_logins": True, "repeated_fails_by_ip": True, "repeated_fails_by_username": True, "failed_1h": 9, "avg_hourly": 1.12, "spike_threshold": 10.0, "top_ip": "203.0.113.44", "top_ip_fails": 14, "top_username": "ops.crise", "top_username_fails": 9, "denied_spike": True, "repeated_denied": True, "denied_1h": 6, "avg_denied_hourly": 0.46, "top_denied_ip": "203.0.113.44", "top_denied_ip_count": 7, "top_denied_username": "ops.crise", "top_denied_username_count": 6},
        "security_recent_attempts": {
            "recent_logins": [_login_attempt(hours_ago=1, username="ops.crise", ip="203.0.113.44", success=False), _login_attempt(hours_ago=1, username="ops.crise", ip="203.0.113.44", success=False), _login_attempt(hours_ago=2, username="admin.ccas", ip="198.51.100.10", success=True)],
            "recent_risky": [_audit_event(hours_ago=1, action="ROLE_CHANGE", admin_username="superadmin", target_type="AdminUser", target_id=22, ip="198.51.100.4", payload={"old": "ops", "new": "admin"}), _audit_event(hours_ago=3, action="CREATE_REQUEST", admin_username="ops.crise", target_type="Request", target_id=111, ip="203.0.113.44")],
            "recent_denied": [_audit_event(hours_ago=1, action="security.denied_action", admin_username="ops.crise", target_type="Request", target_id=114, ip="203.0.113.44"), _audit_event(hours_ago=2, action="security.denied_action", admin_username="ops.lyon", target_type="Request", target_id=112, ip="203.0.113.52")],
            "recent_sensitive": [_audit_event(hours_ago=5, action="STRUCTURE_CREATED", admin_username="superadmin", target_type="Structure", target_id=12, ip="198.51.100.4")],
            "top_ips": [("203.0.113.44", 14), ("203.0.113.52", 7), ("198.51.100.61", 4)],
            "top_usernames": [("ops.crise", 9), ("ops.lyon", 6), ("admin.demo", 4)],
            "top_denied_ips": [("203.0.113.44", 7), ("203.0.113.52", 3)],
            "top_denied_usernames": [("ops.crise", 6), ("ops.lyon", 3)],
            "risky_actions": _base_actions(),
        },
        "audit_rows": [
            _audit_event(hours_ago=1, action="admin_login_failure", admin_username="ops.crise", target_type="AdminUser", target_id=18, ip="203.0.113.44", payload={"route": "login", "reason": "invalid_credentials"}),
            _audit_event(hours_ago=2, action="security.denied_action", admin_username="ops.lyon", target_type="Request", target_id=112, ip="203.0.113.52", payload={"attempted_action": "POST /admin/requests/112/delete"}),
            _audit_event(hours_ago=4, action="ASSIGN_OPERATOR", admin_username="superadmin", target_type="Request", target_id=113, ip="198.51.100.4", payload={"old": "none", "new": "Marie Dupont"}),
            _audit_event(hours_ago=6, action="CREATE_REQUEST", admin_username="ops.crise", target_type="Request", target_id=111, ip="203.0.113.44"),
        ],
        "audit_filters": {"action": "", "admin": "", "target_type": "", "target_id": "", "days": "7"},
        "audit_actions": ["admin_login_failure", "security.denied_action", "ASSIGN_OPERATOR", "CREATE_REQUEST"],
        "audit_target_types": ["AdminUser", "Request"],
        "sla_kpis": {"breach_label": "SLA crise sociale", "resolve_count": 3, "owner_assign_count": 4, "volunteer_assign_count": 1, "prediction_counts": {"resolution_overdue": 3, "owner_assignment_overdue": 4, "volunteer_assignment_overdue": 1}},
        "sla_rows": [
            {"id": 111, "title": "Famille sans hebergement immediat", "category": "logement", "status": "open", "created_at": now - timedelta(days=4), "owner_id": None, "assigned_volunteer_id": None, "overdue_hours": 39.0, "breach_type": "owner_assign"},
            {"id": 112, "title": "Sortie d'hospitalisation sans relais", "category": "sante", "status": "open", "created_at": now - timedelta(days=3, hours=8), "owner_id": None, "assigned_volunteer_id": None, "overdue_hours": 29.5, "breach_type": "resolve"},
            {"id": 114, "title": "Signalement expulsion imminente", "category": "logement", "status": "open", "created_at": now - timedelta(days=5), "owner_id": None, "assigned_volunteer_id": None, "overdue_hours": 48.0, "breach_type": "owner_assign"},
        ],
    }


def _build_surcharge_hiver_payload() -> dict[str, object]:
    now = _now()
    requests = [
        _request(request_id=121, title="Recherche d'hebergement d'urgence", city="Paris", category="logement", status="open", priority="high", owner_name=None, created_delta_hours=8, updated_delta_hours=3),
        _request(request_id=122, title="Menage en precarite energetique", city="Lyon", category="social", status="in_progress", priority="medium", owner_name="Marie Dupont", created_delta_hours=20, updated_delta_hours=10),
        _request(request_id=123, title="Sortie rue par temps froid", city="Boulogne", category="logement", status="open", priority="high", owner_name=None, created_delta_hours=34, updated_delta_hours=28),
        _request(request_id=124, title="Coordination sante et hebergement", city="Paris", category="sante", status="in_progress", priority="medium", owner_name="Nadia Bernard", created_delta_hours=42, updated_delta_hours=6),
    ]
    request_map = {req.id: req for req in requests}
    return {
        "scenario_meta": {"label": "Surcharge hiver", "short_description": "Hausse saisonniere du volume avec pression logement et hebergement."},
        "workspace_kpis": {"critical": 2, "unassigned": 2, "relance": 2, "notifications_failed": 1, "updated_today": 5, "retry_notifications": 2},
        "workspace_rows": requests,
        "workspace_queue_reasons": {121: ["Critique", "Logement"], 122: ["Coordination a suivre"], 123: ["Sans responsable", "Sans action recente"], 124: ["Sante", "Hiver"]},
        "workspace_priority_levels": {121: "critique", 122: "normal", 123: "eleve", 124: "eleve"},
        "cases_kpis": {"critical": 2, "attention": 2, "no_owner": 2, "stale": 1},
        "cases_rows": [
            _case(case_id=201, request_row=request_map[121], status="new", priority="critical", owner_name=None, last_activity_hours=3, risk_score=90),
            _case(case_id=202, request_row=request_map[122], status="in_progress", priority="high", owner_name="Marie Dupont", last_activity_hours=10, risk_score=76),
            _case(case_id=203, request_row=request_map[123], status="assigned", priority="high", owner_name=None, last_activity_hours=74, risk_score=88),
        ],
        "cases_signals": {201: ["URGENT", "HEBERGEMENT"], 202: ["A VERIFIER"], 203: ["SANS ACTION 72H", "NON ASSIGNE"]},
        "cases_priority_levels": {201: "critique", 202: "eleve", 203: "critique"},
        "notifications_kpis": {"pending": 1, "processing": 0, "done": 0, "dead_letter": 1, "retry": 2, "failed": 1, "sent": 2},
        "notification_rows": [
            _notification(job_id=321, status="pending", event_type="owner_alert", recipient="hebergement@paris.fr", attempts=1, created_delta_hours=2, retry_delta_hours=1),
            _notification(job_id=322, status="retry", event_type="reminder", recipient="astreinte@lyon.fr", attempts=2, max_attempts=5, created_delta_hours=4, retry_delta_hours=1),
            _notification(job_id=323, status="failed", event_type="email_send", recipient="nuit@boulogne.fr", attempts=3, max_attempts=5, created_delta_hours=7, retry_delta_hours=2, last_error="Serveur distant temporairement indisponible"),
        ],
        "notification_channels": ["email"],
        "security_kpis": {"success_24h": 11, "failed_24h": 8, "distinct_failed_ips_24h": 3, "distinct_failed_usernames_24h": 3, "lockout_buckets_24h": 1, "risky_actions_24h": 3, "denied_24h": 4},
        "security_anomalies": {"spike_failed_logins": False, "repeated_fails_by_ip": False, "repeated_fails_by_username": False, "failed_1h": 2, "avg_hourly": 0.33, "spike_threshold": 10.0, "top_ip": "203.0.113.80", "top_ip_fails": 4, "top_username": "ops.hiver", "top_username_fails": 3, "denied_spike": False, "repeated_denied": False, "denied_1h": 1, "avg_denied_hourly": 0.17, "top_denied_ip": "203.0.113.80", "top_denied_ip_count": 2, "top_denied_username": "ops.hiver", "top_denied_username_count": 2},
        "security_recent_attempts": {
            "recent_logins": [_login_attempt(hours_ago=1, username="ops.hiver", ip="203.0.113.80", success=False), _login_attempt(hours_ago=3, username="admin.ccas", ip="198.51.100.11", success=True), _login_attempt(hours_ago=5, username="ops.logement", ip="203.0.113.81", success=True)],
            "recent_risky": [_audit_event(hours_ago=4, action="STATUS_CHANGE", admin_username="ops.logement", target_type="Request", target_id=123, ip="203.0.113.81", payload={"old": "open", "new": "in_progress"})],
            "recent_denied": [_audit_event(hours_ago=2, action="security.denied_action", admin_username="ops.hiver", target_type="Request", target_id=121, ip="203.0.113.80")],
            "recent_sensitive": [_audit_event(hours_ago=6, action="ASSIGN_OPERATOR", admin_username="admin.ccas", target_type="Request", target_id=124, ip="198.51.100.11")],
            "top_ips": [("203.0.113.80", 4), ("203.0.113.81", 2)],
            "top_usernames": [("ops.hiver", 3), ("ops.logement", 2)],
            "top_denied_ips": [("203.0.113.80", 2)],
            "top_denied_usernames": [("ops.hiver", 2)],
            "risky_actions": _base_actions(),
        },
        "audit_rows": [
            _audit_event(hours_ago=2, action="security.denied_action", admin_username="ops.hiver", target_type="Request", target_id=121, ip="203.0.113.80", payload={"attempted_action": "POST /admin/requests/121/assign"}),
            _audit_event(hours_ago=4, action="STATUS_CHANGE", admin_username="ops.logement", target_type="Request", target_id=123, ip="203.0.113.81", payload={"old": "open", "new": "in_progress"}),
            _audit_event(hours_ago=9, action="ASSIGN_OPERATOR", admin_username="admin.ccas", target_type="Request", target_id=124, ip="198.51.100.11", payload={"old": "none", "new": "Nadia Bernard"}),
        ],
        "audit_filters": {"action": "", "admin": "", "target_type": "", "target_id": "", "days": "7"},
        "audit_actions": ["security.denied_action", "STATUS_CHANGE", "ASSIGN_OPERATOR"],
        "audit_target_types": ["Request"],
        "sla_kpis": {"breach_label": "SLA surcharge hiver", "resolve_count": 1, "owner_assign_count": 2, "volunteer_assign_count": 1, "prediction_counts": {"resolution_overdue": 2, "owner_assignment_overdue": 2, "volunteer_assignment_overdue": 1}},
        "sla_rows": [
            {"id": 121, "title": "Recherche d'hebergement d'urgence", "category": "logement", "status": "open", "created_at": now - timedelta(days=3), "owner_id": None, "assigned_volunteer_id": None, "overdue_hours": 18.0, "breach_type": "owner_assign"},
            {"id": 123, "title": "Sortie rue par temps froid", "category": "logement", "status": "open", "created_at": now - timedelta(days=4), "owner_id": None, "assigned_volunteer_id": None, "overdue_hours": 22.0, "breach_type": "resolve"},
        ],
    }


def get_demo_payload(scenario: str | None = None) -> dict[str, object]:
    scenario_name = get_demo_scenario_name(scenario)
    if scenario_name == "crise_sociale":
        payload = _build_crise_sociale_payload()
    elif scenario_name == "surcharge_hiver":
        payload = _build_surcharge_hiver_payload()
    else:
        payload = _build_pilot_ccas_payload()
    payload["scenario_name"] = scenario_name
    payload["audit_pagination"] = _pagination(len(payload["audit_rows"]))
    return payload


def get_demo_kpis(scenario: str | None = None) -> dict[str, int]:
    return get_demo_payload(scenario)["workspace_kpis"]  # type: ignore[return-value]


def get_demo_requests(scenario: str | None = None) -> list[SimpleNamespace]:
    return get_demo_payload(scenario)["workspace_rows"]  # type: ignore[return-value]


def get_demo_queue_reasons(scenario: str | None = None) -> dict[int, list[str]]:
    return get_demo_payload(scenario)["workspace_queue_reasons"]  # type: ignore[return-value]


def get_demo_ops_priority_levels(scenario: str | None = None) -> dict[int, str]:
    return get_demo_payload(scenario)["workspace_priority_levels"]  # type: ignore[return-value]


def get_demo_cases(scenario: str | None = None) -> list[SimpleNamespace]:
    return get_demo_payload(scenario)["cases_rows"]  # type: ignore[return-value]


def get_demo_case_signals(scenario: str | None = None) -> dict[int, list[str]]:
    return get_demo_payload(scenario)["cases_signals"]  # type: ignore[return-value]


def get_demo_notifications(scenario: str | None = None) -> list[SimpleNamespace]:
    return get_demo_payload(scenario)["notification_rows"]  # type: ignore[return-value]


def get_demo_notification_summary(scenario: str | None = None) -> dict[str, int]:
    return get_demo_payload(scenario)["notifications_kpis"]  # type: ignore[return-value]


def get_demo_notification_channels(scenario: str | None = None) -> list[str]:
    return get_demo_payload(scenario)["notification_channels"]  # type: ignore[return-value]


def get_demo_sla_payload(scenario: str | None = None) -> dict[str, object]:
    payload = get_demo_payload(scenario)
    return {**payload["sla_kpis"], "rows": payload["sla_rows"]}  # type: ignore[arg-type]
