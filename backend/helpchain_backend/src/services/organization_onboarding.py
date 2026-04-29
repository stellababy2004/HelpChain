from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import func

from backend.extensions import db
from backend.helpchain_backend.src.models import (
    AdminUser,
    OrganizationAccessRequest,
    Structure,
)
from backend.helpchain_backend.src.services.structure_service import _slugify, _unique_slug


APPROVABLE_STATUSES = {"new", "reviewed", "need_info"}


class AccessRequestAlreadyApproved(ValueError):
    pass


class AccessRequestNotApprovable(ValueError):
    pass


class AccessRequestEmailAlreadyUsed(ValueError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _clean_notes(internal_notes: str | None) -> str | None:
    notes = (internal_notes or "").strip()
    return notes or None


def _unique_admin_username(contact_name: str | None, email: str) -> str:
    base_source = (contact_name or email.split("@", 1)[0] or "admin").strip()
    base = _slugify(base_source).replace("-", "_")[:60] or "admin"
    username = base
    idx = 2
    while (
        db.session.query(AdminUser.id)
        .filter(func.lower(AdminUser.username) == username.lower())
        .first()
        is not None
    ):
        suffix = f"_{idx}"
        username = f"{base[: 80 - len(suffix)]}{suffix}"
        idx += 1
    return username


def _temporary_password() -> str:
    return f"Temp{secrets.token_urlsafe(14)}9a"


def create_structure_from_access_request(
    access_request: OrganizationAccessRequest,
) -> Structure:
    name = (access_request.organization_name or "").strip()
    if not name:
        raise ValueError("organization_name_required")

    slug = _unique_slug(_slugify(name))
    structure = Structure(name=name, slug=slug)
    if hasattr(structure, "status"):
        structure.status = "active"
    db.session.add(structure)
    db.session.flush()
    return structure


def create_org_admin_for_structure(
    access_request: OrganizationAccessRequest,
    structure: Structure,
) -> tuple[AdminUser, str]:
    email = (access_request.email or "").strip().lower()
    if not email:
        raise ValueError("email_required")

    existing = (
        db.session.query(AdminUser)
        .filter(func.lower(AdminUser.email) == email.lower())
        .first()
    )
    if existing:
        raise AccessRequestEmailAlreadyUsed("admin_email_exists")

    admin = AdminUser(
        username=_unique_admin_username(access_request.contact_name, email),
        email=email,
        role="admin",
        is_active=True,
        structure_id=structure.id,
        password_hash="",
        must_change_password=True,
        onboarding_step="welcome",
    )
    temporary_password = _temporary_password()
    admin.set_password(temporary_password)
    db.session.add(admin)
    db.session.flush()
    return admin, temporary_password


def approve_access_request(
    access_request: OrganizationAccessRequest,
    *,
    reviewer_admin_id: int | None,
    internal_notes: str | None = None,
) -> tuple[Structure, AdminUser, str]:
    status = ((access_request.status or "").strip().lower() or "new")
    if status == "approved":
        raise AccessRequestAlreadyApproved("access_request_already_approved")
    if status not in APPROVABLE_STATUSES:
        raise AccessRequestNotApprovable("access_request_not_approvable")

    try:
        structure = create_structure_from_access_request(access_request)
        admin, temporary_password = create_org_admin_for_structure(access_request, structure)
        access_request.status = "approved"
        access_request.reviewed_by_admin_id = reviewer_admin_id
        access_request.reviewed_at = _now()
        access_request.internal_notes = _clean_notes(internal_notes)
        access_request.updated_at = _now()
        db.session.commit()
        return structure, admin, temporary_password
    except Exception:
        db.session.rollback()
        raise


def reject_access_request(
    access_request: OrganizationAccessRequest,
    *,
    reviewer_admin_id: int | None,
    internal_notes: str | None = None,
) -> OrganizationAccessRequest:
    return _mark_review_status(
        access_request,
        status="rejected",
        reviewer_admin_id=reviewer_admin_id,
        internal_notes=internal_notes,
    )


def mark_access_request_need_info(
    access_request: OrganizationAccessRequest,
    *,
    reviewer_admin_id: int | None,
    internal_notes: str | None = None,
) -> OrganizationAccessRequest:
    return _mark_review_status(
        access_request,
        status="need_info",
        reviewer_admin_id=reviewer_admin_id,
        internal_notes=internal_notes,
    )


def _mark_review_status(
    access_request: OrganizationAccessRequest,
    *,
    status: str,
    reviewer_admin_id: int | None,
    internal_notes: str | None = None,
) -> OrganizationAccessRequest:
    if ((access_request.status or "").strip().lower() or "new") == "approved":
        raise AccessRequestAlreadyApproved("access_request_already_approved")

    try:
        access_request.status = status
        access_request.reviewed_by_admin_id = reviewer_admin_id
        access_request.reviewed_at = _now()
        access_request.internal_notes = _clean_notes(internal_notes)
        access_request.updated_at = _now()
        db.session.commit()
        return access_request
    except Exception:
        db.session.rollback()
        raise
