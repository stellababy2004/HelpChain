from alembic import op
import sqlalchemy as sa

revision = '18b44c015e6a'
down_revision = '89e64a6fbd28'
branch_labels = None
depends_on = None


def upgrade():
    # 👉 FIX 1: add admin_user_id
    op.add_column(
        "case_participants",
        sa.Column("admin_user_id", sa.Integer(), nullable=True)
    )

    op.create_foreign_key(
        "fk_case_participants_admin_user_id",
        "case_participants",
        "admin_users",
        ["admin_user_id"],
        ["id"],
    )

    # 👉 FIX 2: add latitude / longitude
    op.add_column(
        "intervenants",
        sa.Column("latitude", sa.Float(), nullable=True)
    )
    op.add_column(
        "intervenants",
        sa.Column("longitude", sa.Float(), nullable=True)
    )


def downgrade():
    op.drop_constraint(
        "fk_case_participants_admin_user_id",
        "case_participants",
        type_="foreignkey"
    )

    op.drop_column("case_participants", "admin_user_id")

    op.drop_column("intervenants", "latitude")
    op.drop_column("intervenants", "longitude")