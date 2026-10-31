from __future__ import annotations

from backend.helpchain_backend.src.routes.admin import _pilotage_quality_reason_label


def test_founder_operations_queue_localizes_quality_reasons_without_changing_codes():
    assert (
        _pilotage_quality_reason_label("No operational owner is assigned")
        == "Aucun responsable opérationnel n’est assigné"
    )
    assert (
        _pilotage_quality_reason_label("No meaningful activity for at least 72 hours")
        == "Aucune activité significative depuis au moins 72 heures"
    )
    assert _pilotage_quality_reason_label("no_recent_activity") == "no_recent_activity"

def test_founder_operations_queue_keeps_pilotage_access_controlled(
    authenticated_admin_client,
):
    response = authenticated_admin_client.get("/admin/pilotage")

    assert response.status_code == 200


def test_founder_operations_queue_denies_anonymous_access(app):
    response = app.test_client().get("/admin/pilotage", follow_redirects=False)

    assert response.status_code in {302, 303, 403, 404}
