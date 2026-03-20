from __future__ import annotations

import pathlib
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.appy import app
from backend.extensions import db
from backend.models import AdminUser, Request, Structure, User


ADMIN_USERNAME = "visibility_admin"
ADMIN_EMAIL = "visibility_admin@local.test"
ADMIN_PASSWORD = "VisibilityAdmin123!"

OPERATOR_USERNAME = "visibility_operator"
OPERATOR_EMAIL = "visibility_operator@local.test"
OPERATOR_PASSWORD = "VisibilityOperator123!"

REQUESTER_USERNAME = "visibility_requester"
REQUESTER_EMAIL = "visibility_requester@local.test"

STRUCTURE_MAIN_SLUG = "ops-visibility-main"
STRUCTURE_OTHER_SLUG = "ops-visibility-other"


@dataclass(frozen=True)
class VerificationRequest:
    code: str
    title: str
    structure_slug: str
    status: str | None
    owner_username: str | None
    priority: str | None
    age_hours: int
    expected_admin: bool
    expected_operator: bool
    reason: str


REQUEST_SCENARIOS = [
    VerificationRequest(
        code="A",
        title="VERIFY A - null status unassigned",
        structure_slug=STRUCTURE_MAIN_SLUG,
        status=None,
        owner_username=None,
        priority=None,
        age_hours=1,
        expected_admin=True,
        expected_operator=True,
        reason="Main structure, status NULL, unassigned, now treated as operator-actionable.",
    ),
    VerificationRequest(
        code="B",
        title="VERIFY B - new status unassigned",
        structure_slug=STRUCTURE_MAIN_SLUG,
        status="new",
        owner_username=None,
        priority=None,
        age_hours=2,
        expected_admin=True,
        expected_operator=True,
        reason="Main structure, legacy new status, unassigned, operator-actionable.",
    ),
    VerificationRequest(
        code="C",
        title="VERIFY C - closed status",
        structure_slug=STRUCTURE_MAIN_SLUG,
        status="done",
        owner_username=None,
        priority=None,
        age_hours=24,
        expected_admin=True,
        expected_operator=False,
        reason="Closed terminal status remains admin-visible but excluded from operator queue.",
    ),
    VerificationRequest(
        code="D",
        title="VERIFY D - other structure",
        structure_slug=STRUCTURE_OTHER_SLUG,
        status="pending",
        owner_username=None,
        priority=None,
        age_hours=3,
        expected_admin=True,
        expected_operator=False,
        reason="Different structure, visible to global admin but not to structure-bound operator.",
    ),
    VerificationRequest(
        code="E",
        title="VERIFY E - owned normal fresh",
        structure_slug=STRUCTURE_MAIN_SLUG,
        status="pending",
        owner_username=OPERATOR_USERNAME,
        priority="low",
        age_hours=1,
        expected_admin=True,
        expected_operator=False,
        reason="Same structure, but already owned, fresh, non-urgent and non-stale, so excluded from operator queue.",
    ),
]


def _now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _ensure_structure(*, slug: str, name: str) -> Structure:
    row = Structure.query.filter_by(slug=slug).first()
    if row is None:
        row = Structure(name=name, slug=slug, status="active")
        db.session.add(row)
        db.session.flush()
    else:
        row.name = name
        if hasattr(row, "status"):
            row.status = "active"
    return row


def _ensure_admin(*, username: str, email: str, role: str, structure_id: int | None, password: str) -> AdminUser:
    user = AdminUser.query.filter_by(username=username).first()
    if user is None:
        user = AdminUser(
            username=username,
            email=email,
            role=role,
            is_active=True,
            structure_id=structure_id,
        )
        db.session.add(user)
    user.email = email
    user.role = role
    user.is_active = True
    user.structure_id = structure_id
    user.set_password(password)
    db.session.flush()
    return user


