"""Add serial selections to equipment usage requests.

Revision ID: 0014_usage_request_serials
Revises: 0013_resource_handover_history
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa

revision = '0014_usage_request_serials'
down_revision = '0013_resource_handover_history'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('equipment_usage_requests', sa.Column('asset_ids', sa.JSON(), nullable=True))
    op.add_column('equipment_usage_requests', sa.Column('asset_identifiers', sa.JSON(), nullable=True))
    op.execute("UPDATE equipment_usage_requests SET asset_ids = '[]' WHERE asset_ids IS NULL")
    op.execute("UPDATE equipment_usage_requests SET asset_identifiers = '[]' WHERE asset_identifiers IS NULL")


def downgrade() -> None:
    op.drop_column('equipment_usage_requests', 'asset_identifiers')
    op.drop_column('equipment_usage_requests', 'asset_ids')
