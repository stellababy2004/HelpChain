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


def upgrade():
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
            server_default="active",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["request_id"], ["requests.id"]),
        sa.ForeignKeyConstraint(["intervenant_id"], ["intervenants.id"]),
        sa.ForeignKeyConstraint(["assigned_by_admin_id"], ["admin_users.id"]),
    )
    op.create_index("ix_assignments_request_id", "assignments", ["request_id"])
    op.create_index("ix_assignments_intervenant_id", "assignments", ["intervenant_id"])
    op.create_index("ix_assignments_assigned_at", "assignments", ["assigned_at"])
    op.create_index("ix_assignments_status", "assignments", ["status"])


def downgrade():
    op.drop_index("ix_assignments_status", table_name="assignments")
    op.drop_index("ix_assignments_assigned_at", table_name="assignments")
    op.drop_index("ix_assignments_intervenant_id", table_name="assignments")
    op.drop_index("ix_assignments_request_id", table_name="assignments")
    op.drop_table("assignments")
