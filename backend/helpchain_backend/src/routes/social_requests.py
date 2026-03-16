from __future__ import annotations

from datetime import datetime, timedelta

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_babel import gettext as _
from sqlalchemy import func

from backend.helpchain_backend.src.routes.admin import operator_required
from backend.models import (
    AdminAuditEvent,
    AdminUser,
    SocialRequest,
    SocialRequestEvent,
    Structure,
    User,
    db,
)

bp = Blueprint("social_requests", __name__, url_prefix="/requests")

NEED_TYPES = [
    ("aide_alimentaire", "Food support"),
    ("aide_administrative", "Administrative support"),
    ("visite_senior", "Senior visit"),
    ("urgence_sociale", "Social emergency"),
    ("autre", "Other"),
]
URGENCIES = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
]
ALLOWED_STATUSES = {"new", "in_progress", "resolved", "closed"}


def _safe_int(v: str | None) -> int | None:
    if not v:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _utcnow():
    return datetime.utcnow()


def _structure_scope():
    return _safe_int(request.args.get("structure_id"))


def compute_structure_health(structure_id: int | None) -> int:
    score = 100
    now = datetime.utcnow()

    base = SocialRequest.query
    if structure_id:
        base = base.filter(SocialRequest.structure_id == structure_id)

    unassigned = base.filter(SocialRequest.assigned_to_user_id.is_(None)).count()
    if unassigned > 0:
        score -= 30

    stale_cutoff = now - timedelta(hours=48)
    stale = base.filter(
        (SocialRequest.updated_at < stale_cutoff)
        | (SocialRequest.updated_at.is_(None) & (SocialRequest.created_at < stale_cutoff))
    ).count()
    if stale > 0:
        score -= 20

    overdue_cutoff = now - timedelta(days=3)
    overdue = base.filter(
        SocialRequest.status.in_(["new", "in_progress"]),
        SocialRequest.created_at < overdue_cutoff,
    ).count()
    if overdue > 0:
        score -= 20

    return max(score, 0)


def _current_actor_user_id() -> int | None:
    for key in ("user_id", "volunteer_user_id"):
        candidate = _safe_int(session.get(key))
        if candidate and db.session.get(User, candidate):
            return candidate
    return None


def _current_actor_label() -> str:
    admin_user_id = _safe_int(session.get("admin_user_id"))
    if admin_user_id:
        admin = db.session.get(AdminUser, admin_user_id)
        if admin and getattr(admin, "username", None):
            return f"admin:{admin.username}"
    actor_user_id = _current_actor_user_id()
    if actor_user_id:
        u = db.session.get(User, actor_user_id)
        if u:
            return f"user:{u.email or u.username or u.id}"
    return "system"


def _audit_admin_event(action: str, request_id: int, payload: dict | None = None) -> None:
    try:
        admin_user_id = session.get("admin_user_id")
        admin_username = None
        if admin_user_id:
            admin = db.session.get(AdminUser, int(admin_user_id))
            admin_username = getattr(admin, "username", None) if admin else None
        ua = request.headers.get("User-Agent")
        db.session.add(
            AdminAuditEvent(
                admin_user_id=admin_user_id,
                admin_username=admin_username,
                action=action,
                target_type="Request",
                target_id=int(request_id),
                ip=request.remote_addr,
                user_agent=(ua[:256] if ua else None),
                payload=payload,
            )
        )
    except Exception:
        # Never block business flow on audit write preparation errors.
        pass


@bp.get("")
@operator_required
def list_requests():
    sid = _structure_scope()
    q = SocialRequest.query

    if sid:
        q = q.filter(SocialRequest.structure_id == sid)

    items = q.order_by(SocialRequest.created_at.desc()).limit(200).all()
    structures = Structure.query.order_by(Structure.name.asc()).all()

    return render_template(
        "requests/list.html",
        items=items,
        structures=structures,
        selected_structure_id=sid,
    )


@bp.get("/dashboard")
@operator_required
def dashboard():
    sid = _structure_scope()
    structures = Structure.query.order_by(Structure.name.asc()).all()

    base = db.session.query(SocialRequest)
    if sid:
        base = base.filter(SocialRequest.structure_id == sid)

    total = base.with_entities(func.count(SocialRequest.id)).scalar()

    active = base.with_entities(func.count(SocialRequest.id)).filter(
        SocialRequest.status.in_(["new", "in_progress"])
    ).scalar()

    resolved = base.with_entities(func.count(SocialRequest.id)).filter(
        SocialRequest.status == "resolved"
    ).scalar()

    closed = base.with_entities(func.count(SocialRequest.id)).filter(
        SocialRequest.status == "closed"
    ).scalar()

    urgent = base.with_entities(func.count(SocialRequest.id)).filter(
        SocialRequest.urgency == "high"
    ).scalar()

    return render_template(
        "requests/dashboard.html",
        total=total,
        active=active,
        resolved=resolved,
        closed=closed,
        urgent=urgent,
        structures=structures,
        selected_structure_id=sid,
    )


