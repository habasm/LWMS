"""Preserve consumed/discarded resource history and archive depleted stock."""
from alembic import op
import sqlalchemy as sa
revision='0007_consumable_inventory_history';down_revision='0006_maintenance_workflow_history';branch_labels=None;depends_on=None
def upgrade():
    op.add_column('facility_resources',sa.Column('archived',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('equipment_usage_requests',sa.Column('usage_type',sa.String(20),nullable=False,server_default='consumed'))
def downgrade():
    op.drop_column('equipment_usage_requests','usage_type');op.drop_column('facility_resources','archived')
