"""Browser diagnostics for the three canonical admin map pages."""

import json
import os
import base64
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright


BASE_URL = os.environ.get("HELPCHAIN_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
ADMIN_USERNAME = os.environ.get("HC_QA_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("HC_QA_ADMIN_PASSWORD", "Change-me-local-admin-1")
REPORT_DIR = Path(os.environ.get("HC_QA_REPORT_DIR", "reports/visual-audit/admin-maps"))
MOCK_TILES = os.environ.get("HC_QA_MOCK_TILES", "false").lower() == "true"
MAPS = (
    ("professionals", "/admin/professionals-map", "#professionalsMap"),
    ("risk", "/admin/risk-map", "#riskMapCanvas"),
    ("command", "/admin/command-map", "#commandMapCanvas"),
)


def _diagnostic(page, name, route, console_errors, failed_requests, csp_violations, failure=""):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    screenshot = REPORT_DIR / f"{name}-failure.png"
    page.screenshot(path=str(screenshot), full_page=True)
    report = {
        "test": "test_admin_map_rendering",
        "route": route,
        "url": page.url,
        "console_errors": console_errors,
        "failed_requests": failed_requests,
        "csp_violations": csp_violations,
        "failure": failure,
        "screenshot": str(screenshot).replace("\\", "/"),
    }
    (REPORT_DIR / f"{name}-failure.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )


@pytest.mark.browser
def test_admin_map_rendering():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1366, "height": 900}, locale="fr", service_workers="block"
        )
        page = context.new_page()
        if MOCK_TILES:
            tile_png = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
            )

            def route_tile(route):
                if "tile.openstreetmap.org" in route.request.url:
                    route.fulfill(status=200, content_type="image/png", body=tile_png)
                else:
                    route.continue_()

            page.route("**/*", route_tile)
        console_errors = []
        failed_requests = []
        csp_violations = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("requestfailed", lambda request: failed_requests.append(request.url))
        page.on(
            "response",
            lambda response: failed_requests.append(f"HTTP {response.status}: {response.url}")
            if response.status >= 400
            else None,
        )
        page.on(
            "console",
            lambda msg: csp_violations.append(msg.text)
            if "content security policy" in msg.text.lower()
            else None,
        )

        login = page.goto(f"{BASE_URL}/admin/login", wait_until="domcontentloaded")
        assert login and login.ok, f"Admin login returned HTTP {login.status if login else 'no response'}"
        page.locator("#username").fill(ADMIN_USERNAME)
        page.locator("#password").fill(ADMIN_PASSWORD)
        page.locator("form.hc-auth-form button[type='submit']").click()
        page.wait_for_load_state("domcontentloaded")
        if "/admin/login" in page.url:
            _diagnostic(page, "login", "/admin/login", console_errors, failed_requests, csp_violations)
            raise AssertionError("Local QA admin login did not succeed")

        map_failures = []
        for name, route, selector in MAPS:
            console_errors.clear()
            failed_requests.clear()
            csp_violations.clear()
            response = page.goto(f"{BASE_URL}{route}", wait_until="networkidle")
            try:
                assert response and response.ok, f"{route} returned HTTP {response.status if response else 'no response'}"
                container = page.locator(selector)
                expect(container).to_be_visible()
                box = container.bounding_box()
                assert box and box["width"] > 200 and box["height"] > 200, f"{route} map container has invalid size: {box}"
                assert page.locator(f"{selector} .leaflet-tile-loaded").count() > 0, f"{route} has no loaded map tiles"
                markers = page.locator(f"{selector} .leaflet-marker-icon, {selector} .leaflet-marker-pane > *").count()
                if route == "/admin/risk-map" and markers == 0:
                    empty_state = page.locator("#riskMapEmptyState")
                    assert empty_state.is_visible() or empty_state.evaluate(
                        "el => el.classList.contains('is-visible')"
                    ), f"{route} has neither markers nor a visible empty state"
                else:
                    assert markers > 0, f"{route} has no markers"
                assert not console_errors, f"{route} browser errors: {console_errors}"
                assert not csp_violations, f"{route} CSP violations: {csp_violations}"
            except Exception as exc:
                _diagnostic(page, name, route, console_errors, failed_requests, csp_violations, str(exc))
                map_failures.append(route)
        assert not map_failures, f"Admin map browser checks failed: {', '.join(map_failures)}"
        browser.close()
