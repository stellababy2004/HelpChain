"""Remove duplicate twofa_enabled column from admin_users

Revision ID: remove_twofa_col
Revises: 001_initial
Create Date: 2025-10-20 12:00:00

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "remove_twofa_col"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade():
    # Remove the old twofa_enabled column from admin_users table
    op.drop_column("admin_users", "twofa_enabled")


def downgrade():
    # Add back the twofa_enabled column if needed for rollback
    op.add_column(
        "admin_users", sa.Column("twofa_enabled", sa.Boolean(), nullable=True)
    )
