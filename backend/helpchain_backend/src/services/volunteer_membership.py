"""Explicit admin-approved links between legacy identities and canonical actors."""

import json

from sqlalchemy import func

from ..admin_actor import resolve_current_admin_actor
from ..models import Intervenant, IntervenantActivity, Structure, Volunteer, db


class VolunteerLinkError(ValueError):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def link_volunteer_to_intervenant(
    *,
    volunteer_id: int,
    intervenant_id: int,
    structure_id: int,
    confirmed: bool = False,
) -> bool:
    """Stage the link and audit atomically; caller commits. Return whether newly linked.

    All bridge writers lock the Volunteer first, then the target Intervenant.
    PostgreSQL row locks serialize competing links without a schema constraint.
    """
    actor = resolve_current_admin_actor()
    if not actor.is_authenticated or actor.role not in {"admin", "superadmin"}:
        raise VolunteerLinkError("Vous ne pouvez pas lier ce compte bénévole.", 403)
    if any(
        type(value) is not int or value <= 0
        for value in (volunteer_id, intervenant_id, structure_id)
    ):
        raise VolunteerLinkError(
            "Compte, intervenant et structure explicites requis.", 400
        )
    if not actor.is_platform_global and actor.structure_id != structure_id:
        raise VolunteerLinkError(
            "Cette structure ne relève pas de votre périmètre.", 403
        )
    if confirmed is not True:
        raise VolunteerLinkError(
            "Confirmez explicitement le compte bénévole à lier.", 400
        )

    try:
        volunteer = (
            Volunteer.query.filter_by(id=volunteer_id)
            .populate_existing()
            .with_for_update(of=Volunteer)
            .first()
        )
        if volunteer is None:
            raise VolunteerLinkError("Compte bénévole introuvable.", 404)
        # Email only detects ambiguous login identities; it never chooses membership.
        normalized_email = (volunteer.email or "").strip().lower()
        if (
            normalized_email
            and db.session.query(Volunteer.id)
            .filter(
                func.lower(func.trim(Volunteer.email)) == normalized_email,
                Volunteer.id != volunteer.id,
            )
            .first()
            is not None
        ):
            raise VolunteerLinkError(
                "Plusieurs comptes utilisent cet email. Vérification requise.", 409
            )
        target = (
            Intervenant.query.filter_by(id=intervenant_id)
            # Lock only the actor, not the nullable eager-joined Structure side.
            .populate_existing()
            .with_for_update(of=Intervenant)
            .first()
        )
        if target is None:
            raise VolunteerLinkError("Intervenant introuvable.", 404)
        if (
            target.structure_id != structure_id
            or db.session.get(Structure, structure_id) is None
        ):
            raise VolunteerLinkError(
                "La structure ne correspond pas à cet intervenant.", 403
            )
        if target.actor_type != "volunteer":
            raise VolunteerLinkError(
                "Seul un intervenant Bénévole peut recevoir ce lien.", 409
            )
        if target.legacy_volunteer_id not in (None, volunteer.id):
            raise VolunteerLinkError(
                "Cet intervenant est déjà lié à un autre compte.", 409
            )

        # Include inactive actors and same-structure duplicates; neither is a transfer.
        links = (
            db.session.query(Intervenant.id)
            .filter(Intervenant.legacy_volunteer_id == volunteer.id)
            .all()
        )
        if any(link_id != target.id for (link_id,) in links):
            raise VolunteerLinkError(
                "Ce compte bénévole est déjà lié à un autre intervenant.", 409
            )

        changed = target.legacy_volunteer_id is None
        target.legacy_volunteer_id = volunteer.id
        db.session.add(
            IntervenantActivity(
                intervenant_id=target.id,
                structure_id=structure_id,
                actor_admin_id=actor.admin_id,
                event_type="volunteer_account_linked",
                label="Compte bénévole lié" if changed else "Lien bénévole déjà établi",
                old_value=None if changed else str(volunteer.id),
                new_value=str(volunteer.id),
                meta_json=json.dumps(
                    {
                        "volunteer_id": volunteer.id,
                        "intervenant_id": target.id,
                        "structure_id": structure_id,
                        "result": "linked" if changed else "already_linked",
                    },
                    sort_keys=True,
                ),
            )
        )
        # An unavailable audit store must not leave an unaudited membership behind.
        db.session.flush()
        return changed
    except Exception:
        db.session.rollback()
        raise
