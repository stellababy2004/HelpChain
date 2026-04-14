"""case_participant: add admin_user relation

Revision ID: 27eefbea70e9
Revises: c91e21741d5c
Create Date: 2026-04-14
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "27eefbea70e9"
down_revision = "c91e21741d5c"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "case_participants",
        sa.Column("admin_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_case_participants_admin_user_id",
        "case_participants",
        "admin_users",
        ["admin_user_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint(
        "fk_case_participants_admin_user_id",
        "case_participants",
        type_="foreignkey",
    )
    op.drop_column("case_participants", "admin_user_id")