from __future__ import annotations

from flask import abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from backend.extensions import db
from ..models import (
    Case,
    CaseReferral,
    AdminUser,
    OrganizationConnection,
    ReferralActivity,
    Request,
    RequestActivity,
    Structure,
    User,
    default_referral_shared_scope,
    utc_now,
)
from .admin import (
    _current_structure_id,
    _table_exists,
    admin_bp,
    admin_required,
    admin_required_404,
    admin_role_required,
    audit_admin_action,
    can_edit_request,
    is_safe_url,
    log_request_activity,
)


REFERRAL_ACTIVE_STATUSES = ("sent", "received")
SHARED_SCOPE_KEYS = tuple(default_referral_shared_scope().keys())
PARTNER_STATUSES = ("pending", "active", "suspended", "revoked")
DEFAULT_CONNECTION_PERMISSIONS = {
    "can_send_referrals": True,
    "can_receive_referrals": True,
    "can_view_status_after_transfer": True,
    "can_comment": False,
    "can_share_documents": False,
}


def _admin_structure_id() -> int | None:
    admin = _referral_admin_user()
    value = getattr(admin, "structure_id", None)
    if value is not None:
        return int(value)
    if _referral_is_superadmin():
        return None
    try:
        return _current_structure_id()
    except Exception:
        return None


def _referral_admin_user() -> AdminUser | None:
    admin_user_id = session.get("admin_user_id") or getattr(current_user, "id", None)
    try:
        if admin_user_id:
            return db.session.get(AdminUser, int(admin_user_id))
    except Exception:
        db.session.rollback()
    return current_user if getattr(current_user, "is_authenticated", False) else None


def _referral_is_superadmin() -> bool:
    admin = _referral_admin_user()
    role = (getattr(admin, "role", None) or "").strip().lower()
    return role in {"superadmin", "super_admin", "super-admin"}


def _can_view_referral(referral: CaseReferral) -> bool:
    if _referral_is_superadmin():
        return True
    structure_id = _admin_structure_id()
    return bool(
        structure_id
        and structure_id in {referral.from_structure_id, referral.to_structure_id}
    )


def _require_referral_access(referral: CaseReferral) -> None:
    if not _can_view_referral(referral):
        abort(403)


def _can_accept_or_refuse(referral: CaseReferral) -> bool:
    structure_id = _admin_structure_id()
    return bool(structure_id and structure_id == referral.to_structure_id)


def _can_cancel(referral: CaseReferral) -> bool:
    structure_id = _admin_structure_id()
    return bool(
        structure_id
        and structure_id == referral.from_structure_id
        and referral.status in REFERRAL_ACTIVE_STATUSES
    )


def _can_view_connection(connection: OrganizationConnection) -> bool:
    if _referral_is_superadmin():
        return True
    structure_id = _admin_structure_id()
    return bool(
        structure_id
        and structure_id
        in {connection.source_structure_id, connection.target_structure_id}
    )


def _require_connection_access(connection: OrganizationConnection) -> None:
    if not _can_view_connection(connection):
        abort(403)


def _can_accept_or_refuse_connection(connection: OrganizationConnection) -> bool:
    structure_id = _admin_structure_id()
    return bool(
        structure_id
        and structure_id == connection.target_structure_id
        and connection.status == "pending"
    )


def _can_suspend_or_revoke_connection(connection: OrganizationConnection) -> bool:
    if connection.status not in {"active", "pending", "suspended"}:
        return False
    structure_id = _admin_structure_id()
    return bool(
        structure_id
        and structure_id
        in {connection.source_structure_id, connection.target_structure_id}
    )


def _can_reactivate_connection(connection: OrganizationConnection) -> bool:
    if connection.status != "suspended":
        return False
    return _can_suspend_or_revoke_connection(connection)


def _connection_query():
    query = OrganizationConnection.query.options(
        joinedload(OrganizationConnection.source_structure),
        joinedload(OrganizationConnection.target_structure),
    ).filter(OrganizationConnection.connection_type == "referral")
    if _referral_is_superadmin():
        return query
    structure_id = _admin_structure_id()
    if not structure_id:
        return query.filter(False)
    return query.filter(
        or_(
            OrganizationConnection.source_structure_id == structure_id,
            OrganizationConnection.target_structure_id == structure_id,
        )
    )


