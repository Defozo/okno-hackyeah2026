"""Prevent an export job from writing into a deleted plan."""
from alembic import op

revision = '0003'
down_revision = '0002'


def upgrade():
    with op.batch_alter_table('export_snapshots') as batch:
        batch.create_foreign_key('fk_export_plan', 'plans', ['plan_id'], ['id'], ondelete='CASCADE')


def downgrade():
    with op.batch_alter_table('export_snapshots') as batch:
        batch.drop_constraint('fk_export_plan', type_='foreignkey')
