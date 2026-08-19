"""Add equipment usage request approval workflow."""
from alembic import op
import sqlalchemy as sa

revision='0005_equipment_usage_requests'
down_revision='0004_facility_admin_acceptance'
branch_labels=None
depends_on=None

def upgrade():
    status=sa.Enum('pending','approved','assigned','in_progress','completed','rejected',name='status')
    op.create_table('equipment_usage_requests',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('resource_id',sa.Integer(),sa.ForeignKey('facility_resources.id'),nullable=False),
        sa.Column('facility_id',sa.Integer(),sa.ForeignKey('facilities.id'),nullable=False),
        sa.Column('requester_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('quantity',sa.Integer(),nullable=False),
        sa.Column('purpose',sa.Text(),nullable=False),
        sa.Column('status',status,nullable=False,server_default='pending'),
        sa.Column('approver_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=True),
        sa.Column('decision_notes',sa.Text(),nullable=True),
        sa.Column('decided_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index('ix_equipment_usage_requests_resource_id','equipment_usage_requests',['resource_id'])
    op.create_index('ix_equipment_usage_requests_facility_id','equipment_usage_requests',['facility_id'])

def downgrade():
    op.drop_table('equipment_usage_requests')
