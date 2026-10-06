"""
Tests del cálculo de permisos del detalle de ticket (§5.3).

Función pura: estos tests corren siempre, sin base de datos ni servicios.
    pytest mobile_api/tests/test_permissions.py
"""

from mobile_api.services.permission_service import compute_ticket_permissions

DEV = "11111111-1111-1111-1111-111111111111"
OTHER = "22222222-2222-2222-2222-222222222222"


def test_developer_asignado_en_progreso():
    p = compute_ticket_permissions("DEVELOPER", DEV, "IN_PROGRESS", DEV)
    assert p["can_complete"] and p["can_question"] and p["can_redirect"]
    assert p["can_edit_subtasks"]
    assert not p["can_assign"] and not p["can_start"]
    assert p["can_edit"] and not p["can_delete"]


def test_developer_no_asignado_solo_lectura():
    p = compute_ticket_permissions("DEVELOPER", OTHER, "IN_PROGRESS", DEV)
    assert not any(p.values()), "Un developer no asignado no puede ejecutar ninguna acción"


def test_developer_puede_comenzar_todo_y_redirigido():
    for estado in ("TODO", "REDIRECTED"):
        p = compute_ticket_permissions("DEVELOPER", DEV, estado, DEV)
        assert p["can_start"], estado
        assert not p["can_complete"]


def test_bloqueado_resuelve_asignado_o_lider():
    asignado = compute_ticket_permissions("DEVELOPER", DEV, "BLOCKED_QUESTION", DEV)
    lider = compute_ticket_permissions("TEAM_LEADER", OTHER, "BLOCKED_QUESTION", DEV)
    ajeno = compute_ticket_permissions("DEVELOPER", OTHER, "BLOCKED_QUESTION", DEV)
    assert asignado["can_resolve_question"]
    assert lider["can_resolve_question"]
    assert not ajeno["can_resolve_question"]


def test_lider_asigna_pero_no_trabaja_tickets_ajenos():
    p = compute_ticket_permissions("TEAM_LEADER", OTHER, "TODO", DEV)
    assert p["can_assign"] and p["can_edit"] and p["can_edit_subtasks"]
    assert not p["can_start"] and not p["can_complete"] and not p["can_delete"]


def test_admin_es_el_unico_que_elimina():
    admin = compute_ticket_permissions("ADMIN", OTHER, "TODO", DEV)
    lider = compute_ticket_permissions("TEAM_LEADER", OTHER, "TODO", DEV)
    assert admin["can_delete"] and not lider["can_delete"]


def test_ticket_done_es_intocable():
    for rol, uid in (("ADMIN", OTHER), ("TEAM_LEADER", OTHER), ("DEVELOPER", DEV)):
        p = compute_ticket_permissions(rol, uid, "COMPLETED", DEV)
        assert not p["can_assign"] and not p["can_edit_subtasks"]
        assert not p["can_start"] and not p["can_complete"]


def test_ticket_sin_asignar():
    p = compute_ticket_permissions("DEVELOPER", DEV, "TODO", None)
    assert p["can_start"], "Un desarrollador puede reclamar un ticket sin asignar"
    lider = compute_ticket_permissions("ADMIN", DEV, "TODO", None)
    assert lider["can_assign"]
