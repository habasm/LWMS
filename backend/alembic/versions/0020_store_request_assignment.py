"""Track which store man receives an approved material request."""
from alembic import op
import sqlalchemy as sa

revision = '0020_store_request_assignment'
down_revision = '0019_store_chair_routing'
branch_labels = None
depends_on = None


def upgrade():
    columns={column['name'] for column in sa.inspect(op.get_bind()).get_columns('store_requests')}
    if 'assigned_manager_id' not in columns:
        with op.batch_alter_table('store_requests') as batch:
            batch.add_column(sa.Column('assigned_manager_id',sa.Integer,nullable=True))
            batch.create_foreign_key('fk_store_requests_assigned_manager_id','users',['assigned_manager_id'],['id'])
    op.execute(sa.text("""UPDATE store_requests SET assigned_manager_id=COALESCE(issued_by_id,
        (SELECT manager_id FROM stores WHERE stores.id=store_requests.store_id))
        WHERE kind='consumable' AND status IN ('ready','issued') AND assigned_manager_id IS NULL"""))


def downgrade():
    with op.batch_alter_table('store_requests') as batch:
        batch.drop_constraint('fk_store_requests_assigned_manager_id',type_='foreignkey')
        batch.drop_column('assigned_manager_id')
