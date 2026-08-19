"""Require provisioned users to change their first password."""
from alembic import op
import sqlalchemy as sa
revision='0002_user_password_change_flag'
down_revision='0001_initial_schema'
branch_labels=None
depends_on=None
def upgrade():
    op.add_column('users',sa.Column('must_change_password',sa.Boolean(),nullable=False,server_default=sa.false()))
def downgrade():
    op.drop_column('users','must_change_password')
