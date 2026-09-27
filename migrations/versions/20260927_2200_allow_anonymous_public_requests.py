"""Allow anonymous public requests.

Revision ID: 20260927_2200
Revises: 20260729_1600
"""

from alembic import op
import sqlalchemy as sa


revision = "20260927_2200"
down_revision = "20260729_1600"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("requests") as batch_op:
            batch_op.alter_column(
                "user_id",
                existing_type=sa.Integer(),
                nullable=True,
            )
    else:
        op.alter_column(
            "requests",
            "user_id",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade():
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("requests") as batch_op:
            batch_op.alter_column(
                "user_id",
                existing_type=sa.Integer(),
                nullable=False,
            )
    else:
        op.alter_column(
            "requests",
            "user_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
