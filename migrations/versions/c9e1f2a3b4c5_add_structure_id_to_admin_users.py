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
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "admin_users" not in insp.get_table_names():
        return
    existing_cols = {c["name"] for c in insp.get_columns("admin_users")}
    with op.batch_alter_table("admin_users") as batch_op:
        if "structure_id" not in existing_cols:
            batch_op.add_column(sa.Column("structure_id", sa.Integer(), nullable=True))
        # FK/index are safe to attempt in batch mode for SQLite.
        batch_op.create_foreign_key(
            "fk_admin_users_structure_id",
            "structures",
            ["structure_id"],
            ["id"],
        )
        batch_op.create_index("ix_admin_users_structure_id", ["structure_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "admin_users" not in insp.get_table_names():
        return
    with op.batch_alter_table("admin_users") as batch_op:
        batch_op.drop_index("ix_admin_users_structure_id")
        batch_op.drop_constraint(
            "fk_admin_users_structure_id",
            type_="foreignkey",
        )
        batch_op.drop_column("structure_id")
