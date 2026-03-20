"""add latitude longitude to cases

Revision ID: 0bf44bd7207d
Revises: 7f2c3d4e5a6b
Create Date: 2026-03-16 12:01:43.123501

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0bf44bd7207d"
down_revision = "7f2c3d4e5a6b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("cases", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("cases", sa.Column("longitude", sa.Float(), nullable=True))


def downgrade():
    op.drop_column("cases", "longitude")
    op.drop_column("cases", "latitude")
