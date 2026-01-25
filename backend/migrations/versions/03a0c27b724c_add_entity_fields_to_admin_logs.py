"""add entity fields to admin_logs

Revision ID: 03a0c27b724c
Revises: 9c6b7a2b0a77
Create Date: 2026-01-25 14:47:44.982473

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '03a0c27b724c'
down_revision = '9c6b7a2b0a77'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns("admin_logs")}

    with op.batch_alter_table("admin_logs") as batch:
        if "entity_type" not in cols:
            batch.add_column(sa.Column("entity_type", sa.String(length=50), nullable=True))
        if "entity_id" not in cols:
            batch.add_column(sa.Column("entity_id", sa.Integer(), nullable=True))
        if "ip_address" not in cols:
            batch.add_column(sa.Column("ip_address", sa.String(length=45), nullable=True))
        if "user_agent" not in cols:
            batch.add_column(sa.Column("user_agent", sa.String(length=255), nullable=True))


def downgrade():
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns("admin_logs")}

    with op.batch_alter_table("admin_logs") as batch:
        if "user_agent" in cols:
            batch.drop_column("user_agent")
        if "ip_address" in cols:
            batch.drop_column("ip_address")
        if "entity_id" in cols:
            batch.drop_column("entity_id")
        if "entity_type" in cols:
            batch.drop_column("entity_type")
