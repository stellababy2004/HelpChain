"""add created_at to admin_logs

Revision ID: fb611ecf034d
Revises: 03a0c27b724c
Create Date: 2026-01-25 17:22:36.097709

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'fb611ecf034d'
down_revision = '03a0c27b724c'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns("admin_logs")}

    with op.batch_alter_table("admin_logs") as batch:
        if "created_at" not in cols:
            batch.add_column(
                sa.Column(
                    "created_at",
                    sa.DateTime(),
                    nullable=True,
                    server_default=sa.text("CURRENT_TIMESTAMP"),
                )
            )


def downgrade():
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns("admin_logs")}

    with op.batch_alter_table("admin_logs") as batch:
        if "created_at" in cols:
            batch.drop_column("created_at")
