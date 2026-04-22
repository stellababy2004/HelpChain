"""add organization access requests

Revision ID: 20260422_1430
Revises: a63fb6ad50da
Create Date: 2026-04-22 14:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260422_1430"
down_revision = "a63fb6ad50da"
branch_labels = None
depends_on = None


def _has_table(bind, table_name: str) -> bool:
    try:
        return table_name in inspect(bind).get_table_names()
    except Exception:
        return False


def _has_index(bind, table_name: str, index_name: str) -> bool:
    try:
        return any(
            idx.get("name") == index_name
            for idx in inspect(bind).get_indexes(table_name)
        )
    except Exception:
        return False


def upgrade():
    bind = op.get_bind()
    table_name = "organization_access_requests"

    if not _has_table(bind, table_name):
        op.create_table(
            table_name,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("organization_name", sa.String(length=255), nullable=False),
            sa.Column("contact_name", sa.String(length=160), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("phone", sa.String(length=50), nullable=True),
            sa.Column("city", sa.String(length=120), nullable=True),
            sa.Column("org_type", sa.String(length=80), nullable=True),
            sa.Column("estimated_users", sa.Integer(), nullable=True),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=30), server_default="new", nullable=False),
            sa.Column("reviewed_by_admin_id", sa.Integer(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("internal_notes", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["reviewed_by_admin_id"], ["admin_users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    for index_name, columns in (
        ("ix_organization_access_requests_email", ["email"]),
        ("ix_organization_access_requests_city", ["city"]),
        ("ix_organization_access_requests_org_type", ["org_type"]),
        ("ix_organization_access_requests_status", ["status"]),
        ("ix_organization_access_requests_reviewed_by_admin_id", ["reviewed_by_admin_id"]),
        ("ix_organization_access_requests_created_at", ["created_at"]),
        ("ix_org_access_requests_status_created_at", ["status", "created_at"]),
    ):
        if not _has_index(bind, table_name, index_name):
            op.create_index(index_name, table_name, columns, unique=False)


def downgrade():
    bind = op.get_bind()
    table_name = "organization_access_requests"
    if _has_table(bind, table_name):
        op.drop_table(table_name)
