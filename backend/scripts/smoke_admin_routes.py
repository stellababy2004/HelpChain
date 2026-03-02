"""Quick admin route smoke test.

Usage:
  python backend/scripts/smoke_admin_routes.py

Requires env:
  ADMIN_SEED_USERNAME
  ADMIN_SEED_PASSWORD
"""

from __future__ import annotations

import os

from backend.appy import app
from backend.helpchain_backend.src.models import Request


def _must_env(name: str) -> str:
    v = (os.getenv(name) or "").strip()
    if not v:
        raise SystemExit(f"Missing env: {name}")
    return v


def main() -> int:
    username = _must_env("ADMIN_SEED_USERNAME")
    password = _must_env("ADMIN_SEED_PASSWORD")

    with app.app_context():
        req = Request.query.order_by(Request.id.desc()).first()
        req_id = req.id if req else 1

    with app.test_client() as c:
        # Prefer canonical login.
        c.get("/admin/login")
        resp = c.post(
            "/admin/login",
            data={"username": username, "password": password},
            follow_redirects=False,
        )
        if resp.status_code not in (302, 303):
            resp = c.post(
                "/admin/ops/login",
                data={"username": username, "password": password},
                follow_redirects=False,
            )

        checks = [
            "/admin/requests",
            f"/admin/requests/{req_id}",
            "/admin/audit",
            "/admin/security",
            "/admin/professional-leads",
        ]
        ok_codes = {200, 302, 303, 403}
        failed = False
        for path in checks:
            r = c.get(path, follow_redirects=False)
            print(f"{path}: {r.status_code}")
            if r.status_code not in ok_codes:
                failed = True
        if failed:
            raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
