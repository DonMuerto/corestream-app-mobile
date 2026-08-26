"""add teams table and epics.team_id

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-08-25 00:00:00.000000

Agrupador liviano "Team" para poder trackear y evaluar el trabajo de un
equipo de estudiantes (software factory con convenio DuocUC/UTEM) como una
unidad, aunque sus épicas estén repartidas entre distintas Application. Ver
docstring de app/models/team.py para el contexto completo.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'teams',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=1000), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index('ix_teams_created_at', 'teams', ['created_at'])
    op.create_index('ix_teams_name', 'teams', ['name'])

    op.add_column('epics', sa.Column('team_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('ix_epics_team_id', 'epics', ['team_id'])
    op.create_foreign_key(
        'fk_epics_team_id_teams',
        'epics', 'teams',
        ['team_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_epics_team_id_teams', 'epics', type_='foreignkey')
    op.drop_index('ix_epics_team_id', table_name='epics')
    op.drop_column('epics', 'team_id')

    op.drop_index('ix_teams_name', table_name='teams')
    op.drop_index('ix_teams_created_at', table_name='teams')
    op.drop_table('teams')
