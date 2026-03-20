"""add admin_audit_events table in root migration chain

Revision ID: e4b7a1c2d9f0
Revises: c3f9d1a7b2e4
Create Date: 2026-03-02 15:05:00
"""

from alembic import op
import sqlalchemy as sa
from backend.db.migration_utils import safe_drop_column, safe_drop_constraint, safe_drop_index, safe_create_index


# revision identifiers, used by Alembic.
revision = "e4b7a1c2d9f0"
down_revision = "c3f9d1a7b2e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "admin_audit_events" in existing_tables:
        return

    op.create_table(
        "admin_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("admin_user_id", sa.Integer(), nullable=True),
        sa.Column("admin_username", sa.String(length=120), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
    )

    op.create_index(
        "ix_admin_audit_events_created_at",
        "admin_audit_events",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_admin_audit_events_admin_user_id",
        "admin_audit_events",
        ["admin_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_admin_audit_events_admin_username",
        "admin_audit_events",
        ["admin_username"],
        unique=False,
    )
    op.create_index(
        "ix_admin_audit_events_action",
        "admin_audit_events",
        ["action"],
        unique=False,
    )
    op.create_index(
        "ix_admin_audit_events_target_type_target_id_created_at",
        "admin_audit_events",
        ["target_type", "target_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "admin_audit_events" not in existing_tables:
        return

    for idx in (
        "ix_admin_audit_events_target_type_target_id_created_at",
        "ix_admin_audit_events_action",
        "ix_admin_audit_events_admin_username",
        "ix_admin_audit_events_admin_user_id",
        "ix_admin_audit_events_created_at",
    ):
        safe_drop_index(op, idx, table_name="admin_audit_events")
    op.drop_table("admin_audit_events")