"""add explicit volunteer structure memberships"""

from alembic import op
import sqlalchemy as sa


revision = "20261030_1200"
down_revision = "20261026_1200"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "volunteer_structure_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("volunteer_id", sa.Integer(), nullable=False),
        sa.Column("structure_id", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("approved_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("suspended_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("suspended_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["volunteer_id"], ["volunteers.id"]),
        sa.ForeignKeyConstraint(["structure_id"], ["structures.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["approved_by_admin_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["suspended_by_admin_id"], ["admin_users.id"]),
        sa.ForeignKeyConstraint(["revoked_by_admin_id"], ["admin_users.id"]),
        sa.UniqueConstraint(
            "volunteer_id",
            "structure_id",
            name="uq_volunteer_structure_membership",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'suspended', 'revoked')",
            name="ck_volunteer_structure_membership_status",
        ),
    )
    op.create_index(
        "ix_volunteer_structure_memberships_volunteer_id",
        "volunteer_structure_memberships",
        ["volunteer_id"],
    )
    op.create_index(
        "ix_volunteer_structure_memberships_structure_id",
        "volunteer_structure_memberships",
        ["structure_id"],
    )
    op.create_index(
        "ix_volunteer_structure_membership_structure_status",
        "volunteer_structure_memberships",
        ["structure_id", "status"],
    )
    op.create_index(
        "ix_volunteer_structure_membership_volunteer_status",
        "volunteer_structure_memberships",
        ["volunteer_id", "status"],
    )


def downgrade():
    op.drop_table("volunteer_structure_memberships")
