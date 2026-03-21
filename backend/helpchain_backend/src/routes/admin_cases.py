from __future__ import annotations

import json

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from backend.extensions import db
from ..models import (
    AdminUser,
    Case,
    CaseCollaborator,
    CaseEvent,
    CaseParticipant,
    ProfessionalLead,
    Request,
    Structure,
    User,
)
from ..services.case_assistant import build_case_assistant_recommendation
from ..services.case_matching import suggest_professional_leads_for_case
from ..services.risk_alerts import evaluate_case_alerts
from ..services.risk_engine import update_case_risk
from .admin import (
    CATEGORY_CASE_STATUSES,
    CASE_PARTICIPANT_ROLES,
    CASE_PARTICIPANT_TYPES,
    CASE_PRIORITIES,
    _append_case_event,
    _build_operational_blockages,
    _build_risk_ai_suggestion,
    _cases_enabled,
    _current_structure_id,
    _is_global_admin,
    _now_utc,
    _render_cases_list,
    _scope_requests,
    admin_bp,
    admin_required,
    admin_required_404,
    admin_role_required,
)


def _safe_json_dict(raw: str | None) -> dict:
    txt = (raw or "").strip()
    if not txt:
        return {}
    try:
        val = json.loads(txt)
        if isinstance(val, dict):
            return val
    except Exception:
        return {}
    return {}


def _get_scoped_case_or_404(case_id: int) -> tuple[Case, Request]:
    case_row = db.session.get(Case, int(case_id))
    if not case_row:
        abort(404)
    sid = _current_structure_id()
    if sid and case_row.structure_id != sid and not _is_global_admin():
        collaborator = (
            CaseCollaborator.query.filter(CaseCollaborator.case_id == case_row.id)
            .filter(CaseCollaborator.structure_id == sid)
            .first()
        )
        if not collaborator:
            abort(404)
        req = db.session.get(Request, case_row.request_id)
    else:
        req = _scope_requests(Request.query).filter(Request.id == case_row.request_id).first()
    if not req:
        abort(404)
    return case_row, req


def _upsert_case_participant(
    case_id: int,
    participant_type: str,
    role: str,
    user_id: int | None = None,
    professional_lead_id: int | None = None,
    external_name: str | None = None,
    status: str = "active",
) -> CaseParticipant:
    q = CaseParticipant.query.filter(CaseParticipant.case_id == int(case_id))
    q = q.filter(CaseParticipant.participant_type == participant_type)
    if user_id is not None:
        q = q.filter(CaseParticipant.user_id == int(user_id))
    elif professional_lead_id is not None:
        q = q.filter(CaseParticipant.professional_lead_id == int(professional_lead_id))
    else:
        q = q.filter(CaseParticipant.external_name == (external_name or "").strip())

    row = q.first()
    if row:
        row.role = role
        row.status = status
        if external_name:
            row.external_name = external_name.strip()
        return row

    row = CaseParticipant(
        case_id=int(case_id),
        participant_type=participant_type,
        user_id=user_id,
        professional_lead_id=professional_lead_id,
        external_name=(external_name or "").strip() or None,
        role=role,
        status=status,
        added_at=_now_utc(),
    )
    db.session.add(row)
    return row


@admin_bp.get("/cases")
@admin_required
@admin_role_required("readonly", "ops", "superadmin")
def admin_cases_list():
    admin_required_404()
    return _render_cases_list()