def _ensure_requester() -> User:
    user = User.query.filter_by(email=REQUESTER_EMAIL).first()
    if user is None:
        user = User(
            username=REQUESTER_USERNAME,
            email=REQUESTER_EMAIL,
            password_hash="!",
            role="requester",
            is_active=True,
        )
        db.session.add(user)
        db.session.flush()
    return user


def _upsert_request(
    *,
    title: str,
    requester_id: int,
    structure_id: int,
    status: str | None,
    owner_id: int | None,
    priority: str | None,
    age_hours: int,
) -> Request:
    row = Request.query.filter_by(title=title).first()
    created_at = _now_naive() - timedelta(hours=age_hours)
    if row is None:
        row = Request(
            title=title,
            description=title,
            category="general",
            user_id=requester_id,
            structure_id=structure_id,
        )
        db.session.add(row)

    row.description = title
    row.category = "general"
    row.user_id = requester_id
    row.structure_id = structure_id
    row.status = status
    row.owner_id = owner_id
    row.priority = priority
    row.created_at = created_at
    row.updated_at = created_at if owner_id is None else created_at + timedelta(minutes=50)
    row.deleted_at = None
    row.is_archived = False
    row.assigned_volunteer_id = None
    row.completed_at = created_at if status in {"done", "cancelled", "closed", "rejected"} else None
    db.session.flush()
    return row


def seed_visibility_verification() -> list[dict[str, object]]:
    main_structure = _ensure_structure(slug=STRUCTURE_MAIN_SLUG, name="Ops Visibility Main")
    other_structure = _ensure_structure(slug=STRUCTURE_OTHER_SLUG, name="Ops Visibility Other")
    requester = _ensure_requester()

    admin = _ensure_admin(
        username=ADMIN_USERNAME,
        email=ADMIN_EMAIL,
        role="superadmin",
        structure_id=None,
        password=ADMIN_PASSWORD,
    )
    operator = _ensure_admin(
        username=OPERATOR_USERNAME,
        email=OPERATOR_EMAIL,
        role="ops",
        structure_id=main_structure.id,
        password=OPERATOR_PASSWORD,
    )

    structures_by_slug = {
        STRUCTURE_MAIN_SLUG: main_structure,
        STRUCTURE_OTHER_SLUG: other_structure,
    }
    owners_by_username = {
        OPERATOR_USERNAME: operator,
    }

    created: list[dict[str, object]] = []
    for scenario in REQUEST_SCENARIOS:
        structure = structures_by_slug[scenario.structure_slug]
        owner = owners_by_username.get(scenario.owner_username) if scenario.owner_username else None
        request_row = _upsert_request(
            title=scenario.title,
            requester_id=requester.id,
            structure_id=structure.id,
            status=scenario.status,
            owner_id=getattr(owner, "id", None),
            priority=scenario.priority,
            age_hours=scenario.age_hours,
        )
        created.append(
            {
                "code": scenario.code,
                "id": int(request_row.id),
                "title": request_row.title,
                "structure_slug": scenario.structure_slug,
                "status": scenario.status,
                "owner_username": scenario.owner_username,
                "expected_admin": scenario.expected_admin,
                "expected_operator": scenario.expected_operator,
                "reason": scenario.reason,
            }
        )

    db.session.commit()
    return created


def main() -> int:
    with app.app_context():
        rows = seed_visibility_verification()
        print("Seeded operator visibility verification dataset:")
        print(f"- admin: {ADMIN_USERNAME} / {ADMIN_PASSWORD}")
        print(f"- operator: {OPERATOR_USERNAME} / {OPERATOR_PASSWORD}")
        print(f"- main structure: {STRUCTURE_MAIN_SLUG}")
        print(f"- other structure: {STRUCTURE_OTHER_SLUG}")
        for row in rows:
            print(
                f"- {row['code']} #{row['id']} | {row['title']} | "
                f"status={row['status']!r} | structure={row['structure_slug']} | "
                f"owner={row['owner_username'] or 'none'} | "
                f"admin={row['expected_admin']} | operator={row['expected_operator']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
