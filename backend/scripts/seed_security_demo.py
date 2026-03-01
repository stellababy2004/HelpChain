"""
Seed demo security data for /admin/security dashboard.

Safe by default:
- Refuses to run if env looks like production
- Refuses to run unless DB is SQLite and points to backend/instance/app_clean.db

Usage (PowerShell):
  (.venv) PS C:\\dev\\HelpChain.bg> python backend\\scripts\\seed_security_demo.py
"""

from __future__ import annotations

import argparse
import os
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _prepare_import_path() -> None:
    this_file = Path(__file__).resolve()
    backend_dir = this_file.parents[1]
    repo_root = backend_dir.parent
    for p in (str(repo_root), str(backend_dir)):
        if p not in os.sys.path:
            os.sys.path.insert(0, p)


_prepare_import_path()

from backend.extensions import db
from backend.helpchain_backend.src.app import create_app
from backend.helpchain_backend.src.models.volunteer_interest import VolunteerInterest
from backend.models import (
    AdminAuditEvent,
    AdminLoginAttempt,
    Request,
    Structure,
    User,
    Volunteer,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_production_env() -> bool:
    markers = [
        os.getenv("HC_ENV", ""),
        os.getenv("FLASK_ENV", ""),
        os.getenv("APP_ENV", ""),
        os.getenv("ENV", ""),
    ]
    markers = [m.strip().lower() for m in markers if m]
    return any(m in ("prod", "production") for m in markers)


def _assert_safe_sqlite_db(app) -> None:
    uri = app.config.get("SQLALCHEMY_DATABASE_URI") or ""
    uri_lower = uri.lower()

    if "postgres" in uri_lower or "neon" in uri_lower:
        raise SystemExit(f"REFUSE: DB looks non-sqlite: {uri}")
    if not uri_lower.startswith("sqlite"):
        raise SystemExit(f"REFUSE: DB is not sqlite: {uri}")

    expected_tail = "backend/instance/app_clean.db"
    uri_norm = uri.replace("\\", "/")
    if expected_tail not in uri_norm:
        raise SystemExit(
            "REFUSE: allowed only for backend/instance/app_clean.db\n"
            f"DB URI: {uri}"
        )


def _demo_ua(tag: str) -> str:
    return f"seed-security-demo/{tag}"


def _reset_demo_rows(tag: str) -> dict[str, int]:
    ua = _demo_ua(tag)
    login_deleted = (
        db.session.query(AdminLoginAttempt)
        .filter(AdminLoginAttempt.user_agent == ua)
        .delete(synchronize_session=False)
    )
    audit_deleted = (
        db.session.query(AdminAuditEvent)
        .filter(AdminAuditEvent.user_agent == ua)
        .delete(synchronize_session=False)
    )
    # Backward-compatible cleanup for older seed versions.
    legacy_login_deleted = (
        db.session.query(AdminLoginAttempt)
        .filter(AdminLoginAttempt.user_agent == "seed-security-demo/1.0")
        .delete(synchronize_session=False)
    )
    legacy_audit_deleted = (
        db.session.query(AdminAuditEvent)
        .filter(AdminAuditEvent.user_agent == "seed-security-demo/1.0")
        .delete(synchronize_session=False)
    )
    db.session.commit()
    return {
        "login_attempts_deleted": int((login_deleted or 0) + (legacy_login_deleted or 0)),
        "audit_events_deleted": int((audit_deleted or 0) + (legacy_audit_deleted or 0)),
    }


def _has_demo_rows(tag: str) -> bool:
    ua = _demo_ua(tag)
    has_logins = (
        db.session.query(AdminLoginAttempt.id)
        .filter(AdminLoginAttempt.user_agent == ua)
        .first()
        is not None
    )
    if has_logins:
        return True
    has_audit = (
        db.session.query(AdminAuditEvent.id)
        .filter(AdminAuditEvent.user_agent == ua)
        .first()
        is not None
    )
    return has_audit


def _insert_login_attempts(now: datetime, rng: random.Random, tag: str) -> dict[str, int]:
    events: list[AdminLoginAttempt] = []
    ua = _demo_ua(tag)

    for _ in range(8):
        t = now - timedelta(hours=rng.randint(2, 23), minutes=rng.randint(0, 59))
        events.append(
            AdminLoginAttempt(
                created_at=t,
                username="admin",
                ip="127.0.0.1",
                success=True,
                user_agent=ua,
            )
        )

    for _ in range(12):
        t = now - timedelta(hours=rng.randint(2, 23), minutes=rng.randint(0, 59))
        events.append(
            AdminLoginAttempt(
                created_at=t,
                username="admin",
                ip="45.67.89.10",
                success=False,
                user_agent=ua,
            )
        )

    for _ in range(13):
        t = now - timedelta(hours=rng.randint(3, 23), minutes=rng.randint(0, 59))
        events.append(
            AdminLoginAttempt(
                created_at=t,
                username="ops",
                ip="45.67.89.10",
                success=False,
                user_agent=ua,
            )
        )

    for _ in range(18):
        t = now - timedelta(minutes=rng.randint(1, 59), seconds=rng.randint(0, 59))
        events.append(
            AdminLoginAttempt(
                created_at=t,
                username="admin",
                ip="91.121.13.77",
                success=False,
                user_agent=ua,
            )
        )

    lock_buckets = [
        ("77.88.99.11", "admin"),
        ("77.88.99.12", "admin"),
        ("77.88.99.13", "ops"),
    ]
    for ip, username in lock_buckets:
        for _ in range(5):
            t = now - timedelta(
                hours=1, minutes=rng.randint(0, 4), seconds=rng.randint(0, 59)
            )
            events.append(
                AdminLoginAttempt(
                    created_at=t,
                    username=username,
                    ip=ip,
                    success=False,
                    user_agent=ua,
                )
            )

    db.session.add_all(events)
    db.session.commit()

    return {
        "login_attempts_inserted": len(events),
        "expected_success_24h": 8,
        "expected_failed_24h": len(events) - 8,
    }


def _insert_audit_events(now: datetime, rng: random.Random, tag: str) -> dict[str, int]:
    actions = [
        "request.archive",
        "request.assign_owner",
        "request.unassign_owner",
        "request.unlock",
        "interest.approve",
        "interest.reject",
    ]
    req_ids, interest_ids = _ensure_demo_targets(rng)
    ips = ["127.0.0.1", "45.67.89.10", "91.121.13.77"]
    ua = _demo_ua(tag)

    events: list[AdminAuditEvent] = []
    for _ in range(12):
        action = rng.choice(actions)
        t = now - timedelta(hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
        ip = rng.choice(ips)

        if action.startswith("interest."):
            target_type = "Interest"
            target_id = rng.choice(interest_ids)
            req_id = rng.choice(req_ids)
            if action == "interest.reject":
                payload = {
                    "req_id": req_id,
                    "interest_id": target_id,
                    "old": {"status": "pending"},
                    "new": {"status": "rejected"},
                    "reason": rng.choice(
                        ["not eligible", "duplicate", "insufficient info"]
                    ),
                    "demo_tag": tag,
                }
            else:
                payload = {
                    "req_id": req_id,
                    "interest_id": target_id,
                    "old": {"status": "pending"},
                    "new": {"status": "approved"},
                    "demo_tag": tag,
                }
        else:
            target_type = "Request"
            target_id = rng.choice(req_ids)
            if action == "request.assign_owner":
                payload = {
                    "old": {"owner_id": None},
                    "new": {"owner_id": 42},
                    "demo_tag": tag,
                }
            elif action == "request.unassign_owner":
                payload = {
                    "old": {"owner_id": 42},
                    "new": {"owner_id": None},
                    "demo_tag": tag,
                }
            elif action == "request.unlock":
                payload = {
                    "req_id": target_id,
                    "old": {"locked": True},
                    "new": {"locked": False},
                    "demo_tag": tag,
                }
            elif action == "request.archive":
                payload = {
                    "old": {"archived": False},
                    "new": {"archived": True},
                    "demo_tag": tag,
                }
            else:
                payload = {"demo_tag": tag}

        events.append(
            AdminAuditEvent(
                created_at=t,
                admin_user_id=1,
                admin_username="admin",
                action=action,
                target_type=target_type,
                target_id=int(target_id),
                ip=ip,
                user_agent=ua,
                payload=payload,
            )
        )

    db.session.add_all(events)
    db.session.commit()
    return {"audit_events_inserted": len(events)}


def _ensure_demo_targets(rng: random.Random) -> tuple[list[int], list[int]]:
    structure = db.session.query(Structure).filter_by(slug="default").first()
    if not structure:
        structure = Structure(name="Default", slug="default")
        db.session.add(structure)
        db.session.flush()

    req_ids: list[int] = []
    for idx in range(1, 5):
        title = f"Security demo request {idx}"
        req = db.session.query(Request).filter_by(title=title).first()
        if not req:
            user = db.session.query(User).filter_by(
                email=f"security_demo_user_{idx}@test.local"
            ).first()
            if not user:
                user = User(
                    username=f"security_demo_user_{idx}",
                    email=f"security_demo_user_{idx}@test.local",
                    password_hash="x",
                    role="requester",
                    is_active=True,
                )
                db.session.add(user)
                db.session.flush()
            req = Request(
                title=title,
                user_id=user.id,
                status=rng.choice(["pending", "approved", "in_progress"]),
                category="general",
                structure_id=getattr(structure, "id", None),
            )
            db.session.add(req)
            db.session.flush()
        req_ids.append(int(req.id))

    interest_ids: list[int] = []
    for idx in range(1, 4):
        volunteer = db.session.query(Volunteer).filter_by(
            email=f"security_demo_vol_{idx}@test.local"
        ).first()
        if not volunteer:
            volunteer = Volunteer(
                name=f"Security Demo Volunteer {idx}",
                email=f"security_demo_vol_{idx}@test.local",
                is_active=True,
            )
            db.session.add(volunteer)
            db.session.flush()

        request_id = req_ids[idx - 1]
        interest = db.session.query(VolunteerInterest).filter_by(
            volunteer_id=volunteer.id, request_id=request_id
        ).first()
        if not interest:
            interest = VolunteerInterest(
                volunteer_id=volunteer.id,
                request_id=request_id,
                status="pending",
            )
            db.session.add(interest)
            db.session.flush()
        interest_ids.append(int(interest.id))

    db.session.commit()
    return req_ids, interest_ids


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed demo data for /admin/security")
    parser.add_argument("--tag", default="demo", help="Demo tag namespace (default: demo)")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete only demo-tagged rows for this tag before insert",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Exit without changes if rows for this tag already exist",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    tag = (args.tag or "demo").strip().lower()
    if not tag:
        raise SystemExit("REFUSE: --tag cannot be empty")

    if _is_production_env():
        raise SystemExit("REFUSE: production-like environment detected.")

    app = create_app()
    with app.app_context():
        _assert_safe_sqlite_db(app)
        if args.once and _has_demo_rows(tag):
            print(f"SEED_SECURITY_DEMO: SKIP (--once and rows exist for tag={tag})")
            return

        if args.reset:
            deleted = _reset_demo_rows(tag)
            print(f"SEED_SECURITY_DEMO: RESET tag={tag} -> {deleted}")

        rng = random.Random(42)
        now = _utc_now()
        stats_logins = _insert_login_attempts(now, rng, tag)
        stats_audit = _insert_audit_events(now, rng, tag)

        print("SEED_SECURITY_DEMO: OK")
        print(f"- tag: {tag}")
        print(f"- DB: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
        print(f"- {stats_logins}")
        print(f"- {stats_audit}")
        print("Open: http://127.0.0.1:5000/admin/security")


if __name__ == "__main__":
    main()
