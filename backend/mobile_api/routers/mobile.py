"""
Router BFF para la app móvil (§5.1–5.4).

Prefijo: /mobile — endpoints de solo lectura que componen en el servidor lo
que cada pantalla necesita (una llamada por pantalla). No introducen reglas
de negocio nuevas: consultan los mismos modelos y respetan los mismos roles.
"""

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import Application, Epic, Subtask, Ticket, TicketEvent, TicketType, User
from app.models.incident import Incident
from app.services.ticket_permissions import get_role_name
from mobile_api.schemas.mobile import (
    ApplicationBoardResponse,
    ApplicationBrief,
    AttentionItem,
    EpicBoard,
    EpicBrief,
    IncidentSummary,
    MemberWorkload,
    MobileDashboardResponse,
    ProjectSummary,
    SubtaskBrief,
    TicketDetailResponse,
    TicketEventDetail,
    TicketFull,
    TicketPermissions,
    TicketSummary,
    TimerState,
    UserBrief,
)
from mobile_api.services.permission_service import LEAD_ROLES, compute_ticket_permissions

router = APIRouter(prefix="/mobile", tags=["Móvil (BFF)"])

_OPEN_INCIDENT_STATES = ("REPORTED", "INVESTIGATING", "MITIGATED")


def _val(x) -> str:
    """Valor string de una columna enum (acepta Enum o str)."""
    return getattr(x, "value", None) or str(x)


def _is_overdue(ticket) -> bool:
    return (
        ticket.due_date is not None
        and _val(ticket.status) != "COMPLETED"
        and ticket.due_date.replace(tzinfo=None) < datetime.utcnow()
    )


async def _subtask_counts_safe(db: AsyncSession, ticket_ids: list) -> dict:
    """
    {ticket_id: (total, hechas)} para un conjunto de tickets.
    Cuenta en Python: el volumen por aplicación es pequeño y evita
    agregaciones con casts específicos de motor.
    """
    if not ticket_ids:
        return {}
    result = await db.execute(
        select(Subtask.ticket_id, Subtask.is_completed).where(Subtask.ticket_id.in_(ticket_ids))
    )
    counts: dict = {}
    for ticket_id, done in result.all():
        total, completed = counts.get(ticket_id, (0, 0))
        counts[ticket_id] = (total + 1, completed + (1 if done else 0))
    return counts


def _ticket_summary(t, users: dict, sub_counts: dict) -> TicketSummary:
    assignee = users.get(t.assignee_id)
    total, done = sub_counts.get(t.id, (0, 0))
    return TicketSummary(
        id=t.id,
        title=t.title,
        status=_val(t.status),
        priority=_val(t.priority),
        due_date=t.due_date,
        is_overdue=_is_overdue(t),
        subtasks_total=total,
        subtasks_done=done,
        assignee=UserBrief.model_validate(assignee) if assignee else None,
    )


async def _users_by_id(db: AsyncSession) -> dict:
    result = await db.execute(select(User).options(selectinload(User.role)))
    return {u.id: u for u in result.scalars().all()}


# ================================================================ §5.1

