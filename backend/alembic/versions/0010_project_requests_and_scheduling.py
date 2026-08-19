"""Add project approval workflow and class/project scheduling fields."""
from alembic import op
import sqlalchemy as sa

revision='0010_project_requests_and_scheduling'
down_revision='0009_serialized_resource_assets'
branch_labels=None
depends_on=None

def upgrade():
    with op.batch_alter_table('projects') as batch:
        batch.add_column(sa.Column('stakeholder_name',sa.String(160),nullable=True));batch.add_column(sa.Column('organization',sa.String(180),nullable=True));batch.add_column(sa.Column('contact_email',sa.String(255),nullable=True));batch.add_column(sa.Column('requested_by_id',sa.Integer(),nullable=True));batch.add_column(sa.Column('approval_status',sa.String(20),nullable=False,server_default='approved'));batch.add_column(sa.Column('approval_notes',sa.Text(),nullable=True));batch.add_column(sa.Column('approved_by_id',sa.Integer(),nullable=True));batch.add_column(sa.Column('approved_at',sa.DateTime(timezone=True),nullable=True));batch.create_foreign_key('fk_projects_requested_by','users',['requested_by_id'],['id']);batch.create_foreign_key('fk_projects_approved_by','users',['approved_by_id'],['id'])
    with op.batch_alter_table('schedules') as batch:
        batch.add_column(sa.Column('schedule_type',sa.String(20),nullable=False,server_default='class'));batch.add_column(sa.Column('project_id',sa.Integer(),nullable=True));batch.add_column(sa.Column('notes',sa.Text(),nullable=True));batch.create_foreign_key('fk_schedules_project','projects',['project_id'],['id'])

def downgrade():
    with op.batch_alter_table('schedules') as batch:
        batch.drop_constraint('fk_schedules_project',type_='foreignkey');batch.drop_column('notes');batch.drop_column('project_id');batch.drop_column('schedule_type')
    with op.batch_alter_table('projects') as batch:
        batch.drop_constraint('fk_projects_approved_by',type_='foreignkey');batch.drop_constraint('fk_projects_requested_by',type_='foreignkey')
        for column in ('approved_at','approved_by_id','approval_notes','approval_status','requested_by_id','contact_email','organization','stakeholder_name'): batch.drop_column(column)
