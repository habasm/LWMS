"""Add facility-assistant repair verification and linked follow-up requests."""
from alembic import op
import sqlalchemy as sa
revision='0008_assistant_maintenance_verification';down_revision='0007_consumable_inventory_history';branch_labels=None;depends_on=None
def upgrade():
    op.add_column('maintenance_requests',sa.Column('assistant_verification',sa.String(30),nullable=True))
    op.add_column('maintenance_requests',sa.Column('verification_notes',sa.Text(),nullable=True))
    op.add_column('maintenance_requests',sa.Column('verified_at',sa.DateTime(timezone=True),nullable=True))
    op.add_column('maintenance_requests',sa.Column('parent_request_id',sa.Integer(),sa.ForeignKey('maintenance_requests.id'),nullable=True))
def downgrade():
    op.drop_column('maintenance_requests','parent_request_id');op.drop_column('maintenance_requests','verified_at');op.drop_column('maintenance_requests','verification_notes');op.drop_column('maintenance_requests','assistant_verification')
