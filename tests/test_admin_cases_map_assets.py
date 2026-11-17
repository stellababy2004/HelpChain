from pathlib import Path

template = Path("templates/admin_cases_map.html")
script = Path("static/js/admin-cases-map.js")
app = Path("backend/helpchain_backend/src/app.py")

def test_admin_map_uses_local_assets():
    html = template.read_text(encoding="utf-8")
    assert "vendor/leaflet/leaflet.css" in html
    assert "vendor/leaflet/leaflet.js" in html
    assert "js/admin-cases-map.js" in html
    assert "<script>" not in html
    assert "unpkg.com" not in html

def test_admin_map_uses_carto_and_safe_popups():
    js = script.read_text(encoding="utf-8")
    assert "tile.openstreetmap.org" in js
    assert "textContent" in js
    assert "innerHTML" not in js
    assert "bindPopup(popup)" in js

def test_csp_does_not_allow_unpkg():
    source = app.read_text(encoding="utf-8")
    assert "https://unpkg.com" not in source
    assert "https://*.basemaps.cartocdn.com" in source
