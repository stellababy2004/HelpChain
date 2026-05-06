"""add integration connectors

Revision ID: 20260506_2100
Revises: 20260506_1900
Create Date: 2026-05-06 21:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260506_2100"
down_revision = "20260506_1900"
branch_labels = None
depends_on = None


def _has_table(bind, table_name: str) -> bool:
    try:
        return table_name in inspect(bind).get_table_names()
    except Exception:
        return False


def _has_column(bind, table_name: str, column_name: str) -> bool:
    try:
        columns = inspect(bind).get_columns(table_name)
    except Exception:
        return False
    return any(str(col.get("name")) == column_name for col in columns)


def _has_index(bind, table_name: str, index_name: str) -> bool:
    try:
        indexes = inspect(bind).get_indexes(table_name)
    except Exception:
        return False
    return any(str(idx.get("name")) == index_name for idx in indexes)


def upgrade():
    bind = op.get_bind()

    if not _has_table(bind, "integration_connectors"):
        op.create_table(
            "integration_connectors",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("structure_id", sa.Integer(), nullable=True),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("source_slug", sa.String(length=120), nullable=False),
            sa.Column("api_key_hash", sa.String(length=255), nullable=False),
            sa.Column(
                "status",
                sa.String(length=32),
                nullable=False,
                server_default="active",
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("allowed_fields_json", sa.Text(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["structure_id"], ["structures.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _has_index(bind, "integration_connectors", op.f("ix_integration_connectors_structure_id")):
        op.create_index(
            op.f("ix_integration_connectors_structure_id"),
            "integration_connectors",
            ["structure_id"],
            unique=False,
        )
    if not _has_index(bind, "integration_connectors", op.f("ix_integration_connectors_source_slug")):
        op.create_index(
            op.f("ix_integration_connectors_source_slug"),
            "integration_connectors",
            ["source_slug"],
            unique=True,
        )
    if not _has_index(bind, "integration_connectors", op.f("ix_integration_connectors_status")):
        op.create_index(
            op.f("ix_integration_connectors_status"),
            "integration_connectors",
            ["status"],
            unique=False,
        )
    if not _has_index(bind, "integration_connectors", op.f("ix_integration_connectors_created_at")):
        op.create_index(
            op.f("ix_integration_connectors_created_at"),
            "integration_connectors",
            ["created_at"],
            unique=False,
        )
    if not _has_index(bind, "integration_connectors", op.f("ix_integration_connectors_last_seen_at")):
        op.create_index(
            op.f("ix_integration_connectors_last_seen_at"),
            "integration_connectors",
            ["last_seen_at"],
            unique=False,
        )
    if not _has_index(bind, "integration_connectors", op.f("ix_integration_connectors_last_event_at")):
        op.create_index(
            op.f("ix_integration_connectors_last_event_at"),
            "integration_connectors",
            ["last_event_at"],
            unique=False,
        )

    if _has_table(bind, "relay_events") and not _has_column(bind, "relay_events", "connector_id"):
        with op.batch_alter_table("relay_events", schema=None) as batch_op:
            batch_op.add_column(sa.Column("connector_id", sa.Integer(), nullable=True))
            batch_op.create_index(op.f("ix_relay_events_connector_id"), ["connector_id"], unique=False)
            batch_op.create_foreign_key(
                "fk_relay_events_connector_id_integration_connectors",
                "integration_connectors",
                ["connector_id"],
                ["id"],
            )


def downgrade():
    pass
