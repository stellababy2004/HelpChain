"""add structure_id to users

Revision ID: 5b1a9c2d3e4f
Revises: 4c2f9d1a6b7e
Create Date: 2026-03-16 03:25:00.000000
"""

from alembic import op
import sqlalchemy as sa
from backend.db.migration_utils import safe_drop_column, safe_drop_constraint, safe_drop_index
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "5b1a9c2d3e4f"
down_revision = "4c2f9d1a6b7e"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if "users" not in inspector.get_table_names():
        return

    op.add_column(
        "users",
        sa.Column("structure_id", sa.Integer(), nullable=True),
    )
    index_names = [i.get("name") for i in inspector.get_indexes("users")]
    if "ix_users_structure_id" not in index_names:
        safe_create_index(op, "ix_users_structure_id", "users", ["structure_id"])
    op.create_foreign_key(
        "fk_users_structure_id",
        "users",
        "structures",
        ["structure_id"],
        ["id"],
    )


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if "users" not in inspector.get_table_names():
        return

    safe_drop_constraint(op, "fk_users_structure_id", "users", type_="foreignkey")
    safe_drop_index(op, "ix_users_structure_id", table_name="users")
    safe_drop_column(op, "users", "structure_id")