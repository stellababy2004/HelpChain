"""Transactional service for explicit volunteer/structure memberships."""

from __future__ import annotations

from backend.extensions import db
from backend.models import (
    AdminUser,
    SecurityEvent,
    Volunteer,
    VolunteerStructureMembership,
)

from ..admin_actor import resolve_current_admin_actor


class MembershipError(ValueError):
    """Expected business or authorization failure."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


VALID_STATUSES = {"pending", "approved", "suspended", "revoked"}


def _require_admin_for_structure(structure_id: int, *, allow_global: bool):
    actor = resolve_current_admin_actor()
    if not actor.is_authenticated or not actor.is_admin:
        raise MembershipError("admin_required", 403)
    if actor.is_platform_global:
        if not allow_global:
            raise MembershipError("explicit_global_authorization_required", 403)
    elif actor.structure_id != structure_id:
        raise MembershipError("structure_scope_mismatch", 403)
    return actor


def _audit(action: str, membership: VolunteerStructureMembership, actor, reason=None):
    db.session.add(
        SecurityEvent(
            event_type=f"volunteer_membership.{action}",
            actor_type="admin",
            actor_id=actor.admin_id,
            route="volunteer_structure_memberships",
            method="SERVICE",
            meta={
                "membership_id": membership.id,
                "structure_id": membership.structure_id,
                "volunteer_id": membership.volunteer_id,
                "status": membership.status,
                "reason_present": bool(reason),
            },
        )
    )


def request_membership(
    *, volunteer_id: int, structure_id: int, requester_user_id: int
) -> VolunteerStructureMembership:
    """Create a pending request for the volunteer's own linked user identity."""
    volunteer = db.session.get(Volunteer, volunteer_id)
    if volunteer is None:
        raise MembershipError("volunteer_not_found", 404)
    if volunteer.user_id is None or int(volunteer.user_id) != int(requester_user_id):
        raise MembershipError("volunteer_identity_not_verified", 403)

    existing = VolunteerStructureMembership.query.filter_by(
        volunteer_id=volunteer_id, structure_id=structure_id
    ).first()
    if existing is not None:
        raise MembershipError("membership_already_exists", 409)

    membership = VolunteerStructureMembership(
        volunteer_id=volunteer_id,
        structure_id=structure_id,
        status="pending",
        requested_by_user_id=requester_user_id,
    )
    db.session.add(membership)
    db.session.flush()
    return membership


def _get_membership(membership_id: int) -> VolunteerStructureMembership:
    membership = db.session.get(VolunteerStructureMembership, membership_id)
    if membership is None:
        raise MembershipError("membership_not_found", 404)
    return membership


def approve_membership(*, membership_id: int, allow_global: bool = False, reason=None):
    membership = _get_membership(membership_id)
    actor = _require_admin_for_structure(
        membership.structure_id, allow_global=allow_global
    )
    if membership.status not in {"pending", "suspended"}:
        raise MembershipError("invalid_approval_transition", 409)
    membership.status = "approved"
    membership.approved_by_admin_id = actor.admin_id
    membership.approved_at = db.func.now()
    membership.decision_reason = reason
    _audit("approved", membership, actor, reason)
    db.session.flush()
    return membership


def suspend_membership(*, membership_id: int, allow_global: bool = False, reason=None):
    membership = _get_membership(membership_id)
    actor = _require_admin_for_structure(
        membership.structure_id, allow_global=allow_global
    )
    if membership.status != "approved":
        raise MembershipError("invalid_suspension_transition", 409)
    membership.status = "suspended"
    membership.suspended_by_admin_id = actor.admin_id
    membership.suspended_at = db.func.now()
    membership.decision_reason = reason
    _audit("suspended", membership, actor, reason)
    db.session.flush()
    return membership


def revoke_membership(*, membership_id: int, allow_global: bool = False, reason=None):
    membership = _get_membership(membership_id)
    actor = _require_admin_for_structure(
        membership.structure_id, allow_global=allow_global
    )
    if membership.status == "revoked":
        raise MembershipError("membership_already_revoked", 409)
    membership.status = "revoked"
    membership.revoked_by_admin_id = actor.admin_id
    membership.revoked_at = db.func.now()
    membership.decision_reason = reason
    _audit("revoked", membership, actor, reason)
    db.session.flush()
    return membership


def is_membership_approved(*, volunteer_id: int, structure_id: int) -> bool:
    return (
        db.session.query(VolunteerStructureMembership.id)
        .filter_by(
            volunteer_id=volunteer_id,
            structure_id=structure_id,
            status="approved",
        )
        .first()
        is not None
    )
