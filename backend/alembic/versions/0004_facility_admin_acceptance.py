"""Add facility-admin assignments and resource verification fields."""
from alembic import op
import sqlalchemy as sa

revision = '0004_facility_admin_acceptance'
down_revision = '0003_facility_resources'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('assigned_facility_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_users_assigned_facility', 'users', 'facilities', ['assigned_facility_id'], ['id'])
    op.add_column('facility_resources', sa.Column('accepted', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('facility_resources', sa.Column('checked_by_id', sa.Integer(), nullable=True))
    op.add_column('facility_resources', sa.Column('checked_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key('fk_resources_checked_by', 'facility_resources', 'users', ['checked_by_id'], ['id'])

def downgrade():
    op.drop_constraint('fk_resources_checked_by', 'facility_resources', type_='foreignkey')
    op.drop_column('facility_resources', 'checked_at')
    op.drop_column('facility_resources', 'checked_by_id')
    op.drop_column('facility_resources', 'accepted')
    op.drop_constraint('fk_users_assigned_facility', 'users', type_='foreignkey')
    op.drop_column('users', 'assigned_facility_id')
