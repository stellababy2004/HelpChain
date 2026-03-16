"""add intervenants table

Revision ID: d4f1c2a3b5d6
Revises: c9e1f2a3b4c5
Create Date: 2026-03-15 02:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d4f1c2a3b5d6"
down_revision = "c9e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "intervenants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("structure_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column(
            "actor_type",
            sa.String(length=50),
            nullable=False,
            server_default="volunteer",
        ),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["structure_id"], ["structures.id"]),
    )
    op.create_index("ix_intervenants_structure_id", "intervenants", ["structure_id"])
    op.create_index("ix_intervenants_actor_type", "intervenants", ["actor_type"])
    op.create_index("ix_intervenants_created_at", "intervenants", ["created_at"])


def downgrade():
    op.drop_index("ix_intervenants_created_at", table_name="intervenants")
    op.drop_index("ix_intervenants_actor_type", table_name="intervenants")
    op.drop_index("ix_intervenants_structure_id", table_name="intervenants")
    op.drop_table("intervenants")