@admin_bp.get("/cases/<int:case_id>")
@admin_required
@admin_role_required("readonly", "ops", "superadmin")
def admin_case_detail(case_id: int):
    admin_required_404()
    if not _cases_enabled():
        flash("Case system tables are not available yet. Run migrations first.", "warning")
        return redirect(url_for("admin.admin_requests"), code=303)

    case_row, req = _get_scoped_case_or_404(case_id)
    risk_ai_suggestion = _build_risk_ai_suggestion(req)
    operational_blockages = _build_operational_blockages(req, case_row)
    suggested_professionals = suggest_professional_leads_for_case(case_row, req, limit=8)
    assistant_recommendation = build_case_assistant_recommendation(
        case_row,
        req,
        risk_ai_suggestion,
        suggested_professionals=suggested_professionals,
    )
    events = (
        CaseEvent.query.filter(CaseEvent.case_id == case_row.id)
        .order_by(CaseEvent.created_at.desc(), CaseEvent.id.desc())
        .limit(200)
        .all()
    )
    participants = (
        CaseParticipant.query.filter(CaseParticipant.case_id == case_row.id)
        .order_by(CaseParticipant.added_at.desc(), CaseParticipant.id.desc())
        .all()
    )
    collaborators = (
        CaseCollaborator.query.filter(CaseCollaborator.case_id == case_row.id)
        .join(Structure, CaseCollaborator.structure_id == Structure.id)
        .with_entities(Structure.name, CaseCollaborator.role)
        .order_by(Structure.name.asc())
        .all()
    )
    owners = (
        AdminUser.query.with_entities(AdminUser.id, AdminUser.username)
        .order_by(AdminUser.username.asc())
        .all()
    )
    users = (
        User.query.with_entities(User.id, User.username, User.email)
        .order_by(User.username.asc())
        .limit(300)
        .all()
    )
    professionals = (
        ProfessionalLead.query.order_by(
            ProfessionalLead.created_at.desc(),
            ProfessionalLead.id.desc(),
        )
        .limit(300)
        .all()
    )
    return render_template(
        "admin/case_detail.html",
        case_row=case_row,
        req=req,
        events=events,
        statuses=list(CATEGORY_CASE_STATUSES),
        priorities=list(CASE_PRIORITIES),
        participant_types=list(CASE_PARTICIPANT_TYPES),
        participant_roles=list(CASE_PARTICIPANT_ROLES),
        owners=owners,
        users=users,
        professionals=professionals,
        participants=participants,
        collaborators=collaborators,
        risk_ai_suggestion=risk_ai_suggestion,
        operational_blockages=operational_blockages,
        suggested_professionals=suggested_professionals,
        assistant_recommendation=assistant_recommendation,
    )


@admin_bp.post("/cases/<int:case_id>/status")
@admin_required
@admin_role_required("ops", "superadmin")
def admin_case_set_status(case_id: int):
    admin_required_404()
    case_row, _req = _get_scoped_case_or_404(case_id)
    new_status = (request.form.get("status") or "").strip().lower()
    if new_status not in CATEGORY_CASE_STATUSES:
        flash("Invalid case status.", "warning")
        return redirect(url_for("admin.admin_case_detail", case_id=case_row.id), code=303)

    old_status = (case_row.status or "").strip().lower()
    if old_status != new_status:
        now = _now_utc()
        case_row.status = new_status
        case_row.last_activity_at = now
        if new_status == "assigned" and not case_row.assigned_at:
            case_row.assigned_at = now
        if new_status == "resolved":
            case_row.resolved_at = now
            _append_case_event(
                case_id=case_row.id,
                actor_user_id=getattr(current_user, "id", None),
                event_type="case_resolved",
                message="Case marked as resolved",
            )
        if new_status == "closed":
            case_row.closed_at = now
            if not case_row.resolved_at:
                case_row.resolved_at = now
            _append_case_event(
                case_id=case_row.id,
                actor_user_id=getattr(current_user, "id", None),
                event_type="case_closed",
                message="Case marked as closed",
            )
        if new_status == "cancelled" and not case_row.closed_at:
            case_row.closed_at = now
        _append_case_event(
            case_id=case_row.id,
            actor_user_id=getattr(current_user, "id", None),
            event_type="status_changed",
            message=f"Status changed: {old_status or '-'} -> {new_status}",
            metadata={"old_status": old_status, "new_status": new_status},
        )
        update_case_risk(case_row)
        evaluate_case_alerts(case_row)
        db.session.commit()
        flash("Case status updated.", "success")
    return redirect(url_for("admin.admin_case_detail", case_id=case_row.id), code=303)


@admin_bp.post("/cases/<int:case_id>/priority")
@admin_required
@admin_role_required("ops", "superadmin")
def admin_case_set_priority(case_id: int):
    admin_required_404()
    case_row, _req = _get_scoped_case_or_404(case_id)
    new_priority = (request.form.get("priority") or "").strip().lower()
    if new_priority not in CASE_PRIORITIES:
        flash("Invalid case priority.", "warning")
        return redirect(url_for("admin.admin_case_detail", case_id=case_row.id), code=303)

    old_priority = (case_row.priority or "").strip().lower()
    if old_priority != new_priority:
        case_row.priority = new_priority
        case_row.last_activity_at = _now_utc()
        _append_case_event(
            case_id=case_row.id,
            actor_user_id=getattr(current_user, "id", None),
            event_type="priority_changed",
            message=f"Priority changed: {old_priority or '-'} -> {new_priority}",
            metadata={"old_priority": old_priority, "new_priority": new_priority},
        )
        update_case_risk(case_row)
        evaluate_case_alerts(case_row)
        db.session.commit()
        flash("Case priority updated.", "success")
    return redirect(url_for("admin.admin_case_detail", case_id=case_row.id), code=303)


