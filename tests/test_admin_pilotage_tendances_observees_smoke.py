from __future__ import annotations


def test_admin_pilotage_tendances_observees_fallback_smoke(authenticated_admin_client):
    resp = authenticated_admin_client.get("/admin/pilotage")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    assert "Tendances observées" in html
    assert "Repères simples issus de l’activité récente et des situations suivies." in html
    assert "Aucune tendance catégorielle significative à ce stade." in html
    assert "Données insuffisantes pour estimer le délai moyen avant affectation." in html
    assert "Aucun signal de vigilance particulier n’est identifié à ce stade." in html