@router.get(
    "/dashboard",
    response_model=MobileDashboardResponse,
    response_model_exclude_none=True,
    summary="Dashboard de inicio (agregado por rol)",
)
async def get_mobile_dashboard(
    attention_limit: int = Query(10, ge=1, le=25, description="Máximo de elementos en atención / mis tickets"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MobileDashboardResponse:
    """
    Todo lo que la pantalla de inicio necesita, en una llamada (§5.1).

    ADMIN / GROUP_LEADER: métricas globales, estado por aplicación y lista
    "Requiere atención". DEVELOPER: métricas personales, sus tickets activos
    ordenados por vencimiento y sus incidencias abiertas.
    """
    users = await _users_by_id(db)

    if get_role_name(current_user) in LEAD_ROLES:
        apps = (await db.execute(select(Application))).scalars().all()
        epics = (await db.execute(select(Epic))).scalars().all()
        tickets = (await db.execute(select(Ticket).where(Ticket.ticket_type == TicketType.DEVELOPMENT))).scalars().all()
        incidents = (await db.execute(select(Incident))).scalars().all() if Incident is not None else []

        epics_by_app: dict = {}
        for e in epics:
            epics_by_app.setdefault(e.application_id if hasattr(e, "application_id") else e.app_id, []).append(e)
        epic_app: dict = {e.id: (getattr(e, "application_id", None) or getattr(e, "app_id", None)) for e in epics}
        app_names = {a.id: a.name for a in apps}

        open_tickets = [t for t in tickets if _val(t.status) != "COMPLETED"]
        blocked = [t for t in open_tickets if _val(t.status) in ("BLOCKED", "BLOCKED_QUESTION")]
        overdue = [t for t in open_tickets if _is_overdue(t)]
        open_incidents = [i for i in incidents if _val(i.status) in _OPEN_INCIDENT_STATES]

        projects = []
        for a in apps:
            app_epic_ids = {e.id for e in epics_by_app.get(a.id, [])}
            app_tickets = [t for t in tickets if t.epic_id in app_epic_ids]
            done = sum(1 for t in app_tickets if _val(t.status) == "COMPLETED")
            projects.append(ProjectSummary(
                id=a.id, name=a.name,
                epics_count=len(app_epic_ids),
                tickets_total=len(app_tickets), tickets_done=done,
                pending=len(app_tickets) - done,
                overdue=sum(1 for t in app_tickets if _is_overdue(t)),
                progress_pct=round(done / len(app_tickets) * 100, 1) if app_tickets else 0.0,
            ))

        attention: list[AttentionItem] = []
        seen = set()
        for t in blocked + overdue:
            if t.id in seen:
                continue
            seen.add(t.id)
            assignee = users.get(t.assignee_id)
            attention.append(AttentionItem(
                kind="TICKET", id=t.id, title=t.title,
                app_name=app_names.get(epic_app.get(t.epic_id), ""),
                status=_val(t.status), due_date=t.due_date,
                assignee_name=assignee.full_name if assignee else None,
            ))
        for i in open_incidents:
            if _val(i.severity) not in ("P1", "P2"):
                continue
            assignee = users.get(getattr(i, "assigned_to_id", None))
            attention.append(AttentionItem(
                kind="INCIDENT", id=i.id, title=i.title,
                app_name=app_names.get(i.application_id, ""),
                status=_val(i.status), severity=_val(i.severity),
                assignee_name=assignee.full_name if assignee else None,
            ))

        return MobileDashboardResponse(
            role=get_role_name(current_user),
            stats={
                "applications": len(apps),
                "open_tickets": len(open_tickets),
                "blocked_tickets": len(blocked),
                "overdue_tickets": len(overdue),
                "open_incidents": len(open_incidents),
            },
            projects=projects,
            attention=attention[:attention_limit],
        )

    # ------------------------------------------------------------ DEVELOPER
    my_tickets_all = (await db.execute(
        select(Ticket).where(Ticket.assignee_id == current_user.id)
    )).scalars().all()
    mine_open = [t for t in my_tickets_all if _val(t.status) != "COMPLETED"]
    mine_open.sort(key=lambda t: (t.due_date is None, t.due_date or datetime.max))

    week_ago = datetime.utcnow() - timedelta(days=7)
    done_last_7d = sum(
        1 for t in my_tickets_all
        if _val(t.status) == "COMPLETED" and t.updated_at and t.updated_at.replace(tzinfo=None) >= week_ago
    )

    incidents = []
    if Incident is not None:
        incidents = (await db.execute(
            select(Incident, Application.name)
            .join(Application, Incident.application_id == Application.id)
            .where(Incident.assigned_to_id == current_user.id)
        )).all()
    my_incidents = [
        IncidentSummary(
            id=i.id, title=i.title, status=_val(i.status),
            severity=_val(i.severity), app_name=app_name, created_at=i.created_at,
        )
        for i, app_name in incidents
        if _val(i.status) in _OPEN_INCIDENT_STATES
    ]

    sub_counts = await _subtask_counts_safe(db, [t.id for t in mine_open])
    return MobileDashboardResponse(
        role=get_role_name(current_user),
        stats={
            "my_open": len(mine_open),
            "in_progress": sum(1 for t in mine_open if _val(t.status) == "IN_PROGRESS"),
            "blocked": sum(1 for t in mine_open if _val(t.status) in ("BLOCKED", "BLOCKED_QUESTION")),
            "done_last_7d": done_last_7d,
            "my_open_incidents": len(my_incidents),
        },
        my_tickets=[_ticket_summary(t, users, sub_counts) for t in mine_open[:attention_limit]],
        my_incidents=my_incidents,
    )


# ================================================================ §5.2

@router.get(
    "/applications/{app_id}/board",
    response_model=ApplicationBoardResponse,
    summary="Tablero de proyecto (épicas con tickets anidados)",
)
async def get_application_board(
    app_id: UUID,
    status_filter: str | None = Query(None, alias="status", description="Filtrar tickets por estado"),
    assignee_id: UUID | None = Query(None, description="Filtrar tickets por asignado"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApplicationBoardResponse:
    """Vista completa del proyecto en una llamada (§5.2)."""
    application = await db.get(Application, app_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aplicación no encontrada")

    app_fk = getattr(Epic, "application_id", None) or Epic.app_id
    epics = (await db.execute(
        select(Epic).where(app_fk == app_id).order_by(getattr(Epic, "order_index", Epic.created_at))
    )).scalars().all()

    epic_ids = [e.id for e in epics]
    tickets: list = []
    if epic_ids:
        tickets = (await db.execute(
            select(Ticket).where(Ticket.epic_id.in_(epic_ids)).order_by(Ticket.order_index)
        )).scalars().all()

    users = await _users_by_id(db)
    sub_counts = await _subtask_counts_safe(db, [t.id for t in tickets])

    boards = []
    for e in epics:
        epic_tickets = [t for t in tickets if t.epic_id == e.id]
        done = sum(1 for t in epic_tickets if _val(t.status) == "COMPLETED")
        visible = epic_tickets
        if status_filter:
            visible = [t for t in visible if _val(t.status) == status_filter.upper()]
        if assignee_id:
            visible = [t for t in visible if t.assignee_id == assignee_id]
        boards.append(EpicBoard(
            id=e.id, name=e.title,  # el modelo Epic llama 'title' a su nombre
            order_index=getattr(e, "order_index", 0) or 0,
            tickets_total=len(epic_tickets), tickets_done=done,
            progress_pct=round(done / len(epic_tickets) * 100, 1) if epic_tickets else 0.0,
            tickets=[_ticket_summary(t, users, sub_counts) for t in visible],
        ))

    return ApplicationBoardResponse(
        application=ApplicationBrief.model_validate(application),
        epics=boards,
    )


# ================================================================ §5.3

@router.get(
    "/tickets/{ticket_id}/detail",
    response_model=TicketDetailResponse,
    summary="Detalle completo de ticket (con permisos calculados)",
)
async def get_ticket_detail(
    ticket_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TicketDetailResponse:
    """
    Ticket + breadcrumb + subtareas + historial + temporizador + permissions,
    en una llamada (§5.3). El bloque permissions se calcula en servidor con
    las mismas reglas que validan los endpoints de acción.
    """
    ticket = await db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")

    if ticket.epic_id is None:
        raise HTTPException(status_code=404, detail="Este ticket no pertenece a un tablero de desarrollo")
    epic = await db.get(Epic, ticket.epic_id)
    application = await db.get(Application, getattr(epic, "application_id", None) or epic.app_id)
    users = await _users_by_id(db)
    assignee = users.get(ticket.assignee_id)
    created_by = users.get(ticket.created_by_id)

    subtasks = (await db.execute(
        select(Subtask).where(Subtask.ticket_id == ticket_id).order_by(getattr(Subtask, "order_index", Subtask.created_at))
    )).scalars().all()

    event_rows = (await db.execute(
        select(TicketEvent, User).options(selectinload(User.role))
        .outerjoin(User, TicketEvent.user_id == User.id)
        .where(TicketEvent.ticket_id == ticket_id)
        .order_by(TicketEvent.created_at.desc())
    )).all()

    events = []
    is_running = _val(ticket.status) == "IN_PROGRESS"
    started_at = ticket.timer_started_at
    is_running = is_running and started_at is not None
    for ev, ev_user in event_rows:
        raw_payload = None
        for column in ("detail", "payload", "data", "event_metadata", "details"):
            if hasattr(ev, column):
                raw_payload = getattr(ev, column)
                break
        # CS-020 stores recipients in FK columns and its reason in detail.
        # Expose both through the existing flexible BFF payload, read-only.
        event_payload = dict(raw_payload) if isinstance(raw_payload, dict) else {}
        if ev.to_user_id:
            event_payload.setdefault("to_user_id", str(ev.to_user_id))
        if ev.from_user_id:
            event_payload.setdefault("from_user_id", str(ev.from_user_id))
        events.append(TicketEventDetail(
            id=ev.id,
            event_type=_val(ev.event_type),
            payload=event_payload or None,
            created_at=ev.created_at,
            user=UserBrief.model_validate(ev_user) if ev_user else None,
        ))
    return TicketDetailResponse(
        ticket=TicketFull.model_validate(ticket),
        epic=EpicBrief(id=epic.id, name=epic.title),
        application=ApplicationBrief.model_validate(application),
        assignee=UserBrief.model_validate(assignee) if assignee else None,
        created_by=UserBrief.model_validate(created_by) if created_by else None,
        subtasks=[SubtaskBrief.model_validate(s) for s in subtasks],
        events=events,
        timer=TimerState(
            is_running=is_running,
            time_spent_seconds=ticket.time_spent_seconds or 0,
            blocked_time_seconds=ticket.blocked_time_seconds or 0,
            started_at=started_at,
            blocked_started_at=ticket.blocked_at if _val(ticket.status) in ("BLOCKED", "BLOCKED_QUESTION") else None,
        ),
        permissions=TicketPermissions(**compute_ticket_permissions(
            role=get_role_name(current_user),
            user_id=current_user.id,
            ticket_status=_val(ticket.status),
            ticket_assignee_id=str(ticket.assignee_id) if ticket.assignee_id else None,
        )),
    )


# ================================================================ §5.4

@router.get(
    "/team/workload",
    response_model=list[MemberWorkload],
    summary="Carga de trabajo del equipo",
)
async def get_team_workload(
    include_inactive: bool = Query(False, description="Incluir usuarios desactivados"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MemberWorkload]:
    """Miembros del equipo con sus contadores de carga (§5.4)."""
    if get_role_name(current_user) not in LEAD_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requiere rol ADMIN o GROUP_LEADER",
        )

    users_q = select(User).options(selectinload(User.role))
    if not include_inactive:
        users_q = users_q.where(User.is_active == True)  # noqa: E712
    members = (await db.execute(users_q.order_by(User.full_name))).scalars().all()

    tickets = (await db.execute(select(Ticket).where(Ticket.assignee_id.isnot(None)))).scalars().all()
    incidents = []
    if Incident is not None:
        incidents = (await db.execute(
            select(Incident).where(Incident.assigned_to_id.isnot(None))
        )).scalars().all()

    week_ago = datetime.utcnow() - timedelta(days=7)
    workload = []
    for m in members:
        mine = [t for t in tickets if t.assignee_id == m.id]
        active = [t for t in mine if _val(t.status) != "COMPLETED"]
        workload.append(MemberWorkload(
            user=UserBrief.model_validate(m),
            is_active=m.is_active,
            active_tickets=len(active),
            in_progress=sum(1 for t in active if _val(t.status) == "IN_PROGRESS"),
            blocked=sum(1 for t in active if _val(t.status) in ("BLOCKED", "BLOCKED_QUESTION")),
            done_last_7d=sum(
                1 for t in mine
                if _val(t.status) == "COMPLETED" and t.updated_at and t.updated_at.replace(tzinfo=None) >= week_ago
            ),
            open_incidents=sum(
                1 for i in incidents
                if i.assigned_to_id == m.id and _val(i.status) in _OPEN_INCIDENT_STATES
            ),
        ))
    return workload
