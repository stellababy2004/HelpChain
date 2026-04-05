"""repair case stack schema drift in production

Revision ID: 20260406_0015
Revises: 20260405_2315
Create Date: 2026-04-06 00:15:00
"""

from alembic import context, op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = "20260406_0015"
down_revision = "20260405_2315"
branch_labels = None
depends_on = None


def _has_table(bind, table_name: str) -> bool:
    try:
        insp = inspect(bind)
        return table_name in insp.get_table_names()
    except (sa.exc.NoInspectionAvailable, Exception):
        return False


def _has_column(bind, table_name: str, column_name: str) -> bool:
    try:
        insp = inspect(bind)
        cols = insp.get_columns(table_name)
    except (sa.exc.NoInspectionAvailable, Exception):
        return False
    return any(c.get("name") == column_name for c in cols)


def _has_index(bind, table_name: str, index_name: str) -> bool:
    try:
        insp = inspect(bind)
        indexes = insp.get_indexes(table_name)
    except (sa.exc.NoInspectionAvailable, Exception):
        return False
    return any(idx.get("name") == index_name for idx in indexes)


def _has_foreign_key(bind, table_name: str, constrained_columns: list[str]) -> bool:
    try:
        insp = inspect(bind)
        foreign_keys = insp.get_foreign_keys(table_name)
    except (sa.exc.NoInspectionAvailable, Exception):
        return False
    expected = tuple(constrained_columns)
    for fk in foreign_keys:
        cols = tuple(fk.get("constrained_columns") or ())
        if cols == expected:
            return True
    return False


