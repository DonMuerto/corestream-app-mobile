"""
Asignación explícita de tickets (§6.1).

Prefijo: /tickets (convive con el router existente; la ruta /assign no existe allí).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models import Ticket, TicketEvent, User
from app.schemas import TokenPayload
from mobile_api.schemas.mobile import TicketAssignRequest
from mobile_api.services.push_service import PushService

router = APIRouter(prefix="/tickets", tags=["Tickets"])

_LEAD_ROLES = ("ADMIN", "GROUP_LEADER")


class TicketAssignResponse(BaseModel):
    """
    Ticket actualizado tras la asignación.

    Esquema propio (subconjunto plano): el TicketResponse existente exige
    campos enriquecidos (epic_title, app_name, subtasks) que este endpoint
    no necesita cargar.
    """

    id: UUID
    title: str
    status: str
    priority: str
    epic_id: UUID
    assignee_id: Optional[UUID] = None
    due_date: Optional[datetime] = None
    updated_at: datetime

    model_config = {"from_attributes": True}


@router.post(
    "/{ticket_id}/assign",
    response_model=TicketAssignResponse,
    summary="Asignar o reasignar un ticket",
)
async def assign_ticket(
    ticket_id: UUID,
    payload: TicketAssignRequest,
    current_user: TokenPayload = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TicketAssignResponse:
    """
    Asigna el ticket a un usuario (§6.1). Solo ADMIN y GROUP_LEADER.

    Efectos:
        - Actualiza assignee_id; si el ticket estaba REDIRECTED vuelve a TODO.
        - Registra un TicketEvent de tipo ASSIGNED (con el comentario opcional).
        - Notifica al nuevo asignado: in-app + WebSocket + push FCM.
    """
    if current_user.role not in _LEAD_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requiere rol ADMIN o GROUP_LEADER",
        )

    ticket = await db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")

    if str(ticket.status) == "DONE" or getattr(ticket.status, "value", None) == "DONE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No se puede asignar un ticket completado",
        )

    assignee = await db.get(User, payload.assignee_id)
    if assignee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    if not assignee.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El usuario asignado está inactivo",
        )

    ticket.assignee_id = assignee.id
    if getattr(ticket.status, "value", str(ticket.status)) == "REDIRECTED":
        ticket.status = "TODO"

    event = TicketEvent(
        ticket_id=ticket.id,
        user_id=current_user.sub,
        event_type="ASSIGNED",
    )
    # El nombre de la columna de datos del evento varía según la versión del
    # modelo (payload / data / event_metadata): se rellena la que exista.
    detail = {"assignee_id": str(assignee.id), "comment": payload.comment}
    for column in ("payload", "data", "event_metadata", "details"):
        if hasattr(TicketEvent, column):
            setattr(event, column, detail)
            break
    db.add(event)

    await db.commit()
    await db.refresh(ticket)

    # Notificación al nuevo asignado (no se auto-notifica una autoasignación)
    if str(assignee.id) != str(current_user.sub):
        assigner = await db.get(User, current_user.sub)
        assigner_name = assigner.full_name if assigner else "Un líder"
        message = f"{assigner_name} te asignó: “{ticket.title}”"
        if payload.comment:
            message += f" — {payload.comment}"
        await PushService.notify_user(
            db,
            user_id=str(assignee.id),
            title="Ticket asignado",
            message=message,
            notification_type="ASSIGNMENT",
            ticket_id=str(ticket.id),
        )

    return TicketAssignResponse.model_validate(ticket)
