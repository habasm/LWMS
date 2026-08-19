"""Allow schedule instructors to be entered as open text names."""
from alembic import op
import sqlalchemy as sa

revision='0012_open_instructor_names'
down_revision='0011_recurring_weekday_schedules'
branch_labels=None
depends_on=None

def upgrade():
    bind=op.get_bind()
    existing={column['name'] for column in sa.inspect(bind).get_columns('schedules')}
    if 'instructor_name' not in existing: op.add_column('schedules',sa.Column('instructor_name',sa.String(160),nullable=True))
    bind.execute(sa.text('UPDATE schedules SET instructor_name = (SELECT full_name FROM users WHERE users.id = schedules.instructor_id) WHERE instructor_id IS NOT NULL'))

def downgrade():
    op.drop_column('schedules','instructor_name')
