"""Recipient export snapshots, encrypted and erased with the plan."""
from alembic import op
import sqlalchemy as sa
revision = '0002'
down_revision = '0001'


def upgrade():
    op.create_table('export_snapshots', sa.Column('id', sa.String(64), primary_key=True), sa.Column('owner', sa.String(64), nullable=False), sa.Column('plan_id', sa.String(36), nullable=False), sa.Column('payload', sa.LargeBinary, nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_export_snapshots_owner', 'export_snapshots', ['owner'])
    op.create_index('ix_export_snapshots_plan_id', 'export_snapshots', ['plan_id'])


def downgrade():
    op.drop_table('export_snapshots')
