"""add volunteers.user_id when missing (production schema drift)

Revision ID: d2e8f4a1b6c3
Revises: f1b2c3d4e5f6
Create Date: 2026-03-02 16:05:00
"""

from alembic import op
import sqlalchemy as sa
from backend.db.migration_utils import safe_drop_column, safe_drop_constraint, safe_drop_index


# revision identifiers, used by Alembic.
revision = "d2e8f4a1b6c3"
down_revision = "f1b2c3d4e5f6"
branch_labels = None
depends_on = None


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {col.get("name") for col in inspector.get_columns(table_name)}


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {idx.get("name") for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "volunteers" not in set(inspector.get_table_names()):
        return

    cols = _column_names(inspector, "volunteers")
    if "user_id" not in cols:
        op.add_column("volunteers", sa.Column("user_id", sa.Integer(), nullable=True))

    inspector = sa.inspect(bind)
    idx_names = _index_names(inspector, "volunteers")
    if "ix_volunteers_user_id" not in idx_names:
        safe_create_index(op, "ix_volunteers_user_id", "volunteers", ["user_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "volunteers" not in set(inspector.get_table_names()):
        return

    idx_names = _index_names(inspector, "volunteers")
    if "ix_volunteers_user_id" in idx_names:
        safe_drop_index(op, "ix_volunteers_user_id", table_name="volunteers")

    cols = _column_names(sa.inspect(bind), "volunteers")
    if "user_id" in cols:
        safe_drop_column(op, "volunteers", "user_id")