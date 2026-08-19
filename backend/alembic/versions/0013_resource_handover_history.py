"""resource handover history

Revision ID: 0013_resource_handover_history
Revises: 0012_open_instructor_names
"""
from alembic import op
import sqlalchemy as sa

revision='0013_resource_handover_history'
down_revision='0012_open_instructor_names'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind();columns={c['name'] for c in sa.inspect(bind).get_columns('facility_resources')}
    if 'review_status' not in columns: op.add_column('facility_resources',sa.Column('review_status',sa.String(20),nullable=False,server_default='pending'))
    if 'review_notes' not in columns: op.add_column('facility_resources',sa.Column('review_notes',sa.Text(),nullable=True))
    if 'revision' not in columns: op.add_column('facility_resources',sa.Column('revision',sa.Integer(),nullable=False,server_default='1'))
    if 'submitted_by_id' not in columns:
        # SQLite cannot add a foreign-key constraint with ALTER TABLE. The ORM
        # relationship remains identical; PostgreSQL receives the constraint.
        column=sa.Column('submitted_by_id',sa.Integer(),nullable=True) if bind.dialect.name=='sqlite' else sa.Column('submitted_by_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=True)
        op.add_column('facility_resources',column)
    if 'last_accepted_snapshot' not in columns: op.add_column('facility_resources',sa.Column('last_accepted_snapshot',sa.JSON(),nullable=True))
    indexes={i['name'] for i in sa.inspect(bind).get_indexes('facility_resources')}
    if 'ix_facility_resources_review_status' not in indexes: op.create_index('ix_facility_resources_review_status','facility_resources',['review_status'])
    tables=set(sa.inspect(bind).get_table_names())
    if 'resource_history' not in tables:
        op.create_table('resource_history',
            sa.Column('id',sa.Integer(),primary_key=True),sa.Column('resource_id',sa.Integer(),sa.ForeignKey('facility_resources.id'),nullable=False),
            sa.Column('facility_id',sa.Integer(),sa.ForeignKey('facilities.id'),nullable=False),sa.Column('actor_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=True),
            sa.Column('action',sa.String(50),nullable=False),sa.Column('revision',sa.Integer(),nullable=False),sa.Column('notes',sa.Text(),nullable=True),
            sa.Column('before_snapshot',sa.JSON(),nullable=True),sa.Column('after_snapshot',sa.JSON(),nullable=True),
            sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
        op.create_index('ix_resource_history_resource_id','resource_history',['resource_id']);op.create_index('ix_resource_history_facility_id','resource_history',['facility_id'])
    op.execute("UPDATE facility_resources SET review_status=CASE WHEN accepted=1 THEN 'accepted' ELSE 'pending' END WHERE review_status IS NULL OR review_status='pending'")

def downgrade():
    op.drop_table('resource_history')
    for name in ('last_accepted_snapshot','submitted_by_id','revision','review_notes','review_status'): op.drop_column('facility_resources',name)
