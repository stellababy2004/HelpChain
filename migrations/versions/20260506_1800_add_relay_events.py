"""add relay events table

Revision ID: 20260506_1800
Revises: 20260429_1100
Create Date: 2026-05-06 18:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260506_1800"
down_revision = "20260429_1100"
branch_labels = None
depends_on = None


def _has_table(bind, table_name: str) -> bool:
    try:
        return table_name in inspect(bind).get_table_names()
    except Exception:
        return False


def upgrade():
    bind = op.get_bind()
    table_name = "relay_events"
    if _has_table(bind, table_name):
        return

    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("external_source", sa.String(length=120), nullable=False),
        sa.Column("external_reference_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("priority", sa.String(length=64), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("relance_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("structure_id", sa.Integer(), nullable=True),
        sa.Column("summary_label", sa.String(length=255), nullable=True),
        sa.Column(
            "sync_status",
            sa.String(length=32),
            nullable=False,
            server_default="received",
        ),
        sa.Column("rejected_fields_json", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["structure_id"], ["structures.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_relay_events_created_at"), table_name, ["created_at"], unique=False)
    op.create_index(op.f("ix_relay_events_external_source"), table_name, ["external_source"], unique=False)
    op.create_index(
        op.f("ix_relay_events_external_reference_id"),
        table_name,
        ["external_reference_id"],
        unique=False,
    )
    op.create_index(op.f("ix_relay_events_status"), table_name, ["status"], unique=False)
    op.create_index(op.f("ix_relay_events_priority"), table_name, ["priority"], unique=False)
    op.create_index(op.f("ix_relay_events_category"), table_name, ["category"], unique=False)
    op.create_index(op.f("ix_relay_events_due_date"), table_name, ["due_date"], unique=False)
    op.create_index(op.f("ix_relay_events_relance_at"), table_name, ["relance_at"], unique=False)
    op.create_index(op.f("ix_relay_events_structure_id"), table_name, ["structure_id"], unique=False)
    op.create_index(op.f("ix_relay_events_sync_status"), table_name, ["sync_status"], unique=False)


def downgrade():
    # Data-safe downgrade: keep relay events once provisioned.
    pass
