from __future__ import annotations

from datetime import datetime, timedelta

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import and_, func, or_

from backend.extensions import db
from ..models import AdminUser, OrganizationAccessRequest, Request, Structure
from ..services.organization_onboarding import (
    AccessRequestAlreadyApproved,
    AccessRequestEmailAlreadyUsed,
    AccessRequestNotApprovable,
    approve_access_request,
    mark_access_request_need_info,
    reject_access_request,
)
from .admin import (
    CLOSED_STATUSES,
    _require_global_admin,
    admin_bp,
    admin_required,
    admin_role_required,
    audit_admin_action,
)


def compute_structure_health(structure_id: int) -> int:
    score = 100
    now = datetime.utcnow()

    # Requests without assigned operator/owner
    unassigned = (
        Request.query.filter(Request.structure_id == structure_id)
        .filter(Request.owner_id.is_(None))
        .count()
    )
    if unassigned > 0:
        score -= 30

    # Requests inactive for more than 48h (no update, or old update)
    stale_cutoff = now - timedelta(hours=48)
    stale = (
        Request.query.filter(Request.structure_id == structure_id)
        .filter(
            or_(
                Request.updated_at < stale_cutoff,
                and_(Request.updated_at.is_(None), Request.created_at < stale_cutoff),
            )
        )
        .count()
    )
    if stale > 0:
        score -= 20

    # Active requests older than 3 days (treat non-closed as active)
    overdue_cutoff = now - timedelta(days=3)
    overdue = (
        Request.query.filter(Request.structure_id == structure_id)
        .filter(Request.created_at < overdue_cutoff)
        .filter(or_(Request.status.is_(None), ~Request.status.in_(list(CLOSED_STATUSES))))
        .count()
    )
    if overdue > 0:
        score -= 20

    return max(score, 0)


def compute_structure_alerts(structure_id: int) -> dict[str, int]:
    now = datetime.utcnow()
    base = Request.query.filter(Request.structure_id == structure_id)

    unassigned_count = base.filter(Request.owner_id.is_(None)).count()

    urgent_priorities = {"high", "critical", "urgent"}
    urgent_unassigned_count = (
        base.filter(Request.owner_id.is_(None))
        .filter(func.lower(func.coalesce(Request.priority, "")).in_(urgent_priorities))
        .count()
    )

    stale_cutoff = now - timedelta(hours=72)
    stale_count = base.filter(
        (Request.updated_at < stale_cutoff)
        | (Request.updated_at.is_(None) & (Request.created_at < stale_cutoff))
    ).count()

    overdue_cutoff = now - timedelta(days=3)
    active_filter = or_(
        Request.status.is_(None),
        ~func.lower(func.coalesce(Request.status, "")).in_(list(CLOSED_STATUSES)),
    )
    overdue_count = (
        base.filter(active_filter).filter(Request.created_at < overdue_cutoff).count()
    )

    return {
        "unassigned_count": int(unassigned_count or 0),
        "urgent_unassigned_count": int(urgent_unassigned_count or 0),
        "stale_count": int(stale_count or 0),
        "overdue_count": int(overdue_count or 0),
    }


@admin_bp.get("/structures")
@admin_required
@admin_role_required("superadmin")
def admin_structures():
    _require_global_admin()
    rows = Structure.query.order_by(Structure.name.asc(), Structure.id.asc()).all()
    return (
        render_template(
            "admin/structures.html",
            structures=rows,
        ),
        200,
    )


@admin_bp.get("/organizations/requests")
@admin_required
@admin_role_required("superadmin")
def admin_organization_access_requests():
    _require_global_admin()
    rows = (
        OrganizationAccessRequest.query.order_by(
            OrganizationAccessRequest.created_at.desc(),
            OrganizationAccessRequest.id.desc(),
        )
        .limit(200)
        .all()
    )
    return (
        render_template(
            "admin/organization_access_requests.html",
            access_requests=rows,
        ),
        200,
    )