def _ensure_index(bind, table_name: str, index_name: str, columns: list[str]) -> None:
    if not _has_index(bind, table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade():
    bind = op.get_bind()

    if context.is_offline_mode():
        op.create_table(
            "case_collaborators",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("case_id", sa.Integer(), nullable=False),
            sa.Column("structure_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False, server_default=sa.text("'viewer'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
            sa.ForeignKeyConstraint(["structure_id"], ["structures.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_case_collaborators_case_id", "case_collaborators", ["case_id"], unique=False)
        op.create_index("ix_case_collaborators_created_at", "case_collaborators", ["created_at"], unique=False)
        op.create_index("ix_case_collaborators_role", "case_collaborators", ["role"], unique=False)
        op.create_index("ix_case_collaborators_structure_id", "case_collaborators", ["structure_id"], unique=False)

        op.create_table(
            "case_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("case_id", sa.Integer(), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("event_type", sa.String(length=60), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("visibility", sa.String(length=20), nullable=False, server_default=sa.text("'internal'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["actor_user_id"], ["admin_users.id"]),
            sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_case_events_actor_user_id", "case_events", ["actor_user_id"], unique=False)
        op.create_index("ix_case_events_case_id", "case_events", ["case_id"], unique=False)
        op.create_index("ix_case_events_created_at", "case_events", ["created_at"], unique=False)
        op.create_index("ix_case_events_event_type", "case_events", ["event_type"], unique=False)
        op.create_index("ix_case_events_visibility", "case_events", ["visibility"], unique=False)

        op.create_table(
            "case_participants",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("case_id", sa.Integer(), nullable=False),
            sa.Column("participant_type", sa.String(length=40), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("professional_lead_id", sa.Integer(), nullable=True),
            sa.Column("external_name", sa.String(length=255), nullable=True),
            sa.Column("role", sa.String(length=40), nullable=False, server_default=sa.text("'contributor'")),
            sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'active'")),
            sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
            sa.ForeignKeyConstraint(["professional_lead_id"], ["professional_leads.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_case_participants_added_at", "case_participants", ["added_at"], unique=False)
        op.create_index("ix_case_participants_case_id", "case_participants", ["case_id"], unique=False)
        op.create_index("ix_case_participants_participant_type", "case_participants", ["participant_type"], unique=False)
        op.create_index("ix_case_participants_professional_lead_id", "case_participants", ["professional_lead_id"], unique=False)
        op.create_index("ix_case_participants_role", "case_participants", ["role"], unique=False)
        op.create_index("ix_case_participants_status", "case_participants", ["status"], unique=False)
        op.create_index("ix_case_participants_user_id", "case_participants", ["user_id"], unique=False)
        return

    if _has_table(bind, "cases"):
        with op.batch_alter_table("cases") as batch_op:
            if not _has_column(bind, "cases", "structure_id"):
                batch_op.add_column(sa.Column("structure_id", sa.Integer(), nullable=True))
            if not _has_column(bind, "cases", "owner_user_id"):
                batch_op.add_column(sa.Column("owner_user_id", sa.Integer(), nullable=True))
            if not _has_column(bind, "cases", "assigned_professional_lead_id"):
                batch_op.add_column(
                    sa.Column("assigned_professional_lead_id", sa.Integer(), nullable=True)
                )
            if not _has_column(bind, "cases", "priority"):
                batch_op.add_column(
                    sa.Column(
                        "priority",
                        sa.String(length=20),
                        nullable=False,
                        server_default=sa.text("'normal'"),
                    )
                )
            if not _has_column(bind, "cases", "risk_score"):
                batch_op.add_column(sa.Column("risk_score", sa.Integer(), nullable=True))
            if not _has_column(bind, "cases", "last_activity_at"):
                batch_op.add_column(sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True))

        with op.batch_alter_table("cases") as batch_op:
            if (
                _has_table(bind, "structures")
                and _has_column(bind, "cases", "structure_id")
                and not _has_foreign_key(bind, "cases", ["structure_id"])
            ):
                batch_op.create_foreign_key(
                    "fk_cases_structure_id_structures",
                    "structures",
                    ["structure_id"],
                    ["id"],
                )
            if (
                _has_table(bind, "admin_users")
                and _has_column(bind, "cases", "owner_user_id")
                and not _has_foreign_key(bind, "cases", ["owner_user_id"])
            ):
                batch_op.create_foreign_key(
                    "fk_cases_owner_user_id_admin_users",
                    "admin_users",
                    ["owner_user_id"],
                    ["id"],
                )
            if (
                _has_table(bind, "professional_leads")
                and _has_column(bind, "cases", "assigned_professional_lead_id")
                and not _has_foreign_key(bind, "cases", ["assigned_professional_lead_id"])
            ):
                batch_op.create_foreign_key(
                    "fk_cases_assigned_professional_lead_id_professional_leads",
                    "professional_leads",
                    ["assigned_professional_lead_id"],
                    ["id"],
                )

        if _has_column(bind, "cases", "structure_id"):
            _ensure_index(bind, "cases", "ix_cases_structure_id", ["structure_id"])
        if _has_column(bind, "cases", "owner_user_id"):
            _ensure_index(bind, "cases", "ix_cases_owner_user_id", ["owner_user_id"])
        if _has_column(bind, "cases", "assigned_professional_lead_id"):
            _ensure_index(
                bind,
                "cases",
                "ix_cases_assigned_professional_lead_id",
                ["assigned_professional_lead_id"],
            )
        if _has_column(bind, "cases", "priority"):
            _ensure_index(bind, "cases", "ix_cases_priority", ["priority"])
        if _has_column(bind, "cases", "risk_score"):
            _ensure_index(bind, "cases", "ix_cases_risk_score", ["risk_score"])
        if _has_column(bind, "cases", "last_activity_at"):
            _ensure_index(bind, "cases", "ix_cases_last_activity_at", ["last_activity_at"])

    if not _has_table(bind, "case_collaborators"):
        op.create_table(
            "case_collaborators",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("case_id", sa.Integer(), nullable=False),
            sa.Column("structure_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False, server_default=sa.text("'viewer'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
            sa.ForeignKeyConstraint(["structure_id"], ["structures.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    _ensure_index(bind, "case_collaborators", "ix_case_collaborators_case_id", ["case_id"])
    _ensure_index(bind, "case_collaborators", "ix_case_collaborators_created_at", ["created_at"])
    _ensure_index(bind, "case_collaborators", "ix_case_collaborators_role", ["role"])
    _ensure_index(bind, "case_collaborators", "ix_case_collaborators_structure_id", ["structure_id"])

    if not _has_table(bind, "case_events"):
        op.create_table(
            "case_events",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("case_id", sa.Integer(), nullable=False),
            sa.Column("actor_user_id", sa.Integer(), nullable=True),
            sa.Column("event_type", sa.String(length=60), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("visibility", sa.String(length=20), nullable=False, server_default=sa.text("'internal'")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["actor_user_id"], ["admin_users.id"]),
            sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    _ensure_index(bind, "case_events", "ix_case_events_actor_user_id", ["actor_user_id"])
    _ensure_index(bind, "case_events", "ix_case_events_case_id", ["case_id"])
    _ensure_index(bind, "case_events", "ix_case_events_created_at", ["created_at"])
    _ensure_index(bind, "case_events", "ix_case_events_event_type", ["event_type"])
    _ensure_index(bind, "case_events", "ix_case_events_visibility", ["visibility"])

    if not _has_table(bind, "case_participants"):
        op.create_table(
            "case_participants",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("case_id", sa.Integer(), nullable=False),
            sa.Column("participant_type", sa.String(length=40), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("professional_lead_id", sa.Integer(), nullable=True),
            sa.Column("external_name", sa.String(length=255), nullable=True),
            sa.Column("role", sa.String(length=40), nullable=False, server_default=sa.text("'contributor'")),
            sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'active'")),
            sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
            sa.ForeignKeyConstraint(["professional_lead_id"], ["professional_leads.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    _ensure_index(bind, "case_participants", "ix_case_participants_added_at", ["added_at"])
    _ensure_index(bind, "case_participants", "ix_case_participants_case_id", ["case_id"])
    _ensure_index(bind, "case_participants", "ix_case_participants_participant_type", ["participant_type"])
    _ensure_index(
        bind,
        "case_participants",
        "ix_case_participants_professional_lead_id",
        ["professional_lead_id"],
    )
    _ensure_index(bind, "case_participants", "ix_case_participants_role", ["role"])
    _ensure_index(bind, "case_participants", "ix_case_participants_status", ["status"])
    _ensure_index(bind, "case_participants", "ix_case_participants_user_id", ["user_id"])


def downgrade():
    # Data-safe downgrade: keep repaired case stack schema once created.
    pass
