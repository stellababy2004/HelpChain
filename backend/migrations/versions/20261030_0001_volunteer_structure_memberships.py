"""create explicit volunteer structure memberships

Revision ID: 20261030_0001
Revises: 20260514_1430
Create Date: 2026-10-30 00:01:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20261030_0001"
down_revision = "20260514_1430"
branch_labels = None
depends_on = None


TABLE_NAME = "volunteer_structure_memberships"


def _has_table(bind) -> bool:
    return TABLE_NAME in inspect(bind).get_table_names()


def upgrade():
    bind = op.get_bind()
    if _has_table(bind):
        return

    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "volunteer_id",
            sa.Integer(),
            sa.ForeignKey("volunteers.id"),
            nullable=False,
        ),
        sa.Column(
            "structure_id",
            sa.Integer(),
            sa.ForeignKey("structures.id"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "requested_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "approved_by_admin_id",
            sa.Integer(),
            sa.ForeignKey("admin_users.id"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column(
            "suspended_by_admin_id",
            sa.Integer(),
            sa.ForeignKey("admin_users.id"),
            nullable=True,
        ),
        sa.Column("suspended_at", sa.DateTime(), nullable=True),
        sa.Column(
            "revoked_by_admin_id",
            sa.Integer(),
            sa.ForeignKey("admin_users.id"),
            nullable=True,
        ),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint(
            "volunteer_id",
            "structure_id",
            name="uq_volunteer_structure_membership",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'suspended', 'revoked')",
            name="ck_volunteer_structure_membership_status",
        ),
    )

    op.create_index(
        "ix_volunteer_structure_membership_volunteer",
        TABLE_NAME,
        ["volunteer_id"],
    )
    op.create_index(
        "ix_volunteer_structure_membership_structure",
        TABLE_NAME,
        ["structure_id"],
    )
    op.create_index(
        "ix_volunteer_structure_membership_status",
        TABLE_NAME,
        ["status"],
    )
    op.create_index(
        "ix_volunteer_structure_membership_structure_status",
        TABLE_NAME,
        ["structure_id", "status"],
    )
    op.create_index(
        "ix_volunteer_structure_membership_volunteer_status",
        TABLE_NAME,
        ["volunteer_id", "status"],
    )


def downgrade():
    # Intentionally non-destructive: membership history must not be deleted
    # by an automatic downgrade.
    pass
