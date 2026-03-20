"""add case_collaborators table

Revision ID: 7f2c3d4e5a6b
Revises: 5b1a9c2d3e4f
Create Date: 2026-03-16 11:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7f2c3d4e5a6b"
down_revision = "5b1a9c2d3e4f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "case_collaborators" not in tables:
        op.create_table(
            "case_collaborators",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id"), nullable=False),
            sa.Column(
                "structure_id",
                sa.Integer(),
                sa.ForeignKey("structures.id"),
                nullable=False,
            ),
            sa.Column(
                "role",
                sa.String(length=32),
                nullable=False,
                server_default=sa.text("'viewer'"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.UniqueConstraint(
                "case_id",
                "structure_id",
                name="uq_case_collaborators_case_structure",
            ),
        )

    inspector = sa.inspect(bind)
    index_names = {idx["name"] for idx in inspector.get_indexes("case_collaborators")}

    if "ix_case_collaborators_case_id" not in index_names:
        op.create_index(
            "ix_case_collaborators_case_id",
            "case_collaborators",
            ["case_id"],
            unique=False,
        )
    if "ix_case_collaborators_structure_id" not in index_names:
        op.create_index(
            "ix_case_collaborators_structure_id",
            "case_collaborators",
            ["structure_id"],
            unique=False,
        )
    if "ix_case_collaborators_role" not in index_names:
        op.create_index(
            "ix_case_collaborators_role",
            "case_collaborators",
            ["role"],
            unique=False,
        )
    if "ix_case_collaborators_created_at" not in index_names:
        op.create_index(
            "ix_case_collaborators_created_at",
            "case_collaborators",
            ["created_at"],
            unique=False,
        )


def downgrade() -> None:
    pass
