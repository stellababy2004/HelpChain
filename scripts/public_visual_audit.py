"""Playwright visual and interaction audit for the public HelpChain site.

This tool is intentionally read-only: it performs GET navigation and safe UI
interactions only. It never submits forms, changes the database, or calls
production services.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from urllib.request import Request, urlopen
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://127.0.0.1:5000"
REPORT_ROOT = ROOT / "reports" / "visual-audit"
LOCALES = ("fr", "bg", "en")
VIEWPORTS = {
    "desktop": (1440, 900),
    "tablet": (768, 1024),
    "mobile": (390, 844),
}
PUBLIC_ROUTES = (
    "/",
    "/about",
    "/gouvernance",
    "/comment_ca_marche",
    "/collectivites_associations",
    "/cas_usage",
    "/deploiement",
    "/simulation-operationnelle",
    "/offre",
    "/tarifs",
    "/pilotage_indicateurs",
    "/partenariats",
    "/pourquoi_helpchain",
    "/vision_europeenne",
    "/securite",
    "/architecture",
    "/pour-les-structures",
    "/professionnels",
    "/faq",
    "/contact",
    "/confidentialite",
    "/conditions_utilisation",
    "/legal",
    "/success_stories",
)
CORRUPTION_RE = re.compile(r"\?{3,}|�|(?:Ã.|Â.|Ð.|Ñ.)")
GETTEXT_KEY_RE = re.compile(r"(?:\{\{|\{%|msgid|gettext\()")
RECOMMENDATIONS = {
    "console": "Inspect the browser console error and the originating script.",
    "encoding": "Inspect the rendered source and the UTF-8 template/catalog entry.",
    "translation": "Check the locale catalog and the gettext wrapper for the rendered text.",
    "content": "Ensure the public page has a visible primary heading.",
    "cta": "Check that the page exposes its primary links or calls to action.",
    "resource": "Check the referenced local asset path and server response.",
    "image": "Check the image URL and that the asset is served successfully.",
    "layout": "Inspect the element causing horizontal overflow at this viewport.",
    "viewport": "Inspect the positioned element at this viewport; confirm intentional behavior.",
    "mobile-menu": "Inspect the mobile navigation toggle and its open/close state.",
    "lightbox": "Inspect the lightbox trigger, dialog sizing, and close interactions.",
}


@dataclass
class Finding:
    severity: str
    category: str
    message: str
    screenshot: str = ""


@dataclass
class Check:
    route: str
    locale: str
    viewport: str
    width: int
    height: int
    screenshot: str
    status: str = "PASS"
    findings: list[Finding] = field(default_factory=list)

    def add(self, severity: str, category: str, message: str, screenshot: str = "") -> None:
        self.findings.append(Finding(severity, category, message, screenshot))
        if severity == "FAIL":
            self.status = "FAIL"
        elif severity == "WARNING" and self.status == "PASS":
            self.status = "WARNING"


def safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip("/") or "home")


def visible_text(page) -> str:
    return page.locator("body").inner_text(timeout=5000)


def check_layout(check: Check, page) -> None:
    metrics = page.evaluate(
        """() => {
          const vw = window.innerWidth, vh = window.innerHeight;
          const visible = el => {
            const s = getComputedStyle(el), r = el.getBoundingClientRect();
            return s.display !== 'none' && s.visibility !== 'hidden' &&
              r.width > 0 && r.height > 0;
          };
          const outside = [];
          document.querySelectorAll('body *').forEach(el => {
            if (!visible(el)) return;
            const r = el.getBoundingClientRect();
            const position = getComputedStyle(el).position;
            const cls = String(el.className);
            // Vertical content below the fold is normal page behavior. Only
            // report genuine horizontal escape or fixed/absolute elements
            // positioned above the viewport. Ignore a closed mobile panel.
            if (el.closest('.hc-mobile-nav__panel') && !document.body.classList.contains('hc-mobile-nav-open')) return;
            if (r.right > vw + 2 || r.left < -2 ||
                ((position === 'fixed' || position === 'absolute') && r.top < -vh * 2))
              outside.push({tag: el.tagName, id: el.id, cls: String(el.className).slice(0, 80),
                left: Math.round(r.left), top: Math.round(r.top), right: Math.round(r.right), bottom: Math.round(r.bottom)});
          });
          return {scrollWidth: document.documentElement.scrollWidth, viewport: vw,
            outside: outside.slice(0, 12)};
        }"""
    )
    if metrics["scrollWidth"] > metrics["viewport"] + 2:
        check.add("FAIL", "layout", f"Horizontal overflow: scrollWidth={metrics['scrollWidth']} viewport={metrics['viewport']}")
    if metrics["outside"]:
        check.add("WARNING", "viewport", f"Visible elements extend beyond the viewport: {metrics['outside'][:3]}")


def check_content(check: Check, page) -> None:
    text = visible_text(page)
    if CORRUPTION_RE.search(text):
        check.add("FAIL", "encoding", "Visible text contains replacement/corrupted characters.")
    if GETTEXT_KEY_RE.search(text):
        check.add("WARNING", "translation", "Rendered text contains a possible template/gettext marker.")
    if not page.locator("main h1:visible, main h2:visible").count():
        check.add("FAIL", "content", "No visible primary heading found.")
    if not page.locator("a[href], button").count():
        check.add("WARNING", "cta", "No links or buttons found on the page.")


def check_resources(check: Check, page, failed_requests: list[str]) -> None:
    for url in failed_requests:
        if "/favicon" not in url and not url.endswith("/events") and "/api/website" not in url:
            if url.lower().split("?", 1)[0].endswith(".woff2"):
                try:
                    request = Request(url, method="GET", headers={"Range": "bytes=0-0"})
                    with urlopen(request, timeout=3) as response:
                        if 200 <= response.status < 400:
                            continue
                except Exception:
                    pass
            check.add("FAIL", "resource", f"Resource failed to load: {url}")
    for image in page.locator("img").all():
        try:
            if not image.get_attribute("src") and not image.get_attribute("data-src"):
                continue
            if not image.evaluate("img => img.complete && img.naturalWidth > 0"):
                check.add("FAIL", "image", f"Image failed to load: {image.get_attribute('src')}")
        except PlaywrightError:
            check.add("WARNING", "image", "Could not inspect one image element.")


def check_mobile_menu(check: Check, page) -> None:
    toggle = page.locator("#hcMobileNavToggle")
    if not toggle.count():
        return
    try:
        toggle.click()
        menu = page.locator("#hcMobileNav, .hc-mobile-nav").first
        page.wait_for_function(
            """() => document.getElementById('hcMobileNavToggle')?.getAttribute('aria-expanded') === 'true'
                || document.getElementById('hcMobileNav')?.classList.contains('is-open')""",
            timeout=2000,
        )
        opened = menu.is_visible() or toggle.get_attribute("aria-expanded") == "true" or page.locator("body.hc-mobile-nav-open").count() > 0
        if not opened:
            check.add("WARNING", "mobile-menu", "Mobile navigation did not expose a detectable open state; review manually.")
        page.keyboard.press("Escape")
        try:
            page.wait_for_function(
                """() => document.getElementById('hcMobileNavToggle')?.getAttribute('aria-expanded') !== 'true'
                    && !document.getElementById('hcMobileNav')?.classList.contains('is-open')""",
                timeout=2000,
            )
        except PlaywrightError:
            pass
        if menu.is_visible() and toggle.get_attribute("aria-expanded") == "true":
            check.add("WARNING", "mobile-menu", "Escape did not close mobile navigation.")
    except PlaywrightError as exc:
        check.add("WARNING", "mobile-menu", f"Mobile menu interaction could not be completed: {exc}")


def check_lightbox(check: Check, page, screenshot_dir: Path) -> None:
    source = page.locator("[data-hc-lightbox], [data-hc-lightbox-open]").first
    if not source.count():
        return
    try:
        source.click(timeout=5000)
        dialog = page.locator("dialog[data-hc-universal-lightbox], .hc-universal-lightbox").first
        if not dialog.is_visible():
            check.add("FAIL", "lightbox", "Lightbox did not open.")
            return
        image = dialog.locator("img").first
        if not image.is_visible():
            check.add("FAIL", "lightbox", "Lightbox image is not visible.")
        else:
            box = image.bounding_box()
            if not box or box["width"] < 80 or box["height"] < 80:
                check.add("WARNING", "lightbox", "Lightbox image is unusually small; review manually.")
            if page.viewport_size["width"] <= 768 and dialog.locator(".hc-universal-lightbox__body").evaluate("el => el.scrollHeight > el.clientHeight"):
                check.add("WARNING", "lightbox", "Mobile lightbox requires internal scrolling; review image framing.")
        dialog.screenshot(path=str(screenshot_dir / "lightbox.png"))
        page.keyboard.press("Escape")
        if dialog.is_visible():
            check.add("FAIL", "lightbox", "Escape did not close the lightbox.")
    except PlaywrightError as exc:
        check.add("WARNING", "lightbox", f"Lightbox interaction could not be completed: {exc}")


def render_report(checks: list[Check], output: Path, base_url: str, blocked: str = "") -> None:
    counts = {key: sum(c.status == key for c in checks) for key in ("PASS", "FAIL", "WARNING")}
    rows = []
    for check in checks:
        issues = "<br>".join(
            f"<b>{html.escape(f.severity)}</b> [{html.escape(f.category)}] {html.escape(f.message)}"
            f"<br><i>Recommended: {html.escape(RECOMMENDATIONS.get(f.category, 'Review the reported element manually.'))}</i>"
            + (f" <a href='{html.escape(f.screenshot)}'>screenshot</a>" if f.screenshot else "")
            for f in check.findings
        ) or "None"
        shot = f"<a href='{html.escape(check.screenshot)}'>view</a>" if check.screenshot else "—"
        rows.append("<tr>" + "".join(f"<td>{x}</td>" for x in (
            html.escape(check.route), check.locale, check.viewport, check.status, issues, shot
        )) + "</tr>")
    note = f"<p class='blocked'>{html.escape(blocked)}</p>" if blocked else ""
    document = f"""<!doctype html><meta charset='utf-8'><title>HelpChain visual audit</title>
    <style>body{{font:14px system-ui;margin:24px;color:#14284f}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #d6e2ef;padding:8px;vertical-align:top}}.PASS{{color:#087443}}.FAIL{{color:#b42318}}.WARNING,.blocked{{color:#9a6700}}</style>
    <h1>HelpChain public visual audit</h1><p>Base URL: {html.escape(base_url)}</p>{note}
    <p>Checks: {len(checks)} — PASS: {counts['PASS']} — FAIL: {counts['FAIL']} — WARNING: {counts['WARNING']}</p>
    <table><thead><tr><th>Route</th><th>Locale</th><th>Viewport</th><th>Status</th><th>Findings and recommended correction</th><th>Screenshot</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"""
    output.write_text(document, encoding="utf-8")
    (output.with_suffix(".json")).write_text(json.dumps({"base_url": base_url, "counts": counts}, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--output-dir", type=Path, default=REPORT_ROOT)
    parser.add_argument("--route", action="append", choices=PUBLIC_ROUTES, help="Limit the audit to one or more public routes.")
    parser.add_argument("--locale", action="append", choices=LOCALES, help="Limit the audit to one or more locales.")
    parser.add_argument("--viewport", action="append", choices=tuple(VIEWPORTS), help="Limit the audit to one or more viewport names.")
    parser.add_argument("--case", action="append", metavar="ROUTE,LOCALE,VIEWPORT", help="Run an exact targeted case; may be repeated.")
    args = parser.parse_args()
    if args.case:
        cases = []
        for value in args.case:
            parts = value.split(",")
            if len(parts) != 3 or parts[0] not in PUBLIC_ROUTES or parts[1] not in LOCALES or parts[2] not in VIEWPORTS:
                parser.error(f"Invalid --case {value!r}; expected ROUTE,LOCALE,VIEWPORT")
            cases.append((parts[0], parts[1], parts[2]))
    else:
        routes = tuple(args.route or PUBLIC_ROUTES)
        locales = tuple(args.locale or LOCALES)
        viewports = tuple(args.viewport or VIEWPORTS)
        cases = [(route, locale, viewport_name) for route in routes for locale in locales for viewport_name in viewports]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    screenshot_root = args.output_dir / run_id
    screenshot_root.mkdir(parents=True, exist_ok=True)
    checks: list[Check] = []
    blocked = ""
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for route, locale, viewport_name in cases:
                        width, height = VIEWPORTS[viewport_name]
                        check = Check(route, locale, viewport_name, width, height, "")
                        shot_dir = screenshot_root / safe_name(route) / locale / viewport_name
                        shot_dir.mkdir(parents=True, exist_ok=True)
                        check.screenshot = str(shot_dir.relative_to(args.output_dir)).replace("\\", "/") + "/page.png"
                        context = browser.new_context(viewport={"width": width, "height": height}, locale=locale, ignore_https_errors=True)
                        page = context.new_page()
                        errors: list[str] = []
                        failed_requests: list[str] = []
                        page.on("pageerror", lambda exc: errors.append(str(exc)))
                        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
                        page.on("requestfailed", lambda req: failed_requests.append(req.url))
                        try:
                            if locale != "fr":
                                page.goto(f"{args.base_url}/set-lang/{locale}?next={route}", wait_until="domcontentloaded", timeout=30000)
                            response = page.goto(f"{args.base_url}{route}", wait_until="domcontentloaded", timeout=30000)
                            page.wait_for_timeout(250)
                            if not response or response.status >= 400:
                                check.add("FAIL", "http", f"HTTP status: {response.status if response else 'no response'}")
                            check_content(check, page)
                            check_layout(check, page)
                            check_resources(check, page, failed_requests)
                            if errors:
                                check.add("FAIL", "javascript", "JavaScript errors: " + " | ".join(errors[:5]))
                            if viewport_name == "mobile":
                                check_mobile_menu(check, page)
                            check_lightbox(check, page, shot_dir)
                            page.screenshot(path=str(shot_dir / "page.png"), full_page=True)
                        except PlaywrightError as exc:
                            check.add("FAIL", "navigation", str(exc))
                        finally:
                            context.close()
                        checks.append(check)
            browser.close()
    except Exception as exc:
        blocked = f"Browser audit could not start: {type(exc).__name__}: {exc}"
    report = args.output_dir / f"visual-audit-{run_id}.html"
    render_report(checks, report, args.base_url, blocked)
    print(f"REPORT={report}")
    print(f"CHECKS={len(checks)}")
    print(f"PASS={sum(c.status == 'PASS' for c in checks)} FAIL={sum(c.status == 'FAIL' for c in checks)} WARNING={sum(c.status == 'WARNING' for c in checks)}")
    if blocked:
        print(f"BLOCKED={blocked}")
    if blocked:
        return 3
    return 0 if not any(c.status == "FAIL" for c in checks) else 2


if __name__ == "__main__":
    raise SystemExit(main())
