"""add cases coordinates index

Revision ID: 782e7567009d
Revises: 0bf44bd7207d
Create Date: 2026-03-16 17:09:29.711774

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "782e7567009d"
down_revision = "0bf44bd7207d"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_cases_coordinates",
        "cases",
        ["latitude", "longitude"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_cases_coordinates", table_name="cases")
