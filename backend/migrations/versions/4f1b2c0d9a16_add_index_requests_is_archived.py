"""add index for requests.is_archived

Revision ID: 4f1b2c0d9a16
Revises: 2b3a6b41d1f7
Create Date: 2026-01-24 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "4f1b2c0d9a16"
down_revision = "2b3a6b41d1f7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_requests_is_archived", "requests", ["is_archived"])


def downgrade():
    op.drop_index("ix_requests_is_archived", table_name="requests")