@admin_bp.get("/organizations/requests/<int:req_id>")
@admin_required
@admin_role_required("superadmin")
def admin_organization_access_request_detail(req_id: int):
    _require_global_admin()
    row = OrganizationAccessRequest.query.get_or_404(req_id)
    return (
        render_template(
            "admin/organization_access_request_detail.html",
            access_request=row,
        ),
        200,
    )


def _reviewer_admin_id() -> int | None:
    try:
        return int(getattr(current_user, "id", None))
    except (TypeError, ValueError):
        return None


def _review_notes() -> str | None:
    notes = (request.form.get("internal_notes") or "").strip()
    return notes or None


@admin_bp.post("/organizations/requests/<int:req_id>/approve")
@admin_required
@admin_role_required("superadmin")
def admin_organization_access_request_approve(req_id: int):
    _require_global_admin()
    row = OrganizationAccessRequest.query.get_or_404(req_id)
    try:
        structure, admin_user = approve_access_request(
            row,
            reviewer_admin_id=_reviewer_admin_id(),
            internal_notes=_review_notes(),
        )
    except AccessRequestAlreadyApproved:
        flash("Cette demande a deja ete approuvee. Aucune structure supplementaire n'a ete creee.", "warning")
    except AccessRequestEmailAlreadyUsed:
        flash("Un administrateur utilise deja cet email. Approbation interrompue.", "danger")
    except AccessRequestNotApprovable:
        flash("Cette demande ne peut pas etre approuvee dans son statut actuel.", "danger")
    except Exception:
        flash("L'approbation a echoue. Aucune creation partielle n'a ete conservee.", "danger")
        raise
    else:
        audit_admin_action(
            action="ORGANIZATION_ACCESS_APPROVED",
            target_type="OrganizationAccessRequest",
            target_id=row.id,
            payload={
                "structure": {
                    "id": structure.id,
                    "name": structure.name,
                    "slug": structure.slug,
                },
                "admin_user_id": admin_user.id,
                "actor": {
                    "admin_user_id": getattr(current_user, "id", None),
                    "username": getattr(current_user, "username", None),
                },
            },
        )
        flash("Demande approuvee. Structure et administrateur crees.", "success")
    return redirect(
        url_for("admin.admin_organization_access_request_detail", req_id=row.id),
        code=303,
    )


@admin_bp.post("/organizations/requests/<int:req_id>/reject")
@admin_required
@admin_role_required("superadmin")
def admin_organization_access_request_reject(req_id: int):
    _require_global_admin()
    row = OrganizationAccessRequest.query.get_or_404(req_id)
    try:
        reject_access_request(
            row,
            reviewer_admin_id=_reviewer_admin_id(),
            internal_notes=_review_notes(),
        )
    except AccessRequestAlreadyApproved:
        flash("Cette demande est deja approuvee et ne peut plus etre rejetee.", "warning")
    else:
        flash("Demande rejetee.", "success")
    return redirect(
        url_for("admin.admin_organization_access_request_detail", req_id=row.id),
        code=303,
    )


@admin_bp.post("/organizations/requests/<int:req_id>/need-info")
@admin_required
@admin_role_required("superadmin")
def admin_organization_access_request_need_info(req_id: int):
    _require_global_admin()
    row = OrganizationAccessRequest.query.get_or_404(req_id)
    try:
        mark_access_request_need_info(
            row,
            reviewer_admin_id=_reviewer_admin_id(),
            internal_notes=_review_notes(),
        )
    except AccessRequestAlreadyApproved:
        flash("Cette demande est deja approuvee et ne peut plus etre modifiee.", "warning")
    else:
        flash("Demande marquee comme information complementaire requise.", "success")
    return redirect(
        url_for("admin.admin_organization_access_request_detail", req_id=row.id),
        code=303,
    )


@admin_bp.get("/structures/new")
@admin_required
@admin_role_required("superadmin")
def admin_structure_new():
    _require_global_admin()
    return (
        render_template(
            "admin/structure_new.html",
        ),
        200,
    )


