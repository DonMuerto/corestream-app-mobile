"""add team_members table

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-08-26 00:00:00.000000

Integrantes de un Equipo: un nombre suelto (sin cuenta en CoreStream) o,
opcionalmente, vinculado a un User real ya existente. Ver docstring de
app/models/team_member.py para el contexto completo.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'team_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('team_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_team_members_created_at', 'team_members', ['created_at'])
    op.create_index('ix_team_members_team_id', 'team_members', ['team_id'])
    op.create_index('ix_team_members_user_id', 'team_members', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_team_members_user_id', table_name='team_members')
    op.drop_index('ix_team_members_team_id', table_name='team_members')
    op.drop_index('ix_team_members_created_at', table_name='team_members')
    op.drop_table('team_members')
