"""Initial LWMS domain schema.

Revision ID: 0001_initial_schema
Revises:
"""
from alembic import op
from app.core.database import Base
import app.models
revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None
def upgrade():
    Base.metadata.create_all(op.get_bind())
def downgrade():
    Base.metadata.drop_all(op.get_bind())
