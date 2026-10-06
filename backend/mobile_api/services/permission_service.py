"""
Cálculo del bloque `permissions` del detalle de ticket (§5.3).

Función pura y sin dependencias del resto del proyecto para que sea fácil de
testear y de mantener alineada con las reglas de la máquina de estados
(app/services/ticket_state_machine.py) y del middleware de roles.

Reglas (idénticas a las que validan los endpoints de acción):
    - ADMIN y TEAM_LEADER asignan/reasignan cualquier ticket no completado.
    - Las acciones de trabajo (start, complete, question, redirect) son solo
      del usuario asignado, según el estado actual del ticket.
    - resolve_question la ejecuta ADMIN o TEAM_LEADER, no el developer bloqueado.
    - Las subtareas las edita el asignado o un líder mientras no esté DONE.
    - Editar metadatos del ticket es de líderes; eliminar, solo de ADMIN.
"""

LEAD_ROLES = {"ADMIN", "TEAM_LEADER"}


def compute_ticket_permissions(
    role: str,
    user_id: str,
    ticket_status: str,
    ticket_assignee_id: str | None,
) -> dict[str, bool]:
    """
    Calcula las acciones disponibles para un usuario sobre un ticket.

    Args:
        role: Rol del usuario (ADMIN | TEAM_LEADER | DEVELOPER).
        user_id: Id del usuario actual (str, comparado como str).
        ticket_status: Estado actual del ticket (TicketStatus).
        ticket_assignee_id: Id del asignado actual o None.

    Returns:
        dict con los nueve booleanos del esquema TicketPermissions.
    """
    is_lead = role in LEAD_ROLES
    is_mine = ticket_assignee_id is not None and str(ticket_assignee_id) == str(user_id)
    status = str(ticket_status)
    can_work = role != "ADMIN"
    finished = status in ("COMPLETED", "RESOLVED")

    return {
        "can_assign": is_lead and not finished,
        "can_start": can_work and (is_mine or ticket_assignee_id is None) and status in ("TODO", "REDIRECTED"),
        "can_complete": can_work and is_mine and status == "IN_PROGRESS",
        "can_question": can_work and is_mine and status == "IN_PROGRESS",
        "can_resolve_question": is_lead and status in ("BLOCKED", "BLOCKED_QUESTION"),
        "can_redirect": can_work and is_mine and status == "IN_PROGRESS",
        "can_edit_subtasks": (is_mine or is_lead) and not finished,
        "can_edit": is_lead or is_mine,
        "can_delete": role == "ADMIN",
    }
