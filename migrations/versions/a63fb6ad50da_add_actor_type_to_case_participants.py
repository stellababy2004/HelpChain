"""add actor_type to case_participants

Revision ID: a63fb6ad50da
Revises: 18b44c015e6a
Create Date: 2026-04-15 10:46:50.813545

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'a63fb6ad50da'
down_revision = '18b44c015e6a'
branch_labels = None
depends_on = None


from sqlalchemy import inspect


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    if not _has_column("case_participants", "actor_type"):
        with op.batch_alter_table("case_participants") as batch_op:
            batch_op.add_column(
                sa.Column("actor_type", sa.String(length=32), nullable=True)
            )


def downgrade():
    if _has_column("case_participants", "actor_type"):
        with op.batch_alter_table("case_participants") as batch_op:
            batch_op.drop_column("actor_type")