@bp.get("/operations")
@operator_required
def operations():
    sid = _structure_scope()
    structures = Structure.query.order_by(Structure.name.asc()).all()

    active_q = SocialRequest.query.filter(
        SocialRequest.status.in_(["new", "in_progress"])
    )
    if sid:
        active_q = active_q.filter(SocialRequest.structure_id == sid)
    total_active = active_q.count()

    urgent_q = SocialRequest.query.filter(
        SocialRequest.urgency == "high",
        SocialRequest.status.in_(["new", "in_progress"]),
    )
    if sid:
        urgent_q = urgent_q.filter(SocialRequest.structure_id == sid)
    urgent = urgent_q.count()

    unassigned_q = SocialRequest.query.filter(
        SocialRequest.assigned_to_user_id.is_(None),
        SocialRequest.status.in_(["new", "in_progress"]),
    )
    if sid:
        unassigned_q = unassigned_q.filter(SocialRequest.structure_id == sid)
    unassigned = unassigned_q.count()

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_start = today_start + timedelta(days=1)

    resolved_today_q = db.session.query(func.count(SocialRequestEvent.id)).join(
        SocialRequest, SocialRequest.id == SocialRequestEvent.request_id
    ).filter(
        SocialRequestEvent.event_type == "status_changed",
        SocialRequestEvent.new_value == "resolved",
        SocialRequestEvent.created_at >= today_start,
        SocialRequestEvent.created_at < tomorrow_start,
    )
    if sid:
        resolved_today_q = resolved_today_q.filter(SocialRequest.structure_id == sid)
    resolved_today = resolved_today_q.scalar() or 0

    recent_events_q = SocialRequestEvent.query.order_by(
        SocialRequestEvent.created_at.desc()
    )
    if sid:
        recent_events_q = recent_events_q.join(
            SocialRequest, SocialRequest.id == SocialRequestEvent.request_id
        ).filter(SocialRequest.structure_id == sid)
    recent_events = recent_events_q.limit(30).all()
    health_score = compute_structure_health(sid)

    return render_template(
        "requests/operations.html",
        total_active=total_active,
        urgent=urgent,
        unassigned=unassigned,
        resolved_today=resolved_today,
        recent_events=recent_events,
        structures=structures,
        selected_structure_id=sid,
        health_score=health_score,
    )


@bp.get("/new")
def new_request():
    structures = Structure.query.order_by(Structure.name.asc()).all()
    return render_template(
        "requests/new.html",
        need_types=NEED_TYPES,
        urgencies=URGENCIES,
        structures=structures,
    )


@bp.post("/new")
def create_request():
    structure_id = _safe_int(request.form.get("structure_id"))
    if not structure_id:
        flash(_("Structure is required."), "danger")
        return redirect(url_for("social_requests.new_request"))

    need_type = (request.form.get("need_type") or "").strip()
    urgency = (request.form.get("urgency") or "medium").strip()
    description = (request.form.get("description") or "").strip()
    person_ref = (request.form.get("person_ref") or "").strip() or None

    if not need_type:
        flash(_("Need type is required."), "danger")
        return redirect(url_for("social_requests.new_request"))
    if not description:
        flash(_("Description is required."), "danger")
        return redirect(url_for("social_requests.new_request"))

    sr = SocialRequest(
        structure_id=structure_id,
        need_type=need_type,
        urgency=urgency,
        person_ref=person_ref,
        description=description,
        status="new",
    )
    db.session.add(sr)
    db.session.flush()
    db.session.add(
        SocialRequestEvent(
            request_id=sr.id,
            event_type="created",
            actor_user_id=None,
            old_value=None,
            new_value=f"{sr.need_type}|{sr.urgency}",
        )
    )
    _audit_admin_event(
        "social_request.created",
        sr.id,
        {
            "need_type": sr.need_type,
            "urgency": sr.urgency,
            "status": sr.status,
            "structure_id": sr.structure_id,
        },
    )
    db.session.commit()

    flash(_("Request created."), "success")
    return redirect(url_for("social_requests.details", req_id=sr.id))