def _connection_permissions_summary(connection: OrganizationConnection) -> str:
    permissions = connection.permissions_json or {}
    enabled = [
        "Autoriser l’orientation"
        for key in ("can_send_referrals", "can_receive_referrals")
        if permissions.get(key)
    ]
    if permissions.get("can_view_status_after_transfer"):
        enabled.append("Suivi statut")
    if permissions.get("can_comment"):
        enabled.append("Commentaires")
    if permissions.get("can_share_documents"):
        enabled.append("Documents")
    return ", ".join(dict.fromkeys(enabled)) or "Permissions minimales"


def _connection_status_label(status: str | None) -> str:
    return {
        "active": "Partenaire actif",
        "pending": "En attente",
        "suspended": "Suspendu",
        "revoked": "Révoqué",
    }.get((status or "").strip().lower(), status or "—")


def _audit_connection_action(
    connection: OrganizationConnection,
    action: str,
    payload: dict | None = None,
) -> None:
    audit_admin_action(
        action=f"partner_connection.{action}",
        target_type="OrganizationConnection",
        target_id=connection.id,
        payload=payload or {},
    )


def _target_structure_options():
    structure_id = _admin_structure_id()
    query = Structure.query.order_by(Structure.name.asc())
    if structure_id:
        query = query.filter(Structure.id != structure_id)
    return query.all()


def _log_referral_activity(
    referral: CaseReferral,
    action: str,
    metadata: dict | None = None,
) -> None:
    db.session.add(
        ReferralActivity(
            referral_id=referral.id,
            actor_admin_id=getattr(current_user, "id", None),
            actor_structure_id=_admin_structure_id(),
            action=action,
            metadata_json=metadata or None,
        )
    )


def _referral_query():
    query = CaseReferral.query.options(
        joinedload(CaseReferral.from_structure),
        joinedload(CaseReferral.to_structure),
        joinedload(CaseReferral.request),
    )
    if _referral_is_superadmin():
        return query
    structure_id = _admin_structure_id()
    if not structure_id:
        return query.filter(False)
    return query.filter(
        or_(
            CaseReferral.from_structure_id == structure_id,
            CaseReferral.to_structure_id == structure_id,
        )
    )


def _scope_for_direction(direction: str | None):
    base = _referral_query()
    structure_id = _admin_structure_id()
    if direction == "received" and structure_id:
        return base.filter(CaseReferral.to_structure_id == structure_id)
    if direction == "sent" and structure_id:
        return base.filter(CaseReferral.from_structure_id == structure_id)
    return base


def _parse_shared_scope() -> dict:
    defaults = default_referral_shared_scope()
    parsed = {}
    for key in SHARED_SCOPE_KEYS:
        parsed[key] = bool(request.form.get(key)) if key in request.form else False
    for key, value in defaults.items():
        if key not in parsed:
            parsed[key] = bool(value)
    parsed["share_documents"] = False
    parsed["share_internal_notes"] = False
    return parsed


def _shared_summary(source_request: Request | None, referral: CaseReferral) -> str:
    if referral.message:
        return referral.message.strip()
    if source_request is None:
        return "Orientation partenaire sans résumé source disponible."
    return (
        getattr(source_request, "description", None)
        or getattr(source_request, "message", None)
        or getattr(source_request, "title", None)
        or "Orientation partenaire sans résumé détaillé."
    )


def _safe_referral_username(referral_id: int) -> str:
    return f"orientation_partenaire_{int(referral_id)}"


def _ensure_referral_requester(referral: CaseReferral) -> User:
    username = _safe_referral_username(referral.id)
    email = f"{username}@helpchain.local"
    user = User.query.filter_by(email=email).first()
    if user:
        return user
    user = User(
        username=username,
        email=email,
        password_hash="orientation-partenaire-local-only",
        role="requester",
        is_active=False,
        structure_id=referral.to_structure_id,
    )
    db.session.add(user)
    db.session.flush()
    return user


