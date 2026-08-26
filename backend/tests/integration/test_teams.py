"""
Ciclo de vida de Equipos (Team) — agrupador de épicas para trackear el
trabajo de un equipo de estudiantes como unidad (software factory,
convenio DuocUC/UTEM). Ver docstring de app/models/team.py.
"""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ---------------------------------------------------------------------------
# CRUD básico
# ---------------------------------------------------------------------------

async def test_crear_equipo(client, leader_headers):
    res = await client.post(
        "/api/teams/",
        json={"name": "Equipo A - DuocUC - 2026-1", "description": "Sistema de inventario"},
        headers=leader_headers,
    )
    assert res.status_code == 201, res.text[:300]
    body = res.json()
    assert body["name"] == "Equipo A - DuocUC - 2026-1"
    assert body["epic_count"] == 0
    assert body["total_tickets"] == 0
    assert body["progress"] == 0.0


async def test_crear_equipo_con_nombre_duplicado_falla(client, leader_headers):
    await client.post("/api/teams/", json={"name": "Equipo Duplicado"}, headers=leader_headers)
    res = await client.post("/api/teams/", json={"name": "Equipo Duplicado"}, headers=leader_headers)
    assert res.status_code == 409


async def test_listar_equipos(client, leader_headers):
    await client.post("/api/teams/", json={"name": "Equipo Listado"}, headers=leader_headers)
    res = await client.get("/api/teams/", headers=leader_headers)
    assert res.status_code == 200
    assert any(t["name"] == "Equipo Listado" for t in res.json())


async def test_renombrar_equipo(client, leader_headers):
    creado = await client.post("/api/teams/", json={"name": "Nombre Viejo"}, headers=leader_headers)
    team_id = creado.json()["id"]

    res = await client.put(
        f"/api/teams/{team_id}", json={"name": "Nombre Nuevo"}, headers=leader_headers
    )
    assert res.status_code == 200
    assert res.json()["name"] == "Nombre Nuevo"


async def test_renombrar_equipo_a_nombre_ya_usado_falla(client, leader_headers):
    await client.post("/api/teams/", json={"name": "Equipo Uno"}, headers=leader_headers)
    otro = await client.post("/api/teams/", json={"name": "Equipo Dos"}, headers=leader_headers)

    res = await client.put(
        f"/api/teams/{otro.json()['id']}", json={"name": "Equipo Uno"}, headers=leader_headers
    )
    assert res.status_code == 409


async def test_equipo_inexistente_da_404(client, leader_headers):
    res = await client.get("/api/teams/00000000-0000-4000-8000-000000000000", headers=leader_headers)
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Asociación con épicas y agregación de progreso
# ---------------------------------------------------------------------------

async def test_asignar_equipo_a_epica(client, leader_headers, epic):
    equipo = await client.post("/api/teams/", json={"name": "Equipo Épica"}, headers=leader_headers)
    team_id = equipo.json()["id"]

    res = await client.put(f"/api/epics/{epic['id']}", json={"team_id": team_id}, headers=leader_headers)
    assert res.status_code == 200
    assert res.json()["team_id"] == team_id
    assert res.json()["team_name"] == "Equipo Épica"


async def test_asignar_equipo_inexistente_a_epica_da_404(client, leader_headers, epic):
    res = await client.put(
        f"/api/epics/{epic['id']}",
        json={"team_id": "00000000-0000-4000-8000-000000000000"},
        headers=leader_headers,
    )
    assert res.status_code == 404


