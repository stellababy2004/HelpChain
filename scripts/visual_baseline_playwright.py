#!/usr/bin/env python3
"""
Lightweight visual baseline capture for public institutional pages.

Usage examples:
  python scripts/visual_baseline_playwright.py --mode baseline
  python scripts/visual_baseline_playwright.py --mode compare
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

from PIL import Image, ImageChops
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
VISUAL_ROOT = ROOT / "tests" / "visual"
BASELINE_ROOT = VISUAL_ROOT / "baseline"
CURRENT_ROOT = VISUAL_ROOT / "current"
DIFF_ROOT = VISUAL_ROOT / "diff"


@dataclass(frozen=True)
class PageSpec:
    slug: str
    path: str
    mobile: bool = False


PAGES: tuple[PageSpec, ...] = (
    PageSpec("homepage", "/", mobile=True),
    PageSpec("comment_ca_marche", "/comment-ca-marche", mobile=True),
    PageSpec("collectivites_associations", "/collectivites-associations", mobile=True),
    PageSpec("cas_usage", "/cas-usage"),
    PageSpec("partenariats", "/partenariats"),
    PageSpec("pilotage_indicateurs", "/pilotage-indicateurs"),
    PageSpec("professionnels", "/professionnels", mobile=True),
    PageSpec("securite", "/securite", mobile=True),
    PageSpec("architecture", "/architecture", mobile=True),
    PageSpec("gouvernance", "/gouvernance", mobile=True),
    PageSpec("faq", "/faq", mobile=True),
    PageSpec("legal", "/mentions-legales", mobile=True),
    PageSpec("privacy", "/confidentialite", mobile=True),
    PageSpec("terms", "/conditions-utilisation", mobile=True),
)


def _ensure_dirs(mode: str) -> None:
    (BASELINE_ROOT / "desktop").mkdir(parents=True, exist_ok=True)
    (BASELINE_ROOT / "mobile").mkdir(parents=True, exist_ok=True)
    if mode in {"current", "compare"}:
        (CURRENT_ROOT / "desktop").mkdir(parents=True, exist_ok=True)
        (CURRENT_ROOT / "mobile").mkdir(parents=True, exist_ok=True)
    if mode == "compare":
        (DIFF_ROOT / "desktop").mkdir(parents=True, exist_ok=True)
        (DIFF_ROOT / "mobile").mkdir(parents=True, exist_ok=True)


def _targets(mode: str, bucket: str) -> Path:
    if mode == "baseline":
        return BASELINE_ROOT / bucket
    return CURRENT_ROOT / bucket


def _set_french_locale(page, base_url: str) -> None:
    try:
        page.goto(urljoin(base_url, "/set-lang/fr"), wait_until="domcontentloaded", timeout=20000)
    except Exception:
        # Keep run resilient even if locale switch route is unavailable.
        return


def _stabilize_page(page) -> None:
    # Keep screenshots deterministic: disable transitions/animations and allow layout settling.
    page.add_style_tag(
        content="""
        *,
        *::before,
        *::after {
          animation-delay: 0s !important;
          animation-duration: 0s !important;
          transition-duration: 0s !important;
          scroll-behavior: auto !important;
          caret-color: transparent !important;
        }
        """
    )
    page.wait_for_timeout(350)


def _capture_pages(
    base_url: str,
    mode: str,
    viewport: dict,
    bucket: str,
    pages: Iterable[PageSpec],
) -> list[str]:
    captured: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport=viewport,
            locale="fr-FR",
            timezone_id="Europe/Paris",
            color_scheme="light",
            extra_http_headers={"Accept-Language": "fr-FR,fr;q=0.9"},
        )
        page = context.new_page()
        _set_french_locale(page, base_url)
        for spec in pages:
            url = urljoin(base_url, spec.path)
            out_file = _targets(mode, bucket) / f"{spec.slug}.png"
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                _stabilize_page(page)
                page.screenshot(path=str(out_file), full_page=True)
                captured.append(spec.slug)
                print(f"[{bucket}] captured {spec.slug} -> {out_file}")
            except (PlaywrightTimeoutError, PlaywrightError) as exc:
                print(f"[{bucket}] FAILED {spec.slug} ({url}): {exc}")
        context.close()
        browser.close()
    return captured


def _compare_bucket(bucket: str, pages: Iterable[PageSpec]) -> dict:
    results = {}
    for spec in pages:
        baseline_file = BASELINE_ROOT / bucket / f"{spec.slug}.png"
        current_file = CURRENT_ROOT / bucket / f"{spec.slug}.png"
        diff_file = DIFF_ROOT / bucket / f"{spec.slug}.png"
        if not baseline_file.exists() or not current_file.exists():
            results[spec.slug] = {"status": "missing"}
            continue
        with Image.open(baseline_file).convert("RGBA") as img_a, Image.open(current_file).convert(
            "RGBA"
        ) as img_b:
            if img_a.size != img_b.size:
                results[spec.slug] = {
                    "status": "size_mismatch",
                    "baseline_size": img_a.size,
                    "current_size": img_b.size,
                }
                continue
            diff = ImageChops.difference(img_a, img_b)
            bbox = diff.getbbox()
            if not bbox:
                results[spec.slug] = {"status": "ok", "changed_pixels": 0}
                if diff_file.exists():
                    diff_file.unlink()
                continue
            changed = sum(1 for px in diff.getdata() if px != (0, 0, 0, 0))
            diff.save(diff_file)
            results[spec.slug] = {
                "status": "changed",
                "changed_pixels": changed,
                "diff": str(diff_file.relative_to(ROOT)),
            }
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture and compare visual baselines for public pages.")
    parser.add_argument("--base-url", default="http://127.0.0.1:5000", help="Local app URL")
    parser.add_argument(
        "--mode",
        choices=("baseline", "current", "compare"),
        default="baseline",
        help="baseline=create/update baseline, current=capture new run, compare=capture + compare against baseline",
    )
    args = parser.parse_args()

    _ensure_dirs(args.mode)

    desktop_pages = PAGES
    mobile_pages = tuple(p for p in PAGES if p.mobile)

    _capture_pages(
        base_url=args.base_url,
        mode=args.mode,
        viewport={"width": 1440, "height": 2200},
        bucket="desktop",
        pages=desktop_pages,
    )
    _capture_pages(
        base_url=args.base_url,
        mode=args.mode,
        viewport={"width": 390, "height": 844},
        bucket="mobile",
        pages=mobile_pages,
    )

    if args.mode == "compare":
        report = {
            "desktop": _compare_bucket("desktop", desktop_pages),
            "mobile": _compare_bucket("mobile", mobile_pages),
        }
        report_path = VISUAL_ROOT / "last-compare-report.json"
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Compare report written to {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
