"""Route public staff requests to their selected chair."""
from alembic import op
import sqlalchemy as sa

revision = '0019_store_chair_routing'
down_revision = '0018_standalone_stores'
branch_labels = None
depends_on = None


def upgrade():
    columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('store_requests')}
    if 'chair_id' not in columns:
        with op.batch_alter_table('store_requests') as batch:
            batch.add_column(sa.Column('chair_id', sa.Integer, nullable=True))
            batch.create_foreign_key('fk_store_requests_chair_id', 'users', ['chair_id'], ['id'])


def downgrade():
    with op.batch_alter_table('store_requests') as batch:
        batch.drop_constraint('fk_store_requests_chair_id', type_='foreignkey')
        batch.drop_column('chair_id')
