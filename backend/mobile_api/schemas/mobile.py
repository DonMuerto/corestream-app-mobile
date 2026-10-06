"""
Esquemas Pydantic del BFF móvil (§5.1–5.4) y de la asignación de tickets (§6.1).
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, field_validator

# ---------------------------------------------------------------- comunes

class UserBrief(BaseModel):
    """Usuario resumido para incrustar en respuestas agregadas."""

    id: UUID
    full_name: str
    avatar_url: Optional[str] = None
    specialty: Optional[str] = None
    role: Optional[str] = None

    model_config = {"from_attributes": True}

    @field_validator("role", mode="before")
    @classmethod
    def role_name(cls, value):
        return value.name if hasattr(value, "name") else value


class TicketSummary(BaseModel):
    """Ticket resumido para listados (tablero, dashboard)."""

    id: UUID
    title: str
    status: str
    priority: str
    due_date: Optional[datetime] = None
    is_overdue: bool = False
    subtasks_total: int = 0
    subtasks_done: int = 0
    assignee: Optional[UserBrief] = None


class IncidentSummary(BaseModel):
    """Incidencia resumida para listados."""

    id: UUID
    title: str
    status: str
    severity: str
    app_name: str
    created_at: datetime


# ---------------------------------------------------------------- §5.1 dashboard

class ProjectSummary(BaseModel):
    """Estado agregado de una aplicación para el dashboard."""

    id: UUID
    name: str
    epics_count: int
    tickets_total: int
    tickets_done: int
    pending: int
    overdue: int
    progress_pct: float


class AttentionItem(BaseModel):
    """Elemento de la lista 'Requiere atención' (ADMIN / GROUP_LEADER)."""

    kind: str  # TICKET | INCIDENT
    id: UUID
    title: str
    app_name: str
    status: str
    severity: Optional[str] = None
    due_date: Optional[datetime] = None
    assignee_name: Optional[str] = None


class MobileDashboardResponse(BaseModel):
    """Respuesta de GET /mobile/dashboard — el contenido depende del rol."""

    role: str
    stats: dict[str, int]
    projects: Optional[list[ProjectSummary]] = None
    attention: Optional[list[AttentionItem]] = None
    my_tickets: Optional[list[TicketSummary]] = None
    my_incidents: Optional[list[IncidentSummary]] = None


# ---------------------------------------------------------------- §5.2 tablero

class ApplicationBrief(BaseModel):
    id: UUID
    name: str

    model_config = {"from_attributes": True}


class EpicBoard(BaseModel):
    """Épica con sus tickets anidados y contadores de progreso."""

    id: UUID
    name: str
    order_index: int = 0
    tickets_total: int
    tickets_done: int
    progress_pct: float
    tickets: list[TicketSummary]


class ApplicationBoardResponse(BaseModel):
    """Respuesta de GET /mobile/applications/{app_id}/board."""

    application: ApplicationBrief
    epics: list[EpicBoard]


# ---------------------------------------------------------------- §5.3 detalle

class SubtaskBrief(BaseModel):
    id: UUID
    title: str
    is_completed: bool
    order_index: int = 0

    model_config = {"from_attributes": True}


class TicketEventDetail(BaseModel):
    """Evento del historial del ticket con su autor expandido."""

    id: UUID
    event_type: str
    payload: Optional[dict] = None
    created_at: datetime
    user: Optional[UserBrief] = None


class TimerState(BaseModel):
    """Estado del temporizador del ticket para la vista móvil."""

    is_running: bool
    time_spent_seconds: int
    blocked_time_seconds: int
    started_at: Optional[datetime] = None


class TicketPermissions(BaseModel):
    """
    Acciones que el usuario actual puede ejecutar sobre el ticket.

    Calculadas en servidor con las mismas reglas de roles y máquina de
    estados que validan los endpoints de acción; la app solo las pinta.
    """

    can_assign: bool = False
    can_start: bool = False
    can_complete: bool = False
    can_question: bool = False
    can_resolve_question: bool = False
    can_redirect: bool = False
    can_edit_subtasks: bool = False
    can_edit: bool = False
    can_delete: bool = False


class TicketFull(BaseModel):
    """Ticket completo (estructura equivalente al TicketResponse existente)."""

    id: UUID
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    due_date: Optional[datetime] = None
    pr_link: Optional[str] = None
    blocked_question: Optional[str] = None
    time_spent_seconds: int = 0
    blocked_time_seconds: int = 0
    order_index: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EpicBrief(BaseModel):
    id: UUID
    name: str

    model_config = {"from_attributes": True}


class TicketDetailResponse(BaseModel):
    """Respuesta de GET /mobile/tickets/{ticket_id}/detail."""

    ticket: TicketFull
    epic: EpicBrief
    application: ApplicationBrief
    assignee: Optional[UserBrief] = None
    created_by: Optional[UserBrief] = None
    subtasks: list[SubtaskBrief]
    events: list[TicketEventDetail]
    timer: TimerState
    permissions: TicketPermissions


# ---------------------------------------------------------------- §5.4 equipo

class MemberWorkload(BaseModel):
    """Carga de trabajo de un miembro del equipo."""

    user: UserBrief
    is_active: bool = True
    active_tickets: int
    in_progress: int
    blocked: int
    done_last_7d: int
    open_incidents: int


# ---------------------------------------------------------------- §6.1 asignación

class TicketAssignRequest(BaseModel):
    """Cuerpo de POST /tickets/{ticket_id}/assign."""

    assignee_id: UUID
    comment: Optional[str] = None

    @field_validator("comment")
    @classmethod
    def validate_comment(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) > 500:
                raise ValueError("El comentario supera los 500 caracteres")
            if not v:
                return None
        return v
