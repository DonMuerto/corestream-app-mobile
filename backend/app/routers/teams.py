"""
Router de Equipos (Team).

Un Team agrupa Épicas (posiblemente repartidas entre varias Application)
para poder evaluar el trabajo de un equipo de estudiantes como una unidad.
Ver docstring de app/models/team.py para el contexto completo (software
factory con convenio DuocUC/UTEM).

Solo ADMIN y TEAM_LEADER gestionan equipos — los mismos roles que ya
gestionan aplicaciones y épicas (ver docs/RBAC.md). Los estudiantes
(DEVELOPER) no interactúan con este agrupador en absoluto.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import require_role
from app.models import Epic, Team, Ticket, User, UserRole
from app.schemas import EpicResponse, TeamCreate, TeamDetailResponse, TeamResponse, TeamUpdate

_MANAGERS = [UserRole.ADMIN, UserRole.TEAM_LEADER]

router = APIRouter(prefix="/api/teams", tags=["Equipos"])


def _epic_progress(epic: Epic) -> tuple[int, int]:
    """Retorna (total_tickets, completed_tickets) para una épica ya cargada."""
    total = len(epic.tickets)
    completed = sum(
        1 for t in epic.tickets
        if (t.status.value if hasattr(t.status, "value") else str(t.status)) in ("COMPLETED", "DONE")
    )
    return total, completed


def _team_response(team: Team) -> TeamResponse:
    total_tickets = 0
    completed_tickets = 0
    for epic in team.epics:
        t, c = _epic_progress(epic)
        total_tickets += t
        completed_tickets += c

    progress = round((completed_tickets / total_tickets) * 100, 2) if total_tickets > 0 else 0.0

    view = TeamResponse.model_validate(team)
    view.epic_count = len(team.epics)
    view.total_tickets = total_tickets
    view.completed_tickets = completed_tickets
    view.progress = progress
    return view


@router.get(
    "/",
    response_model=List[TeamResponse],
    summary="Listar equipos",
    description="Lista todos los equipos con sus estadísticas agregadas (sin el detalle de tickets)",
)
async def list_teams(
    current_user: User = Depends(require_role(_MANAGERS)),
    db: AsyncSession = Depends(get_db),
) -> List[TeamResponse]:
    result = await db.execute(
        select(Team)
        .options(selectinload(Team.epics).selectinload(Epic.tickets))
        .order_by(Team.name.asc())
    )
    teams = result.unique().scalars().all()
    return [_team_response(team) for team in teams]


@router.post(
    "/",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear equipo",
    description="Crea un nuevo equipo (agrupador de épicas)",
)
async def create_team(
    data: TeamCreate,
    current_user: User = Depends(require_role(_MANAGERS)),
    db: AsyncSession = Depends(get_db),
) -> TeamResponse:
    existing = await db.execute(select(Team).where(Team.name == data.name))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un equipo con el nombre '{data.name}'",
        )

    team = Team(**data.model_dump())
    db.add(team)
    await db.commit()
    await db.refresh(team)

    # Equipo recién creado: nunca tiene épicas todavía, así que no hace
    # falta (ni se puede, con lazy="raise_on_sql") tocar team.epics aquí.
    view = TeamResponse.model_validate(team)
    view.epic_count = 0
    view.total_tickets = 0
    view.completed_tickets = 0
    view.progress = 0.0
    return view


@router.get(
    "/{team_id}",
    response_model=TeamDetailResponse,
    summary="Obtener detalle de un equipo",
    description="Recupera un equipo con todas sus épicas (y tickets) para la vista de seguimiento por equipo",
)
async def get_team(
    team_id: UUID,
    current_user: User = Depends(require_role(_MANAGERS)),
    db: AsyncSession = Depends(get_db),
) -> TeamDetailResponse:
    result = await db.execute(
        select(Team)
        .where(Team.id == team_id)
        .options(
            selectinload(Team.epics).selectinload(Epic.application),
            selectinload(Team.epics).selectinload(Epic.team),
            selectinload(Team.epics).selectinload(Epic.tickets).selectinload(Ticket.subtasks),
            selectinload(Team.epics).selectinload(Epic.tickets).selectinload(Ticket.assignee).selectinload(User.role),
        )
    )
    team = result.unique().scalar_one_or_none()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equipo con ID {team_id} no encontrado",
        )

    base = _team_response(team)
    epic_views = []
    for epic in team.epics:
        total, completed = _epic_progress(epic)
        epic_view = EpicResponse.model_validate(epic)
        epic_view.total_tickets = total
        epic_view.completed_tickets = completed
        epic_view.progress = round((completed / total) * 100, 2) if total > 0 else 0.0
        epic_views.append(epic_view)

    return TeamDetailResponse(**base.model_dump(), epics=epic_views)


@router.put(
    "/{team_id}",
    response_model=TeamResponse,
    summary="Actualizar equipo",
    description="Renombra o actualiza la descripción de un equipo",
)
async def update_team(
    team_id: UUID,
    data: TeamUpdate,
    current_user: User = Depends(require_role(_MANAGERS)),
    db: AsyncSession = Depends(get_db),
) -> TeamResponse:
    result = await db.execute(
        select(Team).where(Team.id == team_id).options(selectinload(Team.epics).selectinload(Epic.tickets))
    )
    team = result.unique().scalar_one_or_none()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equipo con ID {team_id} no encontrado",
        )

    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] != team.name:
        existing = await db.execute(select(Team).where(Team.name == update_data["name"]))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe un equipo con el nombre '{update_data['name']}'",
            )

    for field, value in update_data.items():
        setattr(team, field, value)

    await db.commit()
    await db.refresh(team, attribute_names=["epics"])
    return _team_response(team)


@router.delete(
    "/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar equipo",
    description="Elimina un equipo. Las épicas asociadas NO se eliminan, solo quedan sin equipo asignado.",
)
async def delete_team(
    team_id: UUID,
    current_user: User = Depends(require_role(_MANAGERS)),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Team).where(Team.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Equipo con ID {team_id} no encontrado",
        )

    await db.delete(team)
    await db.commit()
