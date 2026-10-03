"""Encrypted private plans, idempotency and deletion tombstones."""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None


def upgrade():
    op.create_table('plans', sa.Column('id', sa.String(36), primary_key=True), sa.Column('owner', sa.String(64), nullable=False), sa.Column('version', sa.Integer, nullable=False), sa.Column('payload', sa.LargeBinary, nullable=False), sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_plans_owner', 'plans', ['owner'])
    op.create_index('ix_plans_updated_at', 'plans', ['updated_at'])
    op.create_table('operations', sa.Column('id', sa.String(64), primary_key=True), sa.Column('request_hash', sa.String(64), nullable=False), sa.Column('owner', sa.String(64), nullable=False), sa.Column('plan_id', sa.String(36)), sa.Column('response', sa.LargeBinary, nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_operations_owner', 'operations', ['owner'])
    op.create_index('ix_operations_plan_id', 'operations', ['plan_id'])
    op.create_table('tombstones', sa.Column('id', sa.String(36), primary_key=True), sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=False))


def downgrade():
    op.drop_table('operations')
    op.drop_table('plans')
    op.drop_table('tombstones')
