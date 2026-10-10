from backend.helpchain_backend.src.services.audience_geo import approximate_audience_location


def test_geo_lookup_disabled_by_default(app):
    with app.app_context():
        assert approximate_audience_location("8.8.8.8") is None


def test_geo_lookup_missing_database_is_safe(app):
    with app.app_context():
        app.config["AUDIENCE_GEOIP_ENABLED"] = True
        app.config["AUDIENCE_GEOIP_DATABASE_PATH"] = "/missing/GeoLite2-City.mmdb"
        assert approximate_audience_location("8.8.8.8") is None


def test_geo_lookup_rejects_private_addresses(app, tmp_path):
    with app.app_context():
        path = tmp_path / "GeoLite2-City.mmdb"
        path.write_bytes(b"placeholder")
        app.config["AUDIENCE_GEOIP_ENABLED"] = True
        app.config["AUDIENCE_GEOIP_DATABASE_PATH"] = str(path)
        assert approximate_audience_location("127.0.0.1") is None
        assert approximate_audience_location("192.168.1.10") is None
