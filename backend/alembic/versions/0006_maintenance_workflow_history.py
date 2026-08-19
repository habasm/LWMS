"""Extend maintenance requests and add immutable workflow history."""
from alembic import op
import sqlalchemy as sa
revision='0006_maintenance_workflow_history';down_revision='0005_equipment_usage_requests';branch_labels=None;depends_on=None
def upgrade():
    op.add_column('maintenance_requests',sa.Column('resource_id',sa.Integer(),sa.ForeignKey('facility_resources.id'),nullable=True))
    op.add_column('maintenance_requests',sa.Column('facility_id',sa.Integer(),sa.ForeignKey('facilities.id'),nullable=True))
    op.add_column('maintenance_requests',sa.Column('resolution',sa.String(30),nullable=True))
    op.create_table('maintenance_history',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('request_id',sa.Integer(),sa.ForeignKey('maintenance_requests.id'),nullable=False),sa.Column('actor_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('action',sa.String(50),nullable=False),sa.Column('from_status',sa.String(30),nullable=True),sa.Column('to_status',sa.String(30),nullable=True),sa.Column('notes',sa.Text(),nullable=True),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index('ix_maintenance_history_request_id','maintenance_history',['request_id'])
def downgrade():
    op.drop_table('maintenance_history');op.drop_column('maintenance_requests','resolution');op.drop_column('maintenance_requests','facility_id');op.drop_column('maintenance_requests','resource_id')
