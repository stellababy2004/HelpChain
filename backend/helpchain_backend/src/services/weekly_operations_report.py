from __future__ import annotations

from backend.extensions import db
from backend.models import AdminUser, Structure
from backend.helpchain_backend.src.services.notification_jobs import (
    enqueue_email_notification,
)
from backend.helpchain_backend.src.services.reporting.operations_report import (
    build_operational_report,
)


def _admin_recipients_for_structure(structure_id: int | None = None) -> list[str]:
    query = AdminUser.query

    if structure_id is not None and hasattr(AdminUser, "structure_id"):
        query = query.filter(AdminUser.structure_id == int(structure_id))

    if hasattr(AdminUser, "is_active"):
        query = query.filter(AdminUser.is_active.is_(True))

    recipients = []
    for user in query.all():
        email = (getattr(user, "email", None) or "").strip()
        if email and "@" in email:
            recipients.append(email)

    return sorted(set(recipients))


def enqueue_weekly_operations_report(
    *,
    structure_id: int | None = None,
    days: int = 7,
    base_url: str = "",
    send_now: bool = False,
) -> dict:
    report = build_operational_report(
        structure_id=structure_id,
        days=days,
    )

    structure = None
    if structure_id is not None:
        structure = db.session.get(Structure, int(structure_id))

    structure_name = (
        getattr(structure, "name", None)
        or report["scope"].get("structure_name")
        or "Toutes les structures visibles"
    )

    recipients = _admin_recipients_for_structure(structure_id)

    report_url = f"{base_url.rstrip('/')}/admin/reports/operations?days={days}" if base_url else ""
    pdf_url = f"{base_url.rstrip('/')}/admin/reports/operations/export.pdf?days={days}" if base_url else ""

    queued = 0
    jobs = []

    for recipient in recipients:
        job = enqueue_email_notification(
            recipient=recipient,
            subject=f"Rapport opérationnel hebdomadaire — {structure_name}",
            template="emails/weekly_operations_report.html",
            context={
                "structure_name": structure_name,
                "days": days,
                "report": report,
                "report_url": report_url,
                "pdf_url": pdf_url,
            },
            purpose="weekly_operations_report",
            structure_id=structure_id,
            send_now=send_now,
        )
        if job:
            queued += 1
            jobs.append(job)

    return {
        "ok": True,
        "structure_id": structure_id,
        "structure_name": structure_name,
        "recipients": recipients,
        "queued": queued,
    }
