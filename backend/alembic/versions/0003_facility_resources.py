"""Add flexible facility resource inventory."""
from alembic import op
import sqlalchemy as sa
revision='0003_facility_resources';down_revision='0002_user_password_change_flag';branch_labels=None;depends_on=None
def upgrade():
    op.create_table('facility_resources',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('facility_id',sa.Integer(),sa.ForeignKey('facilities.id'),nullable=False),sa.Column('name',sa.String(150),nullable=False),sa.Column('category',sa.String(80),nullable=False),sa.Column('quantity',sa.Integer(),nullable=False,server_default='1'),sa.Column('properties',sa.JSON(),nullable=False))
    op.create_index('ix_facility_resources_facility_id','facility_resources',['facility_id'])
def downgrade():
    op.drop_table('facility_resources')
