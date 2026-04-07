"""harden magic link token lifecycle and UTC storage

Revision ID: 20260406_0030
Revises: 20260406_0015
Create Date: 2026-04-06 00:30:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260406_0030"
down_revision = "20260406_0015"
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


def _upgrade_datetime_column(bind, table_name: str, column_name: str) -> None:
    if bind.dialect.name == "postgresql":
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            postgresql_using=f"{column_name} AT TIME ZONE 'UTC'",
        )


def _downgrade_datetime_column(bind, table_name: str, column_name: str) -> None:
    if bind.dialect.name == "postgresql":
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            postgresql_using=f"{column_name} AT TIME ZONE 'UTC'",
        )


def upgrade():
    bind = op.get_bind()

    if _has_table(bind, "magic_link_tokens"):
        if not _has_column(bind, "magic_link_tokens", "invalidated_at"):
            op.add_column(
                "magic_link_tokens",
                sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
            )
        if not _has_column(bind, "magic_link_tokens", "invalidated_reason"):
            op.add_column(
                "magic_link_tokens",
                sa.Column("invalidated_reason", sa.String(length=64), nullable=True),
            )
        if not _has_index(bind, "magic_link_tokens", "ix_magic_link_tokens_invalidated_at"):
            op.create_index(
                "ix_magic_link_tokens_invalidated_at",
                "magic_link_tokens",
                ["invalidated_at"],
                unique=False,
            )

        for column_name in ("created_at", "expires_at", "used_at"):
            if _has_column(bind, "magic_link_tokens", column_name):
                _upgrade_datetime_column(bind, "magic_link_tokens", column_name)

    if _has_table(bind, "requests") and _has_column(
        bind, "requests", "requester_token_created_at"
    ):
        _upgrade_datetime_column(bind, "requests", "requester_token_created_at")


def downgrade():
    bind = op.get_bind()

    if _has_table(bind, "requests") and _has_column(
        bind, "requests", "requester_token_created_at"
    ):
        _downgrade_datetime_column(bind, "requests", "requester_token_created_at")

    if not _has_table(bind, "magic_link_tokens"):
        return

    for column_name in ("used_at", "expires_at", "created_at"):
        if _has_column(bind, "magic_link_tokens", column_name):
            _downgrade_datetime_column(bind, "magic_link_tokens", column_name)

    if _has_index(bind, "magic_link_tokens", "ix_magic_link_tokens_invalidated_at"):
        op.drop_index("ix_magic_link_tokens_invalidated_at", table_name="magic_link_tokens")
    if _has_column(bind, "magic_link_tokens", "invalidated_reason"):
        op.drop_column("magic_link_tokens", "invalidated_reason")
    if _has_column(bind, "magic_link_tokens", "invalidated_at"):
        op.drop_column("magic_link_tokens", "invalidated_at")
