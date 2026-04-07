from flask import render_template


def test_login_template_omits_dead_google_button_and_uses_external_controls(app):
    with app.test_request_context("/login"):
        html = render_template("login.html")

    assert "btn-google" not in html
    assert "js/pages/auth_controls.js" in html
    assert "const passwordToggle" not in html


def test_register_template_omits_dead_google_button_and_uses_external_controls(app):
    with app.test_request_context("/register"):
        html = render_template("register.html")

    assert "btn-google" not in html
    assert "js/pages/auth_controls.js" in html
    assert "Checkbox Selection Functionality" not in html


def test_volunteer_login_page_uses_external_loading_behavior(client):
    response = client.get("/volunteer_login")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-loading-label="' in html
    assert "js/pages/auth_controls.js" in html
    assert "function showLoading()" not in html


def test_volunteer_verify_code_template_uses_real_restart_link(app):
    with app.test_request_context("/volunteer_verify_code"):
        html = render_template("volunteer_verify_code.html", error=None)

    assert 'data-action="resendCode"' not in html
    assert 'href="#"' not in html
    assert "Demander un nouveau lien" in html
    assert "js/pages/auth_controls.js" in html


def test_admin_requests_page_has_no_inline_assign_onclick(
    authenticated_admin_client,
):
    response = authenticated_admin_client.get("/admin/requests")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'onclick="this.disabled=true; this.form.submit(); return false;"' not in html
    assert 'data-action="confirmSubmit"' in html
