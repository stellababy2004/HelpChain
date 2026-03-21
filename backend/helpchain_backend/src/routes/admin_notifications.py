from __future__ import annotations

from .admin import (
    _render_notifications_list,
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
