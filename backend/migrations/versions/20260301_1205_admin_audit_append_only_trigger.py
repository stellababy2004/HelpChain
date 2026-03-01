"""enforce append-only admin_audit_events (postgres)

Revision ID: 20260301_1205
Revises: 20260301_1008
Create Date: 2026-03-01 12:05:00
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260301_1205"
down_revision = "20260301_1008"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE OR REPLACE FUNCTION admin_audit_events_append_only()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          RAISE EXCEPTION 'admin_audit_events is append-only: % not allowed', TG_OP
            USING ERRCODE = '42501';
        END;
        $$;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_admin_audit_events_append_only
        ON admin_audit_events;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_admin_audit_events_append_only
        BEFORE UPDATE OR DELETE ON admin_audit_events
        FOR EACH ROW
        EXECUTE FUNCTION admin_audit_events_append_only();
        """
    )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_admin_audit_events_append_only
        ON admin_audit_events;
        """
    )
    op.execute("DROP FUNCTION IF EXISTS admin_audit_events_append_only();")

