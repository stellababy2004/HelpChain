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


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "intervenants" not in tables:
        op.create_table(
            "intervenants",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("structure_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=True),
            sa.Column(
                "actor_type",
                sa.String(length=50),
                nullable=False,
                server_default=sa.text("'volunteer'"),
            ),
            sa.Column("email", sa.String(length=200), nullable=True),
            sa.Column("phone", sa.String(length=50), nullable=True),
            sa.Column("location", sa.String(length=200), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["structure_id"], ["structures.id"]),
        )

    inspector = sa.inspect(bind)
    index_names = {idx["name"] for idx in inspector.get_indexes("intervenants")}

    if "ix_intervenants_structure_id" not in index_names:
        op.create_index(
            "ix_intervenants_structure_id",
            "intervenants",
            ["structure_id"],
            unique=False,
        )
    if "ix_intervenants_actor_type" not in index_names:
        op.create_index(
            "ix_intervenants_actor_type",
            "intervenants",
            ["actor_type"],
            unique=False,
        )
    if "ix_intervenants_created_at" not in index_names:
        op.create_index(
            "ix_intervenants_created_at",
            "intervenants",
            ["created_at"],
            unique=False,
        )


def downgrade() -> None:
    pass
