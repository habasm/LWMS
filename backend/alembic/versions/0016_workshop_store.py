"""Workshop store receipts, stock, requests, and audit trail."""
from alembic import op
import sqlalchemy as sa

revision = '0016_workshop_store'
down_revision = '0015_multi_facility_assistants'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('store_items',
        sa.Column('id', sa.Integer, primary_key=True), sa.Column('name', sa.String(150), nullable=False),
        sa.Column('category', sa.String(80), nullable=False), sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('unit', sa.String(40), nullable=False), sa.Column('description', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index('ix_store_items_name', 'store_items', ['name'])
    op.create_table('store_lots',
        sa.Column('id', sa.Integer, primary_key=True), sa.Column('item_id', sa.Integer, sa.ForeignKey('store_items.id'), nullable=False),
        sa.Column('facility_id', sa.Integer, sa.ForeignKey('facilities.id'), nullable=False),
        sa.Column('quantity', sa.Integer, nullable=False), sa.Column('available', sa.Integer, nullable=False),
        sa.Column('status', sa.String(20), nullable=False), sa.Column('purchase_reference', sa.String(120), nullable=False),
        sa.Column('supplier', sa.String(150)), sa.Column('received_by_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('accepted_by_id', sa.Integer, sa.ForeignKey('users.id')),
        sa.Column('accepted_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index('ix_store_lots_item_id', 'store_lots', ['item_id'])
    op.create_index('ix_store_lots_facility_id', 'store_lots', ['facility_id'])
    op.create_table('store_requests',
        sa.Column('id', sa.Integer, primary_key=True), sa.Column('reference', sa.String(40), nullable=False, unique=True),
        sa.Column('requester_name', sa.String(150), nullable=False), sa.Column('requester_contact', sa.String(160), nullable=False),
        sa.Column('department', sa.String(150), nullable=False), sa.Column('purpose', sa.Text, nullable=False),
        sa.Column('kind', sa.String(20), nullable=False), sa.Column('status', sa.String(30), nullable=False),
        sa.Column('facility_id', sa.Integer, sa.ForeignKey('facilities.id')),
        sa.Column('chair_name', sa.String(150)), sa.Column('dean_id', sa.Integer, sa.ForeignKey('users.id')),
        sa.Column('assigned_by_id', sa.Integer, sa.ForeignKey('users.id')),
        sa.Column('issued_by_id', sa.Integer, sa.ForeignKey('users.id')),
        sa.Column('issued_at', sa.DateTime(timezone=True)), sa.Column('due_at', sa.DateTime(timezone=True)),
        sa.Column('signed_document', sa.String(255)), sa.Column('notes', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index('ix_store_requests_reference', 'store_requests', ['reference'], unique=True)
    op.create_table('store_request_lines',
        sa.Column('id', sa.Integer, primary_key=True), sa.Column('request_id', sa.Integer, sa.ForeignKey('store_requests.id'), nullable=False),
        sa.Column('item_id', sa.Integer, sa.ForeignKey('store_items.id'), nullable=False),
        sa.Column('quantity', sa.Integer, nullable=False), sa.Column('returned', sa.Integer, nullable=False))
    op.create_index('ix_store_request_lines_request_id', 'store_request_lines', ['request_id'])
    op.create_table('store_events',
        sa.Column('id', sa.Integer, primary_key=True), sa.Column('request_id', sa.Integer, sa.ForeignKey('store_requests.id')),
        sa.Column('lot_id', sa.Integer, sa.ForeignKey('store_lots.id')),
        sa.Column('actor_id', sa.Integer, sa.ForeignKey('users.id')),
        sa.Column('action', sa.String(40), nullable=False), sa.Column('notes', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index('ix_store_events_request_id', 'store_events', ['request_id'])
    op.create_index('ix_store_events_lot_id', 'store_events', ['lot_id'])

def downgrade():
    op.drop_table('store_events')
    op.drop_table('store_request_lines')
    op.drop_table('store_requests')
    op.drop_table('store_lots')
    op.drop_table('store_items')