@admin_bp.post("/structures/new")
@admin_required
@admin_role_required("superadmin")
def admin_structure_create():
    _require_global_admin()
    name = (request.form.get("name") or "").strip()
    slug = (request.form.get("slug") or "").strip()

    errors = {}
    if not name:
        errors["name"] = "Le nom est requis."
    if not slug:
        errors["slug"] = "Le slug est requis."

    if slug:
        existing = Structure.query.filter(Structure.slug == slug).first()
        if existing:
            errors["slug"] = "Ce slug est déjà utilisé."

    if errors:
        for msg in errors.values():
            flash(msg, "danger")
        return (
            render_template(
                "admin/structure_new.html",
                form_data={"name": name, "slug": slug},
                form_errors=errors,
            ),
            400,
        )

    row = Structure(
        name=name,
        slug=slug,
        created_at=datetime.utcnow(),
    )
    db.session.add(row)
    db.session.commit()
    audit_admin_action(
        action="STRUCTURE_CREATED",
        target_type="Structure",
        target_id=row.id,
        payload={
            "structure": {"id": row.id, "name": row.name, "slug": row.slug},
            "actor": {
                "admin_user_id": getattr(current_user, "id", None),
                "username": getattr(current_user, "username", None),
            },
        },
    )
    flash("Structure créée.", "success")
    return redirect(url_for("admin.admin_structure_detail", structure_id=row.id), code=303)


@admin_bp.get("/structures/<int:structure_id>")
@admin_required
@admin_role_required("superadmin")
def admin_structure_detail(structure_id: int):
    _require_global_admin()
    structure = Structure.query.get_or_404(structure_id)
    users_count = AdminUser.query.filter(
        AdminUser.structure_id == structure_id
    ).count()
    open_filter = or_(
        Request.status.is_(None), ~func.lower(Request.status).in_(list(CLOSED_STATUSES))
    )
    active_requests = (
        Request.query.filter(Request.structure_id == structure_id)
        .filter(open_filter)
        .count()
    )
    done_requests = (
        Request.query.filter(Request.structure_id == structure_id)
        .filter(func.lower(Request.status) == "done")
        .count()
    )
    recent_requests = (
        Request.query.filter_by(structure_id=structure_id)
        .order_by(Request.created_at.desc())
        .limit(10)
        .all()
    )
    health_score = compute_structure_health(structure_id)
    alerts = compute_structure_alerts(structure_id)
    return (
        render_template(
            "admin/structure_dashboard.html",
            structure=structure,
            users_count=users_count,
            active_requests=active_requests,
            done_requests=done_requests,
            recent_requests=recent_requests,
            health_score=health_score,
            alerts=alerts,
        ),
        200,
    )


@admin_bp.post("/structures/<int:structure_id>/assign-admin")
@admin_required
@admin_role_required("superadmin")
def admin_structure_assign_admin(structure_id: int):
    _require_global_admin()
    row = Structure.query.get_or_404(structure_id)
    admin_id_raw = (request.form.get("admin_id") or "").strip()
    if not admin_id_raw:
        flash("Veuillez sélectionner un administrateur.", "danger")
        return redirect(url_for("admin.admin_structure_detail", structure_id=row.id), code=303)
    try:
        admin_id = int(admin_id_raw)
    except Exception:
        flash("Administrateur invalide.", "danger")
        return redirect(url_for("admin.admin_structure_detail", structure_id=row.id), code=303)

    admin_user = db.session.get(AdminUser, admin_id)
    if not admin_user:
        flash("Administrateur introuvable.", "danger")
        return redirect(url_for("admin.admin_structure_detail", structure_id=row.id), code=303)

    admin_user.structure_id = row.id
    db.session.commit()
    audit_admin_action(
        action="STRUCTURE_ADMIN_ASSIGNED",
        target_type="AdminUser",
        target_id=admin_user.id,
        payload={
            "structure": {"id": row.id, "name": row.name, "slug": row.slug},
            "admin_user_id": admin_user.id,
            "admin_username": getattr(admin_user, "username", None),
            "actor": {
                "admin_user_id": getattr(current_user, "id", None),
                "username": getattr(current_user, "username", None),
            },
        },
    )
    flash("Administrateur assigné à la structure.", "success")
    return redirect(url_for("admin.admin_structure_detail", structure_id=row.id), code=303)
