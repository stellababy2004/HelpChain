from __future__ import annotations

from flask import flash, redirect, request, url_for

from backend.audit import log_activity
from backend.extensions import db
from backend.models import NotificationJob, utc_now

from .admin import (
    _current_structure_id,
    _is_global_admin,
    _render_notifications_list,
    _table_exists,
    admin_bp,
    admin_required,
    admin_required_404,
    admin_role_required,
)


@admin_bp.get("/notifications")
@admin_required
@admin_role_required("readonly", "ops", "superadmin")
def admin_notifications_list():
    admin_required_404()
    return _render_notifications_list()


@admin_bp.post("/notifications/<int:job_id>/retry")
@admin_required
@admin_role_required("ops", "superadmin")
def admin_notifications_retry(job_id: int):
    admin_required_404()

    if not _table_exists("notification_jobs"):
        flash("Notification jobs table is not available yet. Run migrations first.", "warning")
        return redirect(url_for("admin.admin_notifications_list"), code=303)

    query = NotificationJob.query
    try:
        if not _is_global_admin():
            sid = _current_structure_id()
            query = query.filter(
                (NotificationJob.structure_id == sid)
                | (NotificationJob.structure_id.is_(None))
            )
    except Exception:
        pass

    job = query.filter(NotificationJob.id == int(job_id)).first()
    if not job:
        flash("Notification job not found.", "warning")
        return redirect(url_for("admin.admin_notifications_list"), code=303)

    if (job.status or "").lower() != "failed":
        flash("Only failed notification jobs can be retried manually.", "warning")
        return redirect(url_for("admin.admin_notifications_list"), code=303)

    try:
        job.status = "pending"
        job.attempts = 0
        job.next_retry_at = utc_now()
        job.sent_at = None
        job.last_error = None
        job.updated_at = utc_now()
        db.session.commit()
        log_activity(
            entity_type="notification_job",
            entity_id=int(job.id),
            action="notification.retry",
            metadata={
                "status": "pending",
                "channel": job.channel,
                "event_type": job.event_type,
            },
        )
        flash(f"Notification job #{job.id} was re-queued.", "success")
    except Exception:
        db.session.rollback()
        flash(f"Failed to re-queue notification job #{job.id}.", "danger")

    return redirect(
        url_for("admin.admin_notifications_list", **request.args.to_dict(flat=True)),
        code=303,
    )
