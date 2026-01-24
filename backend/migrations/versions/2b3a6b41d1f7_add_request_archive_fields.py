"""add request archive fields

Revision ID: 2b3a6b41d1f7
Revises: add_lat_lng_volunteer
Create Date: 2026-01-24 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "2b3a6b41d1f7"
down_revision = "add_lat_lng_volunteer"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("requests", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("archived_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("requests", schema=None) as batch_op:
        batch_op.drop_column("archived_at")
        batch_op.drop_column("is_archived")

