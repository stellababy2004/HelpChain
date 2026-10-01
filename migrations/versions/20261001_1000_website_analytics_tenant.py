"""Associate website analytics with structures without guessing historical owners.

Revision ID: 20261001_1000
Revises: 20260930_0600
"""

from alembic import op
import sqlalchemy as sa

revision = "20261001_1000"
down_revision = "20260930_0600"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("analytics_events") as batch:
        batch.add_column(sa.Column("structure_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_analytics_events_structure_id", "structures", ["structure_id"], ["id"])
        batch.create_index("ix_analytics_events_structure_id", ["structure_id"])


def downgrade():
    with op.batch_alter_table("analytics_events") as batch:
        batch.drop_index("ix_analytics_events_structure_id")
        batch.drop_constraint("fk_analytics_events_structure_id", type_="foreignkey")
        batch.drop_column("structure_id")
