"""add professional leads

Revision ID: 64a3e8359c2e
Revises: magic_link_tokens
Create Date: 2026-02-13 09:45:13.359089

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '64a3e8359c2e'
down_revision = 'magic_link_tokens'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('professional_leads',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=160), nullable=True),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('city', sa.String(length=120), nullable=True),
    sa.Column('profession', sa.String(length=120), nullable=False),
    sa.Column('organization', sa.String(length=160), nullable=True),
    sa.Column('availability', sa.String(length=80), nullable=True),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('source', sa.String(length=80), nullable=True),
    sa.Column('locale', sa.String(length=10), nullable=True),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.Column('user_agent', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('professional_leads', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_professional_leads_city'), ['city'], unique=False)
        batch_op.create_index(batch_op.f('ix_professional_leads_email'), ['email'], unique=False)
        batch_op.create_index(batch_op.f('ix_professional_leads_profession'), ['profession'], unique=False)


def downgrade():
    with op.batch_alter_table('professional_leads', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_professional_leads_profession'))
        batch_op.drop_index(batch_op.f('ix_professional_leads_email'))
        batch_op.drop_index(batch_op.f('ix_professional_leads_city'))

    op.drop_table('professional_leads')
