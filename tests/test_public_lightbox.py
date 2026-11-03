from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_shared_lightbox_uses_available_space_without_distorting_images():
    css = (ROOT / "static/css/components/hc-universal-lightbox.css").read_text(encoding="utf-8")
    assert "height: 100%;" in css
    assert "width: 100%;" in css
    assert "object-fit: contain;" in css
    assert "overflow: hidden;" in css
    assert "height: calc(94vh - 42px);" in css


def test_all_public_lightbox_pages_use_shared_component_and_close_behaviour():
    js = (ROOT / "static/js/hc-universal-lightbox.js").read_text(encoding="utf-8")
    assert "dialog.addEventListener(\"click\"" in js
    assert "event.target === dialog" in js
    assert "event.key === \"Escape\"" in js
    assert "closeButton.addEventListener(\"click\", close)" in js

    pages = (
        "comment_ca_marche.html",
        "deploiement.html",
        "home_new_slim.html",
        "pilotage_indicateurs.html",
        "securite.html",
    )
    for page in pages:
        html = (ROOT / "templates" / page).read_text(encoding="utf-8")
        assert "data-hc-lightbox" in html, page
