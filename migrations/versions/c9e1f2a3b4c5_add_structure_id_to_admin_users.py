"""add structure_id to admin_users

Revision ID: c9e1f2a3b4c5
Revises: b7c8d9e0f1a2
Create Date: 2026-03-14 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "c9e1f2a3b4c5"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admin_users",
        sa.Column("structure_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_admin_users_structure_id",
        "admin_users",
        "structures",
        ["structure_id"],
        ["id"],
    )
    op.create_index(
        "ix_admin_users_structure_id",
        "admin_users",
        ["structure_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_admin_users_structure_id", table_name="admin_users")
    op.drop_constraint(
        "fk_admin_users_structure_id",
        "admin_users",
        type_="foreignkey",
    )
    op.drop_column("admin_users", "structure_id")