def _create_local_request_from_referral(referral: CaseReferral) -> Request | None:
    if not _table_exists("requests") or not _table_exists("users"):
        current_app.logger.warning(
            "referral_accept_local_request_skipped_missing_tables referral_id=%s",
            referral.id,
        )
        return None

    source_request = referral.request
    scope = referral.shared_scope_json or default_referral_shared_scope()
    user = _ensure_referral_requester(referral)
    title = f"Orientation partenaire #{referral.id}"
    if scope.get("share_summary") and source_request and getattr(source_request, "title", None):
        title = f"Orientation partenaire - {source_request.title}"[:255]

    local_request = Request(
        title=title,
        description=_shared_summary(source_request, referral) if scope.get("share_summary") else referral.reason,
        message=(
            "Créée depuis une orientation partenaire. "
            f"Orientation #{referral.id} depuis structure #{referral.from_structure_id}."
        ),
        status="pending",
        priority=(
            getattr(source_request, "priority", None)
            if scope.get("share_priority") and source_request
            else "normal"
        ),
        category=(
            getattr(source_request, "category", None)
            if scope.get("share_category") and source_request
            else "general"
        )
        or "general",
        source_channel="partner_referral",
        structure_id=referral.to_structure_id,
        user_id=user.id,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    if scope.get("share_identity") and source_request:
        local_request.name = getattr(source_request, "name", None)
    if scope.get("share_contact") and source_request:
        local_request.email = getattr(source_request, "email", None)
        local_request.phone = getattr(source_request, "phone", None)
    if scope.get("share_risk_level") and source_request:
        local_request.risk_level = getattr(source_request, "risk_level", None) or "standard"
        local_request.risk_score = int(getattr(source_request, "risk_score", None) or 0)
    db.session.add(local_request)
    db.session.flush()
    log_request_activity(
        local_request,
        "partner_referral_created",
        old=None,
        new=f"case_referral:{referral.id}",
        actor_admin_id=getattr(current_user, "id", None),
    )
    return local_request


def _active_partner_connections(source_structure_id: int):
    return _active_partner_options(source_structure_id)


def _active_partner_options(source_structure_id: int):
    rows = (
        OrganizationConnection.query.options(
            joinedload(OrganizationConnection.source_structure),
            joinedload(OrganizationConnection.target_structure),
        )
        .filter(
            or_(
                OrganizationConnection.source_structure_id == source_structure_id,
                OrganizationConnection.target_structure_id == source_structure_id,
            )
        )
        .filter(OrganizationConnection.status == "active")
        .filter(OrganizationConnection.connection_type == "referral")
        .order_by(OrganizationConnection.created_at.desc())
        .all()
    )
    options = []
    seen = set()
    for connection in rows:
        if connection.source_structure_id == source_structure_id:
            partner_id = connection.target_structure_id
            partner = connection.target_structure
        else:
            partner_id = connection.source_structure_id
            partner = connection.source_structure
        if partner_id in seen:
            continue
        seen.add(partner_id)
        options.append(
            {
                "connection": connection,
                "target_structure_id": partner_id,
                "target_structure": partner,
            }
        )
    return options


@admin_bp.get("/referrals")
@login_required
@admin_required
@admin_role_required("ops", "admin", "superadmin")
def admin_referrals_index():
    admin_required_404()
    received_count = _scope_for_direction("received").count()
    sent_count = _scope_for_direction("sent").count()
    referrals = (
        _scope_for_direction(None)
        .order_by(CaseReferral.created_at.desc())
        .limit(100)
        .all()
    )
    return render_template(
        "admin/referrals/index.html",
        referrals=referrals,
        active_tab="all",
        received_count=received_count,
        sent_count=sent_count,
    )


@admin_bp.get("/referrals/received")
@login_required
@admin_required
@admin_role_required("ops", "admin", "superadmin")
def admin_referrals_received():
    admin_required_404()
    referrals = _scope_for_direction("received").order_by(CaseReferral.created_at.desc()).all()
    return render_template(
        "admin/referrals/index.html",
        referrals=referrals,
        active_tab="received",
        received_count=len(referrals),
        sent_count=_scope_for_direction("sent").count(),
    )


@admin_bp.get("/referrals/sent")
@login_required
@admin_required
@admin_role_required("ops", "admin", "superadmin")
def admin_referrals_sent():
    admin_required_404()
    referrals = _scope_for_direction("sent").order_by(CaseReferral.created_at.desc()).all()
    return render_template(
        "admin/referrals/index.html",
        referrals=referrals,
        active_tab="sent",
        received_count=_scope_for_direction("received").count(),
        sent_count=len(referrals),
    )


@admin_bp.get("/referrals/partners")
@login_required
@admin_required
@admin_role_required("ops", "admin", "superadmin")
def admin_referral_partners():
    admin_required_404()
    connections = (
        _connection_query()
        .order_by(OrganizationConnection.created_at.desc())
        .all()
    )
    return render_template(
        "admin/referrals/partners.html",
        connections=connections,
        active_tab="partners",
        status_label=_connection_status_label,
        permissions_summary=_connection_permissions_summary,
        can_accept_or_refuse_connection=_can_accept_or_refuse_connection,
        can_suspend_or_revoke_connection=_can_suspend_or_revoke_connection,
        can_reactivate_connection=_can_reactivate_connection,
    )


@admin_bp.get("/referrals/partners/new")
@login_required
@admin_required
@admin_role_required("ops", "admin", "superadmin")
def admin_referral_partner_new():
    admin_required_404()
    if not _admin_structure_id() and not _referral_is_superadmin():
        abort(403)
    return render_template(
        "admin/referrals/partner_new.html",
        structures=_target_structure_options(),
        default_permissions=DEFAULT_CONNECTION_PERMISSIONS,
    )


@admin_bp.post("/referrals/partners/new")
@login_required
@admin_required
@admin_role_required("ops", "admin", "superadmin")
def admin_referral_partner_create():
    admin_required_404()
    source_structure_id = _admin_structure_id()
    if not source_structure_id:
        flash("Structure source indisponible pour créer une connexion partenaire.", "warning")
        return redirect(url_for("admin.admin_referral_partners"))
    try:
        target_structure_id = int(request.form.get("target_structure_id") or "0")
    except ValueError:
        target_structure_id = 0
    if not target_structure_id or target_structure_id == source_structure_id:
        flash("Structure partenaire invalide.", "warning")
        return redirect(url_for("admin.admin_referral_partner_new"))

    target = db.session.get(Structure, target_structure_id)
    if not target:
        flash("Structure partenaire introuvable.", "warning")
        return redirect(url_for("admin.admin_referral_partner_new"))

    existing = (
        OrganizationConnection.query.filter(
            OrganizationConnection.connection_type == "referral",
            OrganizationConnection.status.in_(("active", "pending")),
            or_(
                (
                    (OrganizationConnection.source_structure_id == source_structure_id)
                    & (OrganizationConnection.target_structure_id == target_structure_id)
                ),
                (
                    (OrganizationConnection.source_structure_id == target_structure_id)
                    & (OrganizationConnection.target_structure_id == source_structure_id)
                ),
            ),
        )
        .order_by(OrganizationConnection.id.desc())
        .first()
    )
    if existing:
        if existing.status == "active":
            flash("Partenaire actif déjà configuré pour cette structure.", "info")
        else:
            flash("Demande de connexion partenaire déjà en attente.", "warning")
        return redirect(url_for("admin.admin_referral_partners"), code=303)

    historical = (
        OrganizationConnection.query.filter(
            OrganizationConnection.connection_type == "referral",
            or_(
                (
                    (OrganizationConnection.source_structure_id == source_structure_id)
                    & (OrganizationConnection.target_structure_id == target_structure_id)
                ),
                (
                    (OrganizationConnection.source_structure_id == target_structure_id)
                    & (OrganizationConnection.target_structure_id == source_structure_id)
                ),
            ),
        )
        .order_by(OrganizationConnection.id.desc())
        .first()
    )
    if historical and historical.status in {"suspended", "revoked"}:
        flash(
            f"Une connexion existe déjà avec le statut { _connection_status_label(historical.status) }.",
            "warning",
        )
        return redirect(url_for("admin.admin_referral_partners"), code=303)

    connection = OrganizationConnection(
        source_structure_id=source_structure_id,
        target_structure_id=target_structure_id,
        status="pending",
        connection_type="referral",
        permissions_json=DEFAULT_CONNECTION_PERMISSIONS.copy(),
        created_by_admin_id=getattr(current_user, "id", None),
        created_at=utc_now(),
    )
    db.session.add(connection)
    db.session.flush()
    _audit_connection_action(
        connection,
        "create",
        {
            "source_structure_id": source_structure_id,
            "target_structure_id": target_structure_id,
        },
    )
    db.session.commit()
    flash("Demande de connexion partenaire créée.", "success")
    return redirect(url_for("admin.admin_referral_partners"), code=303)


@admin_bp.post("/referrals/partners/<int:connection_id>/accept")
@login_required
@admin_required
@admin_role_required("ops", "admin", "superadmin")
def admin_referral_partner_accept(connection_id: int):
    admin_required_404()
    connection = OrganizationConnection.query.get_or_404(connection_id)
    _require_connection_access(connection)
    if not _can_accept_or_refuse_connection(connection):
        abort(403)
    connection.status = "active"
    connection.accepted_at = utc_now()
    db.session.add(connection)
    _audit_connection_action(connection, "accept")
    db.session.commit()
    flash("Partenaire actif.", "success")
    return redirect(url_for("admin.admin_referral_partners"), code=303)


@admin_bp.post("/referrals/partners/<int:connection_id>/refuse")
@login_required
@admin_required
@admin_role_required("ops", "admin", "superadmin")
def admin_referral_partner_refuse(connection_id: int):
    admin_required_404()
    connection = OrganizationConnection.query.get_or_404(connection_id)
    _require_connection_access(connection)
    if not _can_accept_or_refuse_connection(connection):
        abort(403)
    connection.status = "revoked"
    connection.revoked_at = utc_now()
    db.session.add(connection)
    _audit_connection_action(connection, "refuse")
    db.session.commit()
    flash("Demande de connexion partenaire refusée.", "info")
    return redirect(url_for("admin.admin_referral_partners"), code=303)


@admin_bp.post("/referrals/partners/<int:connection_id>/suspend")
@login_required
@admin_required
@admin_role_required("ops", "admin", "superadmin")
def admin_referral_partner_suspend(connection_id: int):
    admin_required_404()
    connection = OrganizationConnection.query.get_or_404(connection_id)
    _require_connection_access(connection)
    if not _can_suspend_or_revoke_connection(connection):
        abort(403)
    connection.status = "suspended"
    db.session.add(connection)
    _audit_connection_action(connection, "suspend")
    db.session.commit()
    flash("Connexion partenaire suspendue.", "info")
    return redirect(url_for("admin.admin_referral_partners"), code=303)


@admin_bp.post("/referrals/partners/<int:connection_id>/revoke")
@login_required
@admin_required
@admin_role_required("ops", "admin", "superadmin")
def admin_referral_partner_revoke(connection_id: int):
    admin_required_404()
    connection = OrganizationConnection.query.get_or_404(connection_id)
    _require_connection_access(connection)
    if not _can_suspend_or_revoke_connection(connection):
        abort(403)
    connection.status = "revoked"
    connection.revoked_at = utc_now()
    db.session.add(connection)
    _audit_connection_action(connection, "revoke")
    db.session.commit()
    flash("Connexion partenaire révoquée.", "info")
    return redirect(url_for("admin.admin_referral_partners"), code=303)


@admin_bp.post("/referrals/partners/<int:connection_id>/reactivate")
@login_required
@admin_required
@admin_role_required("ops", "admin", "superadmin")
def admin_referral_partner_reactivate(connection_id: int):
    admin_required_404()
    connection = OrganizationConnection.query.get_or_404(connection_id)
    _require_connection_access(connection)
    if not _can_reactivate_connection(connection):
        abort(403)
    connection.status = "active"
    if not connection.accepted_at:
        connection.accepted_at = utc_now()
    db.session.add(connection)
    _audit_connection_action(connection, "reactivate")
    db.session.commit()
    flash("Partenaire actif.", "success")
    return redirect(url_for("admin.admin_referral_partners"), code=303)


@admin_bp.get("/referrals/<int:referral_id>")
@login_required
@admin_required
@admin_role_required("ops", "admin", "superadmin")
def admin_referral_detail(referral_id: int):
    admin_required_404()
    referral = CaseReferral.query.options(joinedload(CaseReferral.activities)).get_or_404(referral_id)
    _require_referral_access(referral)
    if _can_accept_or_refuse(referral) and referral.status == "sent":
        referral.status = "received"
        _log_referral_activity(referral, "viewed")
        db.session.commit()
    return render_template(
        "admin/referrals/detail.html",
        referral=referral,
        can_accept_or_refuse=_can_accept_or_refuse(referral),
        can_cancel=_can_cancel(referral),
    )


@admin_bp.post("/referrals/<int:referral_id>/accept")
@login_required
@admin_required
@admin_role_required("ops", "admin", "superadmin")
def admin_referral_accept(referral_id: int):
    admin_required_404()
    referral = CaseReferral.query.get_or_404(referral_id)
    _require_referral_access(referral)
    if not _can_accept_or_refuse(referral):
        abort(403)
    if referral.status not in REFERRAL_ACTIVE_STATUSES:
        flash("Orientation déjà traitée.", "info")
        return redirect(url_for("admin.admin_referral_detail", referral_id=referral.id))
    referral.status = "accepted"
    referral.accepted_by_admin_id = getattr(current_user, "id", None)
    referral.accepted_at = utc_now()
    referral.updated_at = utc_now()
    local_request = None
    try:
        local_request = _create_local_request_from_referral(referral)
    except Exception:
        current_app.logger.exception("referral_accept_local_request_failed referral_id=%s", referral.id)
        db.session.rollback()
        referral = CaseReferral.query.get_or_404(referral_id)
        referral.status = "accepted"
        referral.accepted_by_admin_id = getattr(current_user, "id", None)
        referral.accepted_at = utc_now()
        referral.updated_at = utc_now()
    _log_referral_activity(
        referral,
        "accepted",
        {"local_request_id": getattr(local_request, "id", None)},
    )
    db.session.commit()
    audit_admin_action(
        action="referral.accept",
        target_type="CaseReferral",
        target_id=referral.id,
        payload={"local_request_id": getattr(local_request, "id", None)},
    )
    flash("Orientation acceptée.", "success")
    return redirect(url_for("admin.admin_referral_detail", referral_id=referral.id), code=303)


@admin_bp.post("/referrals/<int:referral_id>/refuse")
@login_required
@admin_required
@admin_role_required("ops", "admin", "superadmin")
def admin_referral_refuse(referral_id: int):
    admin_required_404()
    referral = CaseReferral.query.get_or_404(referral_id)
    _require_referral_access(referral)
    if not _can_accept_or_refuse(referral):
        abort(403)
    if referral.status not in REFERRAL_ACTIVE_STATUSES:
        flash("Orientation déjà traitée.", "info")
        return redirect(url_for("admin.admin_referral_detail", referral_id=referral.id))
    referral.status = "refused"
    referral.refused_at = utc_now()
    referral.refusal_reason = (request.form.get("refusal_reason") or "").strip() or None
    referral.updated_at = utc_now()
    _log_referral_activity(referral, "refused", {"reason": referral.refusal_reason})
    db.session.commit()
    audit_admin_action(
        action="referral.refuse",
        target_type="CaseReferral",
        target_id=referral.id,
        payload={"reason": referral.refusal_reason},
    )
    flash("Orientation refusée.", "warning")
    return redirect(url_for("admin.admin_referral_detail", referral_id=referral.id), code=303)


@admin_bp.post("/referrals/<int:referral_id>/cancel")
@login_required
@admin_required
@admin_role_required("ops", "admin", "superadmin")
def admin_referral_cancel(referral_id: int):
    admin_required_404()
    referral = CaseReferral.query.get_or_404(referral_id)
    _require_referral_access(referral)
    if not _can_cancel(referral):
        abort(403)
    referral.status = "cancelled"
    referral.updated_at = utc_now()
    _log_referral_activity(referral, "cancelled")
    db.session.commit()
    audit_admin_action(
        action="referral.cancel",
        target_type="CaseReferral",
        target_id=referral.id,
        payload={},
    )
    flash("Orientation annulée.", "info")
    return redirect(url_for("admin.admin_referral_detail", referral_id=referral.id), code=303)


@admin_bp.get("/requests/<int:req_id>/refer")
@login_required
@admin_required
@admin_role_required("ops", "admin", "superadmin")
def admin_request_refer(req_id: int):
    admin_required_404()
    from .admin_requests import _scope_requests

    source_request = _scope_requests(Request.query).filter(Request.id == req_id).first_or_404()
    if not can_edit_request(source_request, current_user):
        abort(403)
    source_structure_id = getattr(source_request, "structure_id", None) or _admin_structure_id()
    if not source_structure_id:
        abort(403)
    connections = _active_partner_connections(int(source_structure_id))
    return render_template(
        "admin/referrals/refer_request.html",
        req=source_request,
        connections=connections,
        default_scope=default_referral_shared_scope(),
    )


@admin_bp.post("/requests/<int:req_id>/refer")
@login_required
@admin_required
@admin_role_required("ops", "admin", "superadmin")
def admin_request_refer_submit(req_id: int):
    admin_required_404()
    from .admin_requests import _scope_requests

    source_request = _scope_requests(Request.query).filter(Request.id == req_id).first_or_404()
    if not can_edit_request(source_request, current_user):
        abort(403)
    source_structure_id = getattr(source_request, "structure_id", None) or _admin_structure_id()
    if not source_structure_id:
        abort(403)

    try:
        target_structure_id = int(request.form.get("to_structure_id") or "0")
    except ValueError:
        target_structure_id = 0
    connection = (
        OrganizationConnection.query.filter(
            OrganizationConnection.status == "active",
            OrganizationConnection.connection_type == "referral",
            or_(
                (
                    (OrganizationConnection.source_structure_id == int(source_structure_id))
                    & (OrganizationConnection.target_structure_id == target_structure_id)
                ),
                (
                    (OrganizationConnection.source_structure_id == target_structure_id)
                    & (OrganizationConnection.target_structure_id == int(source_structure_id))
                ),
            ),
        ).first()
    )
    if not connection:
        flash("Structure destinataire non autorisée pour les orientations partenaires.", "warning")
        return redirect(url_for("admin.admin_request_refer", req_id=source_request.id))

    reason = (request.form.get("reason") or "").strip()
    message = (request.form.get("message") or "").strip()
    if not reason:
        flash("Motif d’orientation requis.", "warning")
        return redirect(url_for("admin.admin_request_refer", req_id=source_request.id))

    linked_case = Case.query.filter(Case.request_id == source_request.id).first() if _table_exists("cases") else None
    referral = CaseReferral(
        case_id=getattr(linked_case, "id", None),
        request_id=source_request.id,
        from_structure_id=int(source_structure_id),
        to_structure_id=target_structure_id,
        created_by_admin_id=getattr(current_user, "id", None),
        status="sent",
        reason=reason[:255],
        message=message or None,
        shared_scope_json=_parse_shared_scope(),
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.session.add(referral)
    db.session.flush()
    _log_referral_activity(referral, "created")
    _log_referral_activity(referral, "sent", {"request_id": source_request.id})
    db.session.add(
        RequestActivity(
            request_id=source_request.id,
            actor_admin_id=getattr(current_user, "id", None),
            action="partner_referral_sent",
            old_value=None,
            new_value=f"case_referral:{referral.id}",
            created_at=utc_now(),
        )
    )
    db.session.commit()
    audit_admin_action(
        action="referral.send",
        target_type="CaseReferral",
        target_id=referral.id,
        payload={
            "request_id": source_request.id,
            "from_structure_id": int(source_structure_id),
            "to_structure_id": target_structure_id,
        },
    )
    flash("Orientation partenaire envoyée.", "success")
    next_url = (request.form.get("next") or "").strip()
    if next_url and is_safe_url(next_url):
        return redirect(next_url, code=303)
    return redirect(url_for("admin.admin_referral_detail", referral_id=referral.id), code=303)
