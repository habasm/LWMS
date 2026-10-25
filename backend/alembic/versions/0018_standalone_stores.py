"""Move workshop material stock into standalone stores."""
from alembic import op
import sqlalchemy as sa

revision = '0018_standalone_stores'
down_revision = '0017_store_allocations'
branch_labels = None
depends_on = None

def upgrade():
    bind=op.get_bind()
    tables=set(sa.inspect(bind).get_table_names())
    if 'stores' not in tables:
        op.create_table('stores',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(150), nullable=False, unique=True),
        sa.Column('location', sa.String(150), nullable=False),
        sa.Column('description', sa.Text),
        sa.Column('manager_id', sa.Integer, sa.ForeignKey('users.id')),
        sa.Column('created_by_id', sa.Integer, sa.ForeignKey('users.id')),
        sa.Column('review_status', sa.String(20), nullable=False, server_default='unassigned'),
        sa.Column('revision', sa.Integer, nullable=False, server_default='1'),
        sa.Column('accepted_by_id', sa.Integer, sa.ForeignKey('users.id')),
        sa.Column('accepted_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()))
    else:
        existing={c['name'] for c in sa.inspect(bind).get_columns('stores')}
        for column in (sa.Column('review_status',sa.String(20),nullable=False,server_default='unassigned'),
                       sa.Column('revision',sa.Integer,nullable=False,server_default='1'),
                       sa.Column('accepted_by_id',sa.Integer),
                       sa.Column('accepted_at',sa.DateTime(timezone=True))):
            if column.name not in existing: op.add_column('stores',column)
    if 'store_id' not in {c['name'] for c in sa.inspect(bind).get_columns('store_lots')}:
        op.add_column('store_lots', sa.Column('store_id', sa.Integer))
    request_columns={c['name'] for c in sa.inspect(bind).get_columns('store_requests')}
    if 'store_id' not in request_columns: op.add_column('store_requests', sa.Column('store_id', sa.Integer))
    if 'requester_position' not in request_columns: op.add_column('store_requests', sa.Column('requester_position', sa.String(20), nullable=False, server_default='staff'))
    if 'store_id' not in {c['name'] for c in sa.inspect(bind).get_columns('store_events')}:
        op.add_column('store_events', sa.Column('store_id', sa.Integer))
    if not any(index['name']=='ix_store_events_store_id' for index in sa.inspect(bind).get_indexes('store_events')):
        op.create_index('ix_store_events_store_id', 'store_events', ['store_id'])
    if 'store_movements' not in tables:
        op.create_table('store_movements',
        sa.Column('id',sa.Integer,primary_key=True),
        sa.Column('store_id',sa.Integer,sa.ForeignKey('stores.id'),nullable=False),
        sa.Column('item_id',sa.Integer,sa.ForeignKey('store_items.id'),nullable=False),
        sa.Column('lot_id',sa.Integer,sa.ForeignKey('store_lots.id'),nullable=False),
        sa.Column('request_id',sa.Integer,sa.ForeignKey('store_requests.id')),
        sa.Column('actor_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),
        sa.Column('action',sa.String(20),nullable=False),
        sa.Column('quantity',sa.Integer,nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now()))
    if not any(index['name']=='ix_store_movements_store_id' for index in sa.inspect(bind).get_indexes('store_movements')):
        op.create_index('ix_store_movements_store_id','store_movements',['store_id'])
    facility_ids = bind.execute(sa.text('SELECT facility_id FROM store_lots WHERE facility_id IS NOT NULL UNION SELECT facility_id FROM store_requests WHERE facility_id IS NOT NULL')).scalars().all()
    for facility_id in facility_ids:
        facility = bind.execute(sa.text('SELECT name, location FROM facilities WHERE id=:id'), {'id':facility_id}).mappings().first()
        if not facility: continue
        name = f"{facility['name'][:130]} Materials Store"
        store_id = bind.execute(sa.text('INSERT INTO stores (name, location) VALUES (:name, :location) RETURNING id'), {'name':name,'location':facility['location']}).scalar_one()
        bind.execute(sa.text('UPDATE store_lots SET store_id=:store_id WHERE facility_id=:facility_id'), {'store_id':store_id,'facility_id':facility_id})
        bind.execute(sa.text('UPDATE store_requests SET store_id=:store_id WHERE facility_id=:facility_id'), {'store_id':store_id,'facility_id':facility_id})
    missing = bind.execute(sa.text('SELECT COUNT(*) FROM store_requests WHERE store_id IS NULL')).scalar()
    if missing:
        store_id = bind.execute(sa.text("INSERT INTO stores (name, location) VALUES ('Legacy Materials Store', 'Unassigned') RETURNING id")).scalar_one()
        bind.execute(sa.text('UPDATE store_requests SET store_id=:id WHERE store_id IS NULL'), {'id':store_id})
    bind.execute(sa.text("INSERT INTO store_movements (store_id, item_id, lot_id, actor_id, action, quantity, created_at) SELECT store_id, item_id, id, COALESCE(accepted_by_id,received_by_id), 'receipt', quantity, COALESCE(accepted_at,created_at) FROM store_lots WHERE status='accepted' AND store_id IS NOT NULL"))
    with op.batch_alter_table('store_lots') as batch:
        batch.alter_column('facility_id', existing_type=sa.Integer(), nullable=True)
        batch.alter_column('store_id', existing_type=sa.Integer(), nullable=False)
        if not any('store_id' in fk['constrained_columns'] for fk in sa.inspect(bind).get_foreign_keys('store_lots')):
            batch.create_foreign_key('fk_store_lots_store_id','stores',['store_id'],['id'])
        batch.create_index('ix_store_lots_store_id', ['store_id'])
    with op.batch_alter_table('store_requests') as batch:
        batch.alter_column('store_id', existing_type=sa.Integer(), nullable=False)
        if not any('store_id' in fk['constrained_columns'] for fk in sa.inspect(bind).get_foreign_keys('store_requests')):
            batch.create_foreign_key('fk_store_requests_store_id','stores',['store_id'],['id'])
        batch.create_index('ix_store_requests_store_id', ['store_id'])
    if not any('store_id' in fk['constrained_columns'] for fk in sa.inspect(bind).get_foreign_keys('store_events')):
        with op.batch_alter_table('store_events') as batch:
            batch.create_foreign_key('fk_store_events_store_id','stores',['store_id'],['id'])
    if not any('accepted_by_id' in fk['constrained_columns'] for fk in sa.inspect(bind).get_foreign_keys('stores')):
        with op.batch_alter_table('stores') as batch:
            batch.create_foreign_key('fk_stores_accepted_by_id','users',['accepted_by_id'],['id'])

def downgrade():
    raise NotImplementedError('Store ownership migration cannot safely restore facility ownership')
