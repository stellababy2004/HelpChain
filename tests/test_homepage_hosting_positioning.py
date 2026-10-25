def test_homepage_describes_qualified_hosting_options(client):
    response = client.get("/")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    for text in (
        'id="hc-home-hosting-title"',
        "Cloud",
        "Environnement d",
        "Infrastructure de votre organisation",
        "validation technique",
        "services externes optionnels",
        "Discuter de vos exigences d",
    ):
        assert text in body

    for forbidden in (
        "on-premise ready",
        "on-premise turnkey",
        "100 % des données restent chez vous",
        "ISO 27001",
        "HDS",
        "SecNumCloud",
        "air-gapped",
    ):
        assert forbidden not in body
