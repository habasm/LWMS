"""Track the exact delivery lot for each material issue and return."""
from alembic import op
import sqlalchemy as sa

revision = '0017_store_allocations'
down_revision = '0016_workshop_store'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('store_allocations',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('line_id', sa.Integer, sa.ForeignKey('store_request_lines.id'), nullable=False),
        sa.Column('lot_id', sa.Integer, sa.ForeignKey('store_lots.id'), nullable=False),
        sa.Column('quantity', sa.Integer, nullable=False), sa.Column('returned', sa.Integer, nullable=False))
    op.create_index('ix_store_allocations_line_id', 'store_allocations', ['line_id'])
    op.create_index('ix_store_allocations_lot_id', 'store_allocations', ['lot_id'])

def downgrade():
    op.drop_table('store_allocations')
