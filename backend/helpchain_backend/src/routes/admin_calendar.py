from __future__ import annotations

from calendar import Calendar
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user

from backend.extensions import db

from ..models import CalendarEvent
from .admin import (
    _current_structure_id,
    _is_global_admin,
    admin_bp,
    admin_required,
    admin_required_404,
    admin_role_required,
)


def _scoped_calendar_events_query():
    query = CalendarEvent.query
    if not _is_global_admin():
        query = query.filter(
            CalendarEvent.structure_id == _current_structure_id()
        )
    return query


def _scoped_calendar_event_or_404(event_id: int):
    return _scoped_calendar_events_query().filter(
        CalendarEvent.id == event_id
    ).first_or_404()


PARIS_TZ = ZoneInfo("Europe/Paris")


def _calendar_local_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(PARIS_TZ)


def _parse_calendar_local_datetime(raw_value: str) -> datetime:
    value = datetime.fromisoformat(raw_value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=PARIS_TZ)
    return value.astimezone(UTC)


@admin_bp.get("/calendar")
@admin_required
@admin_role_required("readonly", "ops", "admin", "superadmin")
def admin_calendar():
    admin_required_404()

    now = datetime.now(PARIS_TZ)
    calendar_view = (request.args.get("view") or "month").strip().lower()
    if calendar_view not in {"month", "week", "today"}:
        calendar_view = "month"

    try:
        year = int(request.args.get("year", now.year))
        month = int(request.args.get("month", now.month))
        day = int(request.args.get("day", now.day))
        selected_date = datetime(year, month, day).date()
    except (TypeError, ValueError):
        selected_date = now.date()

    year = selected_date.year
    month = selected_date.month

    previous_month = (
        datetime(year - 1, 12, 1)
        if month == 1
        else datetime(year, month - 1, 1)
    )
    next_month = (
        datetime(year + 1, 1, 1)
        if month == 12
        else datetime(year, month + 1, 1)
    )

    previous_date = selected_date - timedelta(days=1 if calendar_view == "today" else 7)
    next_date = selected_date + timedelta(days=1 if calendar_view == "today" else 7)

    if calendar_view == "week":
        week_start = selected_date - timedelta(days=selected_date.weekday())
        calendar_weeks = [
            [week_start + timedelta(days=offset) for offset in range(7)]
        ]
    elif calendar_view == "today":
        calendar_weeks = [[selected_date]]
    else:
        calendar_weeks = Calendar(firstweekday=0).monthdatescalendar(
            year,
            month,
        )

    events = (
        _scoped_calendar_events_query()
        .order_by(CalendarEvent.starts_at.asc())
        .all()
    )
    for event in events:
        event.starts_at = _calendar_local_datetime(event.starts_at)
        event.ends_at = _calendar_local_datetime(event.ends_at)

    return render_template(
        "admin/calendar.html",
        events=events,
        calendar_weeks=calendar_weeks,
        calendar_year=year,
        calendar_month=month,
        calendar_view=calendar_view,
        selected_date=selected_date,
        previous_date=previous_date,
        next_date=next_date,
        previous_month=previous_month,
        next_month=next_month,
        today=now.date(),
    )

