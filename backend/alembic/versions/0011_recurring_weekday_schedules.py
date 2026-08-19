"""Add recurring weekdays, active date range, and daily time gap to schedules."""
from alembic import op
import sqlalchemy as sa
import json
from datetime import datetime

revision='0011_recurring_weekday_schedules'
down_revision='0010_project_requests_and_scheduling'
branch_labels=None
depends_on=None

def upgrade():
    existing={column['name'] for column in sa.inspect(op.get_bind()).get_columns('schedules')}
    with op.batch_alter_table('schedules') as batch:
        if 'schedule_days' not in existing: batch.add_column(sa.Column('schedule_days',sa.JSON(),nullable=False,server_default='[]'))
        if 'period_start' not in existing: batch.add_column(sa.Column('period_start',sa.Date(),nullable=True))
        if 'period_end' not in existing: batch.add_column(sa.Column('period_end',sa.Date(),nullable=True))
        if 'time_from' not in existing: batch.add_column(sa.Column('time_from',sa.Time(),nullable=True))
        if 'time_to' not in existing: batch.add_column(sa.Column('time_to',sa.Time(),nullable=True))
    bind=op.get_bind()
    rows=bind.execute(sa.text('SELECT id, start_at, end_at FROM schedules WHERE period_start IS NULL')).fetchall()
    update_statement=sa.text('UPDATE schedules SET schedule_days=:days, period_start=:period_start, period_end=:period_end, time_from=:time_from, time_to=:time_to WHERE id=:id').bindparams(sa.bindparam('period_start',type_=sa.Date()),sa.bindparam('period_end',type_=sa.Date()),sa.bindparam('time_from',type_=sa.Time()),sa.bindparam('time_to',type_=sa.Time()))
    for row in rows:
        start=row.start_at;end=row.end_at
        if isinstance(start,str): start=datetime.fromisoformat(start)
        if isinstance(end,str): end=datetime.fromisoformat(end)
        bind.execute(update_statement,{'days':json.dumps([start.weekday()]),'period_start':start.date(),'period_end':end.date(),'time_from':start.time(),'time_to':end.time(),'id':row.id})

def downgrade():
    with op.batch_alter_table('schedules') as batch:
        batch.drop_column('time_to');batch.drop_column('time_from');batch.drop_column('period_end');batch.drop_column('period_start');batch.drop_column('schedule_days')
