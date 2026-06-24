"""add proxy tables

Revision ID: a1b2c3d4e5f6
Revises: 83ad5181ce0b
Create Date: 2026-06-24 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '83ad5181ce0b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'proxy_providers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('label', sa.String(), nullable=False),
        sa.Column('api_key', sa.String(), nullable=True),
        sa.Column('api_user', sa.String(), nullable=True),
        sa.Column('api_pass', sa.String(), nullable=True),
        sa.Column('proxy_host', sa.String(), nullable=True),
        sa.Column('proxy_port', sa.Integer(), nullable=True),
        sa.Column('proxy_username', sa.String(), nullable=True),
        sa.Column('proxy_password', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'proxies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=True),
        sa.Column('host', sa.String(), nullable=False),
        sa.Column('port', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(), nullable=True),
        sa.Column('password', sa.String(), nullable=True),
        sa.Column('geo', sa.String(length=5), nullable=True),
        sa.Column('proxy_type', sa.String(), nullable=False, server_default='http'),
        sa.Column('is_rotating', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('status', sa.String(), nullable=False, server_default='untested'),
        sa.Column('last_tested', sa.DateTime(), nullable=True),
        sa.Column('exit_ip', sa.String(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['provider_id'], ['proxy_providers.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_proxies_geo', 'proxies', ['geo'], unique=False)
    op.create_index('idx_proxies_status', 'proxies', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_proxies_status', table_name='proxies')
    op.drop_index('idx_proxies_geo', table_name='proxies')
    op.drop_table('proxies')
    op.drop_table('proxy_providers')