@admin_bp.post("/calendar/events")
@admin_required
@admin_role_required("ops", "admin", "superadmin")
def admin_calendar_create_event():
    admin_required_404()

    # Calendar writes must always have an explicit tenant.
    # Never let a platform-global account fall back to the default structure.
    if _is_global_admin():
        flash(
            "Selectionnez une organisation avant de creer un evenement.",
            "warning",
        )
        return redirect(url_for("admin.admin_calendar"), code=303)

    structure_id = _current_structure_id()

    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    event_type = (request.form.get("event_type") or "meeting").strip().lower()
    starts_at_raw = (request.form.get("starts_at") or "").strip()
    ends_at_raw = (request.form.get("ends_at") or "").strip()

    if not title:
        flash("Le titre de l'evenement est obligatoire.", "warning")
        return redirect(url_for("admin.admin_calendar"), code=303)

    if len(title) > 200:
        flash("Le titre de l'evenement est trop long.", "warning")
        return redirect(url_for("admin.admin_calendar"), code=303)

    allowed_event_types = {
        "meeting",
        "follow_up",
        "partner",
        "deadline",
        "other",
    }
    if event_type not in allowed_event_types:
        event_type = "other"

    try:
        starts_at = _parse_calendar_local_datetime(starts_at_raw)
    except (TypeError, ValueError):
        flash("La date de debut est invalide.", "warning")
        return redirect(url_for("admin.admin_calendar"), code=303)

    ends_at = None
    if ends_at_raw:
        try:
            ends_at = _parse_calendar_local_datetime(ends_at_raw)
        except (TypeError, ValueError):
            flash("La date de fin est invalide.", "warning")
            return redirect(url_for("admin.admin_calendar"), code=303)

    if ends_at is not None and ends_at < starts_at:
        flash(
            "La date de fin doit etre posterieure a la date de debut.",
            "warning",
        )
        return redirect(url_for("admin.admin_calendar"), code=303)

    event = CalendarEvent(
        structure_id=structure_id,
        created_by_user_id=getattr(current_user, "id", None),
        title=title,
        description=description,
        event_type=event_type,
        status="scheduled",
        starts_at=starts_at,
        ends_at=ends_at,
        all_day=False,
    )

    db.session.add(event)
    db.session.commit()

    flash("Evenement ajoute au calendrier.", "success")
    return redirect(url_for("admin.admin_calendar"), code=303)




@admin_bp.post("/calendar/events/<int:event_id>/update")
@admin_required
@admin_role_required("ops", "admin", "superadmin")
def admin_calendar_update_event(event_id):
    admin_required_404()

    if _is_global_admin():
        return ("", 404)

    event = _scoped_calendar_event_or_404(event_id)

    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    event_type = (request.form.get("event_type") or "meeting").strip().lower()
    starts_at_raw = (request.form.get("starts_at") or "").strip()
    ends_at_raw = (request.form.get("ends_at") or "").strip()

    if not title or len(title) > 200:
        flash("Le titre de l'evenement est invalide.", "warning")
        return redirect(url_for("admin.admin_calendar"), code=303)

    allowed_event_types = {
        "meeting", "follow_up", "partner", "deadline", "other"
    }
    if event_type not in allowed_event_types:
        event_type = "other"

    try:
        starts_at = _parse_calendar_local_datetime(starts_at_raw)
    except (TypeError, ValueError):
        flash("La date de debut est invalide.", "warning")
        return redirect(url_for("admin.admin_calendar"), code=303)

    ends_at = None
    if ends_at_raw:
        try:
            ends_at = _parse_calendar_local_datetime(ends_at_raw)
        except (TypeError, ValueError):
            flash("La date de fin est invalide.", "warning")
            return redirect(url_for("admin.admin_calendar"), code=303)

    if ends_at is not None and ends_at < starts_at:
        flash(
            "La date de fin doit etre posterieure a la date de debut.",
            "warning",
        )
        return redirect(url_for("admin.admin_calendar"), code=303)

    event.title = title
    event.description = description
    event.event_type = event_type
    event.starts_at = starts_at
    event.ends_at = ends_at

    db.session.commit()
    flash("Evenement modifie.", "success")
    return redirect(url_for("admin.admin_calendar"), code=303)


@admin_bp.post("/calendar/events/<int:event_id>/delete")
@admin_required
@admin_role_required("ops", "admin", "superadmin")
def admin_calendar_delete_event(event_id):
    admin_required_404()

    if _is_global_admin():
        return ("", 404)

    event = _scoped_calendar_event_or_404(event_id)
    db.session.delete(event)
    db.session.commit()

    flash("Evenement supprime.", "success")
    return redirect(url_for("admin.admin_calendar"), code=303)
