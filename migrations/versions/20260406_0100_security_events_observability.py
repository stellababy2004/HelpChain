"""extend security events for sprint 2 observability

Revision ID: 20260406_0100
Revises: 20260406_0030
Create Date: 2026-04-06 01:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260406_0100"
down_revision = "20260406_0030"
branch_labels = None
depends_on = None


def _has_table(bind, table_name: str) -> bool:
    try:
        return table_name in inspect(bind).get_table_names()
    except Exception:
        return False


def _has_column(bind, table_name: str, column_name: str) -> bool:
    try:
        cols = inspect(bind).get_columns(table_name)
    except Exception:
        return False
    return any(col.get("name") == column_name for col in cols)


def _has_index(bind, table_name: str, index_name: str) -> bool:
    try:
        indexes = inspect(bind).get_indexes(table_name)
    except Exception:
        return False
    return any(idx.get("name") == index_name for idx in indexes)


def upgrade():
    bind = op.get_bind()
    if not _has_table(bind, "security_events"):
        return

    if not _has_column(bind, "security_events", "ip"):
        op.add_column("security_events", sa.Column("ip", sa.String(length=64), nullable=True))
    if not _has_column(bind, "security_events", "email_hash"):
        op.add_column(
            "security_events",
            sa.Column("email_hash", sa.String(length=64), nullable=True),
        )
    if not _has_column(bind, "security_events", "meta_json"):
        op.add_column("security_events", sa.Column("meta_json", sa.Text(), nullable=True))

    if not _has_index(bind, "security_events", "ix_security_events_ip_created_at"):
        op.create_index(
            "ix_security_events_ip_created_at",
            "security_events",
            ["ip", "created_at"],
            unique=False,
        )
    if not _has_index(bind, "security_events", "ix_security_events_email_hash_created_at"):
        op.create_index(
            "ix_security_events_email_hash_created_at",
            "security_events",
            ["email_hash", "created_at"],
            unique=False,
        )


def downgrade():
    bind = op.get_bind()
    if not _has_table(bind, "security_events"):
        return

    if _has_index(bind, "security_events", "ix_security_events_email_hash_created_at"):
        op.drop_index(
            "ix_security_events_email_hash_created_at",
            table_name="security_events",
        )
    if _has_index(bind, "security_events", "ix_security_events_ip_created_at"):
        op.drop_index("ix_security_events_ip_created_at", table_name="security_events")

    if _has_column(bind, "security_events", "meta_json"):
        op.drop_column("security_events", "meta_json")
    if _has_column(bind, "security_events", "email_hash"):
        op.drop_column("security_events", "email_hash")
    if _has_column(bind, "security_events", "ip"):
        op.drop_column("security_events", "ip")
