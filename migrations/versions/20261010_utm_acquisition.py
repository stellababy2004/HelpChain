"""add UTM acquisition attribution to user behaviors

Revision ID: 20261010_utm
Revises: 20261008_1200
"""

from alembic import op
import sqlalchemy as sa


revision = "20261010_utm"
down_revision = "20261008_1200"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user_behaviors", schema=None) as batch_op:
        batch_op.add_column(sa.Column("utm_source", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("utm_medium", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("utm_campaign", sa.String(length=150), nullable=True))


def downgrade():
    with op.batch_alter_table("user_behaviors", schema=None) as batch_op:
        batch_op.drop_column("utm_campaign")
        batch_op.drop_column("utm_medium")
        batch_op.drop_column("utm_source")
