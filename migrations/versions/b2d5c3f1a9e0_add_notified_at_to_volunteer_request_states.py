"""add notified_at to volunteer_request_states

Revision ID: b2d5c3f1a9e0
Revises: 7c0e1f8d2a4b
Create Date: 2026-02-19
"""

from alembic import op
import sqlalchemy as sa


revision = "b2d5c3f1a9e0"
down_revision = "7c0e1f8d2a4b"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("volunteer_request_states")}

    if "notified_at" not in cols:
        op.add_column(
            "volunteer_request_states",
            sa.Column("notified_at", sa.DateTime(), nullable=True),
        )

    indexes = {idx["name"] for idx in insp.get_indexes("volunteer_request_states")}
    if "ix_volunteer_request_states_notified_at" not in indexes:
        op.create_index(
            "ix_volunteer_request_states_notified_at",
            "volunteer_request_states",
            ["notified_at"],
            unique=False,
        )

    vrs = sa.table(
        "volunteer_request_states",
        sa.column("volunteer_id", sa.Integer()),
        sa.column("request_id", sa.Integer()),
        sa.column("created_at", sa.DateTime()),
        sa.column("notified_at", sa.DateTime()),
    )
    notif = sa.table(
        "notifications",
        sa.column("volunteer_id", sa.Integer()),
        sa.column("request_id", sa.Integer()),
        sa.column("type", sa.String()),
        sa.column("created_at", sa.DateTime()),
    )

    rows = bind.execute(
        sa.select(
            notif.c.volunteer_id,
            notif.c.request_id,
            sa.func.min(notif.c.created_at).label("first_notified_at"),
        )
        .where(notif.c.type == "new_match")
        .where(notif.c.request_id.isnot(None))
        .group_by(notif.c.volunteer_id, notif.c.request_id)
    ).fetchall()

    for row in rows:
        first_notified = row.first_notified_at
        if first_notified is None:
            continue
        bind.execute(
            vrs.update()
            .where(vrs.c.volunteer_id == row.volunteer_id)
            .where(vrs.c.request_id == row.request_id)
            .where(
                sa.or_(
                    vrs.c.notified_at.is_(None),
                    vrs.c.notified_at > first_notified,
                )
            )
            .values(notified_at=first_notified)
        )

    bind.execute(
        vrs.update()
        .where(vrs.c.notified_at.is_(None))
        .where(vrs.c.created_at.isnot(None))
        .values(notified_at=vrs.c.created_at)
    )


def downgrade():
    bind = op.get_bind()
    indexes = {
        idx["name"] for idx in sa.inspect(bind).get_indexes("volunteer_request_states")
    }
    if "ix_volunteer_request_states_notified_at" in indexes:
        op.drop_index(
            "ix_volunteer_request_states_notified_at",
            table_name="volunteer_request_states",
        )

    cols = {
        c["name"] for c in sa.inspect(bind).get_columns("volunteer_request_states")
    }
    if "notified_at" in cols:
        op.drop_column("volunteer_request_states", "notified_at")