@bp.get("/<int:req_id>")
def details(req_id: int):
    sr = SocialRequest.query.get_or_404(req_id)
    structure = Structure.query.get(sr.structure_id)
    users = User.query.order_by(User.email.asc()).limit(300).all()
    assignee = User.query.get(sr.assigned_to_user_id) if sr.assigned_to_user_id else None
    events = (
        SocialRequestEvent.query.filter(SocialRequestEvent.request_id == sr.id)
        .order_by(SocialRequestEvent.created_at.desc())
        .limit(50)
        .all()
    )
    note_events = (
        SocialRequestEvent.query.filter(
            SocialRequestEvent.request_id == sr.id,
            SocialRequestEvent.event_type == "internal_note",
        )
        .order_by(SocialRequestEvent.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template(
        "requests/details.html",
        sr=sr,
        structure=structure,
        users=users,
        assignee=assignee,
        events=events,
        note_events=note_events,
    )


@bp.post("/<int:req_id>/assign")
def assign(req_id: int):
    sr = SocialRequest.query.get_or_404(req_id)
    user_id = _safe_int(request.form.get("assigned_to_user_id"))
    if not user_id:
        flash(_("User is required."), "danger")
        return redirect(url_for("social_requests.details", req_id=req_id))

    u = User.query.get(user_id)
    if not u:
        flash(_("Invalid user."), "danger")
        return redirect(url_for("social_requests.details", req_id=req_id))

    sr.assigned_to_user_id = u.id
    sr.assigned_at = _utcnow()
    if sr.status == "new":
        sr.status = "in_progress"
    db.session.add(
        SocialRequestEvent(
            request_id=sr.id,
            event_type="assigned",
            actor_user_id=None,
            old_value=None,
            new_value=str(u.id),
        )
    )
    _audit_admin_event(
        "social_request.assigned",
        sr.id,
        {"assigned_to_user_id": u.id, "status": sr.status},
    )

    db.session.commit()
    flash(_("Assignment completed."), "success")
    return redirect(url_for("social_requests.details", req_id=req_id))


@bp.post("/<int:req_id>/unassign")
def unassign(req_id: int):
    sr = SocialRequest.query.get_or_404(req_id)
    old_assignee = str(sr.assigned_to_user_id) if sr.assigned_to_user_id else None
    sr.assigned_to_user_id = None
    sr.assigned_at = None
    db.session.add(
        SocialRequestEvent(
            request_id=sr.id,
            event_type="unassigned",
            actor_user_id=None,
            old_value=old_assignee,
            new_value=None,
        )
    )
    _audit_admin_event(
        "social_request.unassigned",
        sr.id,
        {"old_assigned_to_user_id": old_assignee},
    )
    db.session.commit()
    flash(_("Assignment removed."), "success")
    return redirect(url_for("social_requests.details", req_id=req_id))


@bp.post("/<int:req_id>/status")
def set_status(req_id: int):
    sr = SocialRequest.query.get_or_404(req_id)
    new_status = (request.form.get("status") or "").strip()

    if new_status not in ALLOWED_STATUSES:
        flash(_("Invalid status."), "danger")
        return redirect(url_for("social_requests.details", req_id=req_id))

    old_status = sr.status
    sr.status = new_status
    db.session.add(
        SocialRequestEvent(
            request_id=sr.id,
            event_type="status_changed",
            actor_user_id=None,
            old_value=old_status,
            new_value=new_status,
        )
    )
    _audit_admin_event(
        "social_request.status_changed",
        sr.id,
        {"old_status": old_status, "new_status": new_status},
    )
    db.session.commit()
    flash(_("Status updated."), "success")
    return redirect(url_for("social_requests.details", req_id=req_id))


@bp.post("/<int:req_id>/note")
def add_note(req_id: int):
    sr = SocialRequest.query.get_or_404(req_id)
    note = (request.form.get("note") or "").strip()
    if len(note) < 3:
        flash(_("Note is too short."), "danger")
        return redirect(url_for("social_requests.details", req_id=req_id))
    if len(note) > 2000:
        flash(_("Note is too long (max 2000)."), "danger")
        return redirect(url_for("social_requests.details", req_id=req_id))

    actor_user_id = _current_actor_user_id()
    actor_label = _current_actor_label()
    db.session.add(
        SocialRequestEvent(
            request_id=sr.id,
            event_type="internal_note",
            actor_user_id=actor_user_id,
            old_value=actor_label,
            new_value=note,
        )
    )
    _audit_admin_event(
        "social_request.note_added",
        sr.id,
        {"actor": actor_label, "note_len": len(note)},
    )
    db.session.commit()
    flash(_("Internal note added."), "success")
    return redirect(url_for("social_requests.details", req_id=req_id))
