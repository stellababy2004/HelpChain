import re
from pathlib import Path

template = Path("templates/admin_cases_map.html")
script = Path("static/js/admin-cases-map.js")
admin_map_scripts = (
    Path("static/js/pages/admin-command-map.js"),
    Path("static/js/admin-risk-map.js"),
    Path("static/js/admin-professionals-map.js"),
)
app = Path("backend/helpchain_backend/src/app.py")


def test_admin_map_uses_local_assets():
    html = template.read_text(encoding="utf-8")
    assert "vendor/leaflet/leaflet.css" in html
    assert "vendor/leaflet/leaflet.js" in html
    assert "js/admin-cases-map.js" in html
    assert "<script>" not in html
    assert "unpkg.com" not in html


def test_admin_map_uses_osm_and_safe_popups():
    js = script.read_text(encoding="utf-8")
    assert re.search(r"tile[.]openstreetmap[.]org", js)
    assert "textContent" in js
    assert "innerHTML" not in js
    assert "bindPopup(popup)" in js


def test_admin_maps_use_the_csp_allowed_osm_tile_host():
    for script in admin_map_scripts:
        js = script.read_text(encoding="utf-8")
        assert "https://tile.openstreetmap.org/{z}/{x}/{y}.png" in js
        assert "{s}.tile.openstreetmap.org" not in js


def test_csp_does_not_allow_unpkg():
    source = app.read_text(encoding="utf-8")
    assert "https://unpkg.com" not in source
    assert "https://*.basemaps.cartocdn.com" in source
