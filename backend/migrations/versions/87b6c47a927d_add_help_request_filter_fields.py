"""add help request filter fields

Revision ID: 87b6c47a927d
Revises: add_lat_lng_volunteer
Create Date: 2025-10-29 11:45:06.983221

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "87b6c47a927d"
down_revision = "add_lat_lng_volunteer"
branch_labels = None
depends_on = None


STATUS_NORMALIZATION_MAP = {
    "Pending": "pending",
    "Approved": "approved",
    "Rejected": "rejected",
    "Completed": "completed",
    "Assigned": "assigned",
    "In Progress": "in_progress",
}


def upgrade():
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    inspector = sa.inspect(bind)

    # Defensive: if the help_requests table doesn't exist yet (some revision
    # trees create it in a later migration), skip this migration. The original
    # migration assumed the table existed which causes failures when the
    # applied migration order differs. Making this migration a no-op when the
    # table is absent preserves idempotence and avoids ordering fragility.
    existing_table_names = {t.lower() for t in inspector.get_table_names()}
    if "help_requests" not in existing_table_names:
        # Nothing to do in this environment; bail out cleanly.
        return

    existing_columns = {col["name"] for col in inspector.get_columns("help_requests")}

    def add_column_if_missing(name, column):
        if name not in existing_columns:
            op.add_column("help_requests", column)
            existing_columns.add(name)

    add_column_if_missing(
        "location_text",
        sa.Column("location_text", sa.String(length=255), nullable=True),
    )
    add_column_if_missing(
        "city",
        sa.Column("city", sa.String(length=100), nullable=True),
    )
    add_column_if_missing(
        "region",
        sa.Column("region", sa.String(length=100), nullable=True),
    )
    add_column_if_missing(
        "assigned_volunteer_id",
        sa.Column("assigned_volunteer_id", sa.Integer(), nullable=True),
    )
    add_column_if_missing(
        "completed_at",
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    add_column_if_missing(
        "source_channel",
        sa.Column("source_channel", sa.String(length=50), nullable=True),
    )

    existing_fks = {
        fk["name"]
        for fk in inspector.get_foreign_keys("help_requests")
        if fk.get("name")
    }
    if not is_sqlite and "fk_help_request_assigned_volunteer_id" not in existing_fks:
        op.create_foreign_key(
            "fk_help_request_assigned_volunteer_id",
            "help_requests",
            "volunteers",
            ["assigned_volunteer_id"],
            ["id"],
        )

    existing_indexes = {
        idx["name"] for idx in inspector.get_indexes("help_requests") if idx.get("name")
    }
    if "ix_help_request_location_text" not in existing_indexes:
        op.create_index(
            "ix_help_request_location_text",
            "help_requests",
            ["location_text"],
            unique=False,
        )
    if "ix_help_request_city" not in existing_indexes:
        op.create_index(
            "ix_help_request_city",
            "help_requests",
            ["city"],
            unique=False,
        )
    if "ix_help_request_region" not in existing_indexes:
        op.create_index(
            "ix_help_request_region",
            "help_requests",
            ["region"],
            unique=False,
        )
    if "ix_help_request_assigned_volunteer_id" not in existing_indexes:
        op.create_index(
            "ix_help_request_assigned_volunteer_id",
            "help_requests",
            ["assigned_volunteer_id"],
            unique=False,
        )
    if "ix_help_request_completed_at" not in existing_indexes:
        op.create_index(
            "ix_help_request_completed_at",
            "help_requests",
            ["completed_at"],
            unique=False,
        )
    if "ix_help_request_source_channel" not in existing_indexes:
        op.create_index(
            "ix_help_request_source_channel",
            "help_requests",
            ["source_channel"],
            unique=False,
        )

    for old_status, new_status in STATUS_NORMALIZATION_MAP.items():
        op.execute(
            sa.text(
                "UPDATE help_requests SET status = :new_status WHERE status = :old_status"
            ).bindparams(new_status=new_status, old_status=old_status)
        )


def downgrade():
    for old_status, new_status in STATUS_NORMALIZATION_MAP.items():
        op.execute(
            sa.text(
                "UPDATE help_requests SET status = :old_status WHERE status = :new_status"
            ).bindparams(new_status=new_status, old_status=old_status)
        )

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # If the table doesn't exist, there's nothing to undo here.
    existing_table_names = {t.lower() for t in inspector.get_table_names()}
    if "help_requests" not in existing_table_names:
        return
    existing_indexes = {
        idx["name"] for idx in inspector.get_indexes("help_requests") if idx.get("name")
    }

    if "ix_help_request_source_channel" in existing_indexes:
        op.drop_index("ix_help_request_source_channel", table_name="help_requests")
    if "ix_help_request_completed_at" in existing_indexes:
        op.drop_index("ix_help_request_completed_at", table_name="help_requests")
    if "ix_help_request_assigned_volunteer_id" in existing_indexes:
        op.drop_index(
            "ix_help_request_assigned_volunteer_id", table_name="help_requests"
        )
    if "ix_help_request_region" in existing_indexes:
        op.drop_index("ix_help_request_region", table_name="help_requests")
    if "ix_help_request_city" in existing_indexes:
        op.drop_index("ix_help_request_city", table_name="help_requests")
    if "ix_help_request_location_text" in existing_indexes:
        op.drop_index("ix_help_request_location_text", table_name="help_requests")

    is_sqlite = bind.dialect.name == "sqlite"
    existing_fks = {
        fk["name"]
        for fk in inspector.get_foreign_keys("help_requests")
        if fk.get("name")
    }
    if not is_sqlite and "fk_help_request_assigned_volunteer_id" in existing_fks:
        op.drop_constraint(
            "fk_help_request_assigned_volunteer_id",
            "help_requests",
            type_="foreignkey",
        )

    existing_columns = {col["name"] for col in inspector.get_columns("help_requests")}
    for column_name in (
        "source_channel",
        "completed_at",
        "assigned_volunteer_id",
        "region",
        "city",
        "location_text",
    ):
        if column_name in existing_columns:
            op.drop_column("help_requests", column_name)
