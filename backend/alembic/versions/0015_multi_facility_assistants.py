"""Allow assistants to hold multiple active and pending facilities.

Revision ID: 0015_multi_facility_assistants
Revises: 0014_usage_request_serials
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa

revision = '0015_multi_facility_assistants'
down_revision = '0014_usage_request_serials'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column['name'] for column in sa.inspect(bind).get_columns('users')}
    if 'assigned_facility_ids' not in columns:
        op.add_column('users', sa.Column('assigned_facility_ids', sa.JSON(), nullable=True))
    if 'pending_facility_ids' not in columns:
        op.add_column('users', sa.Column('pending_facility_ids', sa.JSON(), nullable=True))
    op.execute("UPDATE users SET assigned_facility_ids = json_array(assigned_facility_id) WHERE assigned_facility_ids IS NULL AND assigned_facility_id IS NOT NULL")
    op.execute("UPDATE users SET assigned_facility_ids = '[]' WHERE assigned_facility_ids IS NULL")
    op.execute("UPDATE users SET pending_facility_ids = '[]' WHERE pending_facility_ids IS NULL")


def downgrade() -> None:
    op.drop_column('users', 'pending_facility_ids')
    op.drop_column('users', 'assigned_facility_ids')