@admin_bp.post("/cases/<int:case_id>/assign-owner")
@admin_required
@admin_role_required("ops", "superadmin")
def admin_case_assign_owner(case_id: int):
    admin_required_404()
    case_row, _req = _get_scoped_case_or_404(case_id)
    owner_raw = (request.form.get("owner_user_id") or "").strip()
    owner_id = None
    if owner_raw:
        try:
            owner_id = int(owner_raw)
        except Exception:
            owner_id = None
    if owner_id is not None and not db.session.get(AdminUser, owner_id):
        flash("Selected owner does not exist.", "warning")
        return redirect(url_for("admin.admin_case_detail", case_id=case_row.id), code=303)

    old_owner_id = case_row.owner_user_id
    if old_owner_id != owner_id:
        now = _now_utc()
        case_row.owner_user_id = owner_id
        case_row.last_activity_at = now
        if owner_id and not case_row.assigned_at:
            case_row.assigned_at = now
            if case_row.status in {"new", "triaged"}:
                case_row.status = "assigned"
            _upsert_case_participant(
                case_id=case_row.id,
                participant_type="admin_user",
                role="owner",
                user_id=owner_id,
                status="active",
            )
        _append_case_event(
            case_id=case_row.id,
            actor_user_id=getattr(current_user, "id", None),
            event_type="owner_assigned",
            message=f"Owner changed: {old_owner_id or '-'} -> {owner_id or '-'}",
            metadata={"old_owner_user_id": old_owner_id, "new_owner_user_id": owner_id},
        )
        update_case_risk(case_row)
        evaluate_case_alerts(case_row)
        db.session.commit()
        flash("Case owner updated.", "success")
    return redirect(url_for("admin.admin_case_detail", case_id=case_row.id), code=303)


@admin_bp.post("/cases/<int:case_id>/assign-professional")
@admin_required
@admin_role_required("ops", "superadmin")
def admin_case_assign_professional(case_id: int):
    admin_required_404()
    case_row, _req = _get_scoped_case_or_404(case_id)
    lead_raw = (
        request.form.get("assigned_professional_lead_id")
        or request.form.get("primary_professional_lead_id")
        or ""
    ).strip()
    lead_id = None
    if lead_raw:
        try:
            lead_id = int(lead_raw)
        except Exception:
            lead_id = None
    if lead_id is not None and not db.session.get(ProfessionalLead, lead_id):
        flash("Selected professional lead does not exist.", "warning")
        return redirect(url_for("admin.admin_case_detail", case_id=case_row.id), code=303)

    old_lead_id = case_row.assigned_professional_lead_id
    if old_lead_id != lead_id:
        now = _now_utc()
        case_row.assigned_professional_lead_id = lead_id
        case_row.last_activity_at = now
        if lead_id and not case_row.assigned_at:
            case_row.assigned_at = now
            if case_row.status in {"new", "triaged"}:
                case_row.status = "assigned"
        if lead_id:
            _upsert_case_participant(
                case_id=case_row.id,
                participant_type="professional_lead",
                role="primary_professional",
                professional_lead_id=lead_id,
                status="active",
            )
        _append_case_event(
            case_id=case_row.id,
            actor_user_id=getattr(current_user, "id", None),
            event_type="professional_assigned",
            message=f"Primary professional lead changed: {old_lead_id or '-'} -> {lead_id or '-'}",
            metadata={
                "old_professional_lead_id": old_lead_id,
                "new_professional_lead_id": lead_id,
            },
        )
        update_case_risk(case_row)
        evaluate_case_alerts(case_row)
        db.session.commit()
        flash("Case professional assignment updated.", "success")
    return redirect(url_for("admin.admin_case_detail", case_id=case_row.id), code=303)


