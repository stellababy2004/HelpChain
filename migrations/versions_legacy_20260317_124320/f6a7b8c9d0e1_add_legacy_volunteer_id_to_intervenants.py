"""add legacy_volunteer_id to intervenants

Revision ID: f6a7b8c9d0e1
Revises: e1a2b3c4d5e6
Create Date: 2026-03-15 09:55:00.000000
"""

from alembic import op
import sqlalchemy as sa
from backend.db.migration_utils import safe_drop_column, safe_drop_constraint, safe_drop_index, safe_create_index


# revision identifiers, used by Alembic.
revision = "f6a7b8c9d0e1"
down_revision = "e1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "intervenants",
        sa.Column("legacy_volunteer_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_intervenants_legacy_volunteer_id",
        "intervenants",
        ["legacy_volunteer_id"],
    )


def downgrade():
    safe_drop_index(op, 
        "ix_intervenants_legacy_volunteer_id",
        table_name="intervenants",
    )
    safe_drop_column(op, "intervenants", "legacy_volunteer_id")