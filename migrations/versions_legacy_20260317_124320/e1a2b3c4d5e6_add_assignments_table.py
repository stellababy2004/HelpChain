"""add assignments table

Revision ID: e1a2b3c4d5e6
Revises: d4f1c2a3b5d6
Create Date: 2026-03-15 09:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e1a2b3c4d5e6"
down_revision = "d4f1c2a3b5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "assignments" not in tables:
        op.create_table(
            "assignments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("request_id", sa.Integer(), nullable=False),
            sa.Column("intervenant_id", sa.Integer(), nullable=False),
            sa.Column("assigned_by_admin_id", sa.Integer(), nullable=True),
            sa.Column("assigned_at", sa.DateTime(), nullable=False),
            sa.Column(
                "status",
                sa.String(length=32),
                nullable=False,
                server_default=sa.text("'active'"),
            ),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["request_id"], ["requests.id"]),
            sa.ForeignKeyConstraint(["intervenant_id"], ["intervenants.id"]),
            sa.ForeignKeyConstraint(["assigned_by_admin_id"], ["admin_users.id"]),
        )

    inspector = sa.inspect(bind)
    index_names = {idx["name"] for idx in inspector.get_indexes("assignments")}

    if "ix_assignments_request_id" not in index_names:
        op.create_index(
            "ix_assignments_request_id",
            "assignments",
            ["request_id"],
            unique=False,
        )
    if "ix_assignments_intervenant_id" not in index_names:
        op.create_index(
            "ix_assignments_intervenant_id",
            "assignments",
            ["intervenant_id"],
            unique=False,
        )
    if "ix_assignments_assigned_at" not in index_names:
        op.create_index(
            "ix_assignments_assigned_at",
            "assignments",
            ["assigned_at"],
            unique=False,
        )
    if "ix_assignments_status" not in index_names:
        op.create_index(
            "ix_assignments_status",
            "assignments",
            ["status"],
            unique=False,
        )


def downgrade() -> None:
    pass