@admin_bp.post("/cases/<int:case_id>/participants")
@admin_required
@admin_role_required("ops", "superadmin")
def admin_case_add_participant(case_id: int):
    admin_required_404()
    case_row, _req = _get_scoped_case_or_404(case_id)

    participant_type = (request.form.get("participant_type") or "").strip().lower()
    role = (request.form.get("role") or "contributor").strip().lower()
    participant_status = (request.form.get("status") or "active").strip().lower()
    user_raw = (request.form.get("user_id") or "").strip()
    lead_raw = (request.form.get("professional_lead_id") or "").strip()
    external_name = (request.form.get("external_name") or "").strip()

    if participant_type not in CASE_PARTICIPANT_TYPES:
        flash("Invalid participant type.", "warning")
        return redirect(url_for("admin.admin_case_detail", case_id=case_row.id), code=303)
    if role not in CASE_PARTICIPANT_ROLES:
        role = "contributor"
    if participant_status not in {"active", "inactive"}:
        participant_status = "active"

    user_id = None
    lead_id = None
    if user_raw:
        try:
            user_id = int(user_raw)
        except Exception:
            user_id = None
    if lead_raw:
        try:
            lead_id = int(lead_raw)
        except Exception:
            lead_id = None

    if user_id is not None and not db.session.get(User, user_id):
        flash("Selected user does not exist.", "warning")
        return redirect(url_for("admin.admin_case_detail", case_id=case_row.id), code=303)
    if lead_id is not None and not db.session.get(ProfessionalLead, lead_id):
        flash("Selected professional lead does not exist.", "warning")
        return redirect(url_for("admin.admin_case_detail", case_id=case_row.id), code=303)

    if participant_type == "professional_lead" and not lead_id:
        flash("professional_lead participant requires professional_lead_id.", "warning")
        return redirect(url_for("admin.admin_case_detail", case_id=case_row.id), code=303)
    if participant_type in {"admin_user", "professional_user"} and not user_id:
        flash("Selected participant type requires user_id.", "warning")
        return redirect(url_for("admin.admin_case_detail", case_id=case_row.id), code=303)
    if participant_type in {"association", "external_contact"} and not external_name:
        flash("External participant requires external name.", "warning")
        return redirect(url_for("admin.admin_case_detail", case_id=case_row.id), code=303)

    _upsert_case_participant(
        case_id=case_row.id,
        participant_type=participant_type,
        role=role,
        user_id=user_id,
        professional_lead_id=lead_id,
        external_name=external_name or None,
        status=participant_status,
    )
    case_row.last_activity_at = _now_utc()
    _append_case_event(
        case_id=case_row.id,
        actor_user_id=getattr(current_user, "id", None),
        event_type="participant_added",
        message="Participant added/updated",
        metadata={
            "participant_type": participant_type,
            "role": role,
            "status": participant_status,
            "user_id": user_id,
            "professional_lead_id": lead_id,
            "external_name": external_name or None,
        },
    )
    update_case_risk(case_row)
    evaluate_case_alerts(case_row)
    db.session.commit()
    flash("Case participant updated.", "success")
    return redirect(url_for("admin.admin_case_detail", case_id=case_row.id), code=303)


@admin_bp.post("/cases/<int:case_id>/events")
@admin_required
@admin_role_required("ops", "superadmin")
def admin_case_add_event(case_id: int):
    admin_required_404()
    case_row, _req = _get_scoped_case_or_404(case_id)
    event_type = (request.form.get("event_type") or "note_added").strip().lower()
    message = (request.form.get("message") or "").strip()
    metadata = _safe_json_dict(request.form.get("metadata_json"))
    visibility = (request.form.get("visibility") or "internal").strip().lower()
    if visibility not in {"internal", "public"}:
        visibility = "internal"

    if not event_type:
        event_type = "note_added"
    if not message and not metadata:
        flash("Event is empty.", "warning")
        return redirect(url_for("admin.admin_case_detail", case_id=case_row.id), code=303)

    case_row.last_activity_at = _now_utc()
    _append_case_event(
        case_id=case_row.id,
        actor_user_id=getattr(current_user, "id", None),
        event_type=event_type,
        message=message,
        metadata=metadata or None,
        visibility=visibility,
    )
    update_case_risk(case_row)
    evaluate_case_alerts(case_row)
    db.session.commit()
    flash("Case event added.", "success")
    return redirect(url_for("admin.admin_case_detail", case_id=case_row.id), code=303)
