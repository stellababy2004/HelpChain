import os

import pytest
from playwright.sync_api import expect, sync_playwright


BASE_URL = os.environ.get("HELPCHAIN_BASE_URL", "http://127.0.0.1:5000")


@pytest.mark.parametrize("route", ["/", "/comment_ca_marche"])
def test_mobile_navigation_real_pointer_click_and_navigation(route):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 393, "height": 852}, locale="fr")
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        page.goto(BASE_URL + route, wait_until="networkidle")

        toggle = page.locator("#hcMobileNavToggle")
        panel = page.locator(".hc-mobile-nav__panel")
        toggle.click(position={"x": 20, "y": 20})
        expect(panel).to_be_visible()
        assert page.locator("#hcMobileNav").evaluate("el => el.classList.contains('is-open')")
        assert panel.bounding_box()["width"] >= 240
        assert panel.bounding_box()["height"] >= 300

        link = panel.locator("a[href]").first
        expect(link).to_be_visible()
        destination = link.get_attribute("href")
        assert destination and destination.startswith("/")
        link.click()
        page.wait_for_load_state("domcontentloaded")
        assert page.url.rstrip("/").endswith(destination.rstrip("/"))

        page.goto(BASE_URL + route, wait_until="networkidle")
        toggle = page.locator("#hcMobileNavToggle")
        toggle.click(position={"x": 20, "y": 20})
        expect(panel).to_be_visible()
        page.locator(".hc-mobile-nav__close").click()
        page.wait_for_function("() => !document.querySelector('#hcMobileNav')?.classList.contains('is-open')")
        toggle.click(position={"x": 20, "y": 20})
        page.wait_for_timeout(300)
        page.keyboard.press("Escape")
        page.wait_for_function("() => !document.querySelector('#hcMobileNav')?.classList.contains('is-open')")
        assert not errors
        browser.close()
