from __future__ import annotations

from flask import Blueprint, abort, redirect, url_for
from ..admin_actor import resolve_current_admin_actor


org_bp = Blueprint("organization_onboarding", __name__)


@org_bp.post("/create-organization")
def create_organization():
    # Keep the legacy URL, but use the canonical structure + invitation flow.
    # The old implementation created a separate User and emailed its password.
    actor = resolve_current_admin_actor()
    if not actor.is_authenticated or not actor.is_platform_global:
        abort(403)
    return redirect(url_for("admin.admin_structure_new"), code=303)
