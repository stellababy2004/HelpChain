"""add request deleted_at tombstone

Revision ID: 9c6b7a2b0a77
Revises: 4f1b2c0d9a16
Create Date: 2026-01-24 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "9c6b7a2b0a77"
down_revision = "4f1b2c0d9a16"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("requests", schema=None) as batch_op:
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))

    op.create_index("ix_requests_deleted_at", "requests", ["deleted_at"])


def downgrade():
    op.drop_index("ix_requests_deleted_at", table_name="requests")

    with op.batch_alter_table("requests", schema=None) as batch_op:
        batch_op.drop_column("deleted_at")