async def test_detalle_de_equipo_agrega_progreso_de_sus_epicas(
    client, leader_headers, epic, ticket, dev_headers
):
    """
    Un ticket completado en la única épica del equipo debe reflejarse en el
    progreso agregado del equipo (no solo en la épica individual) — esto es
    justamente lo que permite comparar equipos de un vistazo.
    """
    equipo = await client.post("/api/teams/", json={"name": "Equipo Progreso"}, headers=leader_headers)
    team_id = equipo.json()["id"]
    await client.put(f"/api/epics/{epic['id']}", json={"team_id": team_id}, headers=leader_headers)

    await client.post(f"/api/tickets/{ticket['id']}/start", json={}, headers=dev_headers)
    await client.post(
        f"/api/tickets/{ticket['id']}/complete",
        json={"pr_link": "https://github.com/org/repo/pull/1"},
        headers=dev_headers,
    )

    res = await client.get(f"/api/teams/{team_id}", headers=leader_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["epic_count"] == 1
    assert body["total_tickets"] == 1
    assert body["completed_tickets"] == 1
    assert body["progress"] == 100.0
    assert len(body["epics"]) == 1
    assert body["epics"][0]["id"] == epic["id"]
    assert body["epics"][0]["application_name"] is not None


async def test_borrar_equipo_no_borra_sus_epicas(client, leader_headers, epic):
    """
    ondelete=SET NULL: el trabajo ya hecho por un equipo no debe perderse
    solo porque se elimina o reorganiza la etiqueta de agrupación.
    """
    equipo = await client.post("/api/teams/", json={"name": "Equipo Borrable"}, headers=leader_headers)
    team_id = equipo.json()["id"]
    await client.put(f"/api/epics/{epic['id']}", json={"team_id": team_id}, headers=leader_headers)

    res = await client.delete(f"/api/teams/{team_id}", headers=leader_headers)
    assert res.status_code == 204

    epica_res = await client.get(f"/api/epics/by-app/{epic['application_id']}", headers=leader_headers)
    assert epica_res.status_code == 200
    epica_actual = next(e for e in epica_res.json() if e["id"] == epic["id"])
    assert epica_actual["team_id"] is None


# ---------------------------------------------------------------------------
# RBAC — solo ADMIN/TEAM_LEADER gestionan equipos
# ---------------------------------------------------------------------------

async def test_developer_no_puede_listar_equipos(client, dev_headers):
    res = await client.get("/api/teams/", headers=dev_headers)
    assert res.status_code == 403


async def test_developer_no_puede_crear_equipos(client, dev_headers):
    res = await client.post("/api/teams/", json={"name": "Intento Dev"}, headers=dev_headers)
    assert res.status_code == 403


async def test_admin_puede_gestionar_equipos(client, admin_headers):
    res = await client.post("/api/teams/", json={"name": "Equipo Admin"}, headers=admin_headers)
    assert res.status_code == 201


# ---------------------------------------------------------------------------
# Integrantes — sueltos (sin cuenta) o vinculados a un User existente
# ---------------------------------------------------------------------------

async def test_agregar_integrante_suelto(client, leader_headers):
    equipo = await client.post("/api/teams/", json={"name": "Equipo Integrantes 1"}, headers=leader_headers)
    team_id = equipo.json()["id"]

    res = await client.post(
        f"/api/teams/{team_id}/members",
        json={"name": "Estudiante Sin Cuenta", "email": "estudiante@duoc.cl"},
        headers=leader_headers,
    )
    assert res.status_code == 201, res.text[:300]
    body = res.json()
    assert body["name"] == "Estudiante Sin Cuenta"
    assert body["email"] == "estudiante@duoc.cl"
    assert body["user_id"] is None


async def test_agregar_integrante_vinculado_a_usuario_existente(client, leader_headers, dev_id):
    equipo = await client.post("/api/teams/", json={"name": "Equipo Integrantes 2"}, headers=leader_headers)
    team_id = equipo.json()["id"]

    res = await client.post(
        f"/api/teams/{team_id}/members", json={"userId": dev_id}, headers=leader_headers
    )
    assert res.status_code == 201, res.text[:300]
    body = res.json()
    assert body["user_id"] == dev_id
    # nombre/email se completan automáticamente desde el User vinculado
    assert body["name"]
    assert body["email"]


async def test_agregar_integrante_con_userid_inexistente_da_404(client, leader_headers):
    equipo = await client.post("/api/teams/", json={"name": "Equipo Integrantes 3"}, headers=leader_headers)
    team_id = equipo.json()["id"]

    res = await client.post(
        f"/api/teams/{team_id}/members",
        json={"userId": "00000000-0000-4000-8000-000000000000"},
        headers=leader_headers,
    )
    assert res.status_code == 404


async def test_agregar_integrante_sin_nombre_ni_userid_da_400(client, leader_headers):
    equipo = await client.post("/api/teams/", json={"name": "Equipo Integrantes 4"}, headers=leader_headers)
    team_id = equipo.json()["id"]

    res = await client.post(f"/api/teams/{team_id}/members", json={}, headers=leader_headers)
    assert res.status_code == 400


async def test_integrantes_aparecen_en_el_detalle_y_cuentan_en_member_count(client, leader_headers):
    equipo = await client.post("/api/teams/", json={"name": "Equipo Integrantes 5"}, headers=leader_headers)
    team_id = equipo.json()["id"]

    await client.post(f"/api/teams/{team_id}/members", json={"name": "Persona A"}, headers=leader_headers)
    await client.post(f"/api/teams/{team_id}/members", json={"name": "Persona B"}, headers=leader_headers)

    detalle = await client.get(f"/api/teams/{team_id}", headers=leader_headers)
    assert detalle.status_code == 200
    assert len(detalle.json()["members"]) == 2

    listado = await client.get("/api/teams/", headers=leader_headers)
    equipo_en_lista = next(t for t in listado.json() if t["id"] == team_id)
    assert equipo_en_lista["member_count"] == 2


async def test_quitar_integrante_no_afecta_la_cuenta_del_usuario(client, leader_headers, dev_id):
    equipo = await client.post("/api/teams/", json={"name": "Equipo Integrantes 6"}, headers=leader_headers)
    team_id = equipo.json()["id"]

    agregado = await client.post(
        f"/api/teams/{team_id}/members", json={"userId": dev_id}, headers=leader_headers
    )
    member_id = agregado.json()["id"]

    res = await client.delete(f"/api/teams/{team_id}/members/{member_id}", headers=leader_headers)
    assert res.status_code == 204

    detalle = await client.get(f"/api/teams/{team_id}", headers=leader_headers)
    assert detalle.json()["members"] == []

    # el usuario sigue existiendo, solo se quitó del equipo
    usuario = await client.get(f"/api/users/{dev_id}", headers=leader_headers)
    assert usuario.status_code == 200


async def test_quitar_integrante_inexistente_da_404(client, leader_headers):
    equipo = await client.post("/api/teams/", json={"name": "Equipo Integrantes 7"}, headers=leader_headers)
    team_id = equipo.json()["id"]

    res = await client.delete(
        f"/api/teams/{team_id}/members/00000000-0000-4000-8000-000000000000",
        headers=leader_headers,
    )
    assert res.status_code == 404


async def test_developer_no_puede_agregar_integrantes(client, dev_headers, leader_headers):
    equipo = await client.post("/api/teams/", json={"name": "Equipo Integrantes 8"}, headers=leader_headers)
    team_id = equipo.json()["id"]

    res = await client.post(
        f"/api/teams/{team_id}/members", json={"name": "Intento Dev"}, headers=dev_headers
    )
    assert res.status_code == 403
