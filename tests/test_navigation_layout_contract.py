from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESIGN_SYSTEM = (ROOT / "static/css/design-system.css").read_text(encoding="utf-8")


def test_fixed_top_navbars_keep_fixed_position():
    assert ".navbar.fixed-top" in DESIGN_SYSTEM
    assert ".navbar.fixed-top {" in DESIGN_SYSTEM
    assert "position: fixed;" in DESIGN_SYSTEM.split(".navbar.fixed-top {", 1)[1].split("}", 1)[0]


def test_home_layout_does_not_add_second_nav_offset():
    rule = DESIGN_SYSTEM.rsplit("body.hc-page-home {", 1)[1].split("}", 1)[0]
    assert "padding-top: 0;" in rule


def test_admin_and_ops_workspace_reserve_content_space():
    selector = (
        "body.hc-page-admin .hc-admin-workspace__content,\n"
        "body[data-hc-page^=\"/ops\"] .hc-admin-workspace__content"
    )
    assert selector in DESIGN_SYSTEM
    assert "padding-top: 24px;" in DESIGN_SYSTEM


def test_shared_layouts_cover_public_admin_and_ops_surfaces():
    base = (ROOT / "templates/base.html").read_text(encoding="utf-8")
    workspace = (ROOT / "templates/layouts/admin_workspace.html").read_text(encoding="utf-8")
    assert 'class="navbar hc-navbar hc-nav' in base
    assert 'class="hc-admin-shellbar"' in workspace
    assert 'class="hc-admin-workspace__content"' in workspace


def test_fixed_nav_templates_keep_explicit_bootstrap_class():
    for name in ("admin.html", "dashboard.html", "achievements.html", "profile.html"):
        template = (ROOT / "templates" / name).read_text(encoding="utf-8")
        assert "navbar" in template
        assert "fixed-top" in template


def test_global_visual_refinement_contract_uses_requested_palette_and_motion():
    assert "--hc-bg: #f6f9fc;" in DESIGN_SYSTEM
    assert "--hc-surface-soft: #eaf1f8;" in DESIGN_SYSTEM
    assert "--hc-border: #d4e0ec;" in DESIGN_SYSTEM
    assert "--hc-text: #243b53;" in DESIGN_SYSTEM
    assert "--hc-accent: #1d4e89;" in DESIGN_SYSTEM
    assert "--hc-accent-hover: #163d6b;" in DESIGN_SYSTEM
    assert "--hc-focus: #3273c5;" in DESIGN_SYSTEM
    assert "background-color 180ms ease" in DESIGN_SYSTEM
    assert "@media (prefers-reduced-motion: reduce)" in DESIGN_SYSTEM
