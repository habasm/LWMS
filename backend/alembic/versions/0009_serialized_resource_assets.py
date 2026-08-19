"""Add individually traceable resource assets and maintenance asset links."""
from alembic import op
import sqlalchemy as sa

revision='0009_serialized_resource_assets'
down_revision='0008_assistant_maintenance_verification'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('resource_assets',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('resource_id',sa.Integer(),sa.ForeignKey('facility_resources.id'),nullable=False),
        sa.Column('identifier',sa.String(120),nullable=False),
        sa.Column('status',sa.String(30),nullable=False,server_default='available'),
        sa.Column('notes',sa.Text(),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index('ix_resource_assets_resource_id','resource_assets',['resource_id'])
    op.create_index('ix_resource_assets_identifier','resource_assets',['identifier'],unique=True)
    op.add_column('maintenance_requests',sa.Column('asset_id',sa.Integer(),nullable=True))
    op.create_foreign_key('fk_maintenance_requests_asset_id','maintenance_requests','resource_assets',['asset_id'],['id'])
    op.create_index('ix_maintenance_requests_asset_id','maintenance_requests',['asset_id'])
    bind=op.get_bind()
    resources=bind.execute(sa.text('SELECT id, quantity FROM facility_resources WHERE archived = :archived'),{'archived':False}).fetchall()
    for resource_id,quantity in resources:
        for number in range(1,(quantity or 0)+1):
            bind.execute(sa.text('INSERT INTO resource_assets (resource_id, identifier, status) VALUES (:resource_id, :identifier, :status)'),{'resource_id':resource_id,'identifier':f'LWMS-{resource_id}-{number:03d}','status':'available'})

def downgrade():
    op.drop_index('ix_maintenance_requests_asset_id',table_name='maintenance_requests')
    op.drop_constraint('fk_maintenance_requests_asset_id','maintenance_requests',type_='foreignkey')
    op.drop_column('maintenance_requests','asset_id')
    op.drop_index('ix_resource_assets_identifier',table_name='resource_assets')
    op.drop_index('ix_resource_assets_resource_id',table_name='resource_assets')
    op.drop_table('resource_assets')
