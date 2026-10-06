"""
Tests de integración de los endpoints móviles (requieren TEST_DATABASE_URL).

    export TEST_DATABASE_URL=postgresql+asyncpg://corestream:corestream@localhost:5432/corestream_test
    pytest mobile_api/tests/test_api.py -v
"""

import uuid
from datetime import datetime, timedelta

import pytest

from mobile_api.tests.conftest import requires_db

pytestmark = [requires_db, pytest.mark.asyncio]


# ---------------------------------------------------------------- utilidades

async def _create_app_epic_ticket(ctx, assignee=None, status="TODO"):
    """Crea Application -> Epic -> Ticket mínimos para los tests."""
    from app.models import Application, Epic, Ticket

    admin = ctx.users["ADMIN"]
    async with ctx.session_factory() as session:
        app_row = Application(
            name=f"App Test {uuid.uuid4().hex[:6]}",
            description="app de prueba",
            owner_id=admin.id,
        )
        session.add(app_row)
        await session.flush()

        epic = Epic(
            title="Épica de prueba",
            application_id=app_row.id,
            order_index=0,
        )
        session.add(epic)
        await session.flush()

        ticket = Ticket(
            title="Ticket de prueba móvil",
            description="descripción",
            epic_id=epic.id,
            status=status,
            priority="MEDIUM",
            assignee_id=assignee.id if assignee else None,
            created_by_id=admin.id,
            due_date=datetime.utcnow() + timedelta(days=5),
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        return app_row, epic, ticket


# ---------------------------------------------------------------- §4 devices

async def test_registrar_dispositivo_idempotente(ctx, client):
    ctx.set_current_user(ctx.users["DEVELOPER"])
    token = f"fcm-test-{uuid.uuid4().hex}"

    r1 = await client.post("/devices/", json={"fcm_token": token, "platform": "ANDROID", "device_name": "Pixel de prueba"})
    assert r1.status_code == 201, r1.text
    device_id = r1.json()["id"]

    # Mismo token -> 200 y mismo registro (no duplica)
    r2 = await client.post("/devices/", json={"fcm_token": token, "platform": "ANDROID", "app_version": "1.0.1"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["id"] == device_id
    assert r2.json()["app_version"] == "1.0.1"

    # El token cambia de usuario (nueva sesión en el mismo teléfono)
    ctx.set_current_user(ctx.users["GROUP_LEADER"])
    r3 = await client.post("/devices/", json={"fcm_token": token, "platform": "ANDROID"})
    assert r3.status_code == 200
    assert r3.json()["user_id"] == str(ctx.users["GROUP_LEADER"].id)


async def test_no_puede_borrar_dispositivo_ajeno(ctx, client):
    ctx.set_current_user(ctx.users["DEVELOPER"])
    r = await client.post("/devices/", json={"fcm_token": f"fcm-{uuid.uuid4().hex}", "platform": "IOS"})
    device_id = r.json()["id"]

    ctx.set_current_user(ctx.users["GROUP_LEADER"])
    r = await client.delete(f"/devices/{device_id}")
    assert r.status_code == 403
    assert r.json()["detail"] == "No puede eliminar dispositivos de otro usuario"

    ctx.set_current_user(ctx.users["DEVELOPER"])
    r = await client.delete(f"/devices/{device_id}")
    assert r.status_code == 204


async def test_preferencias_defaults_y_actualizacion(ctx, client):
    ctx.set_current_user(ctx.users["DEVELOPER"])

    r = await client.get("/devices/preferences")
    assert r.status_code == 200
    assert r.json()["push_enabled"] is True
    assert r.json()["quiet_hours_start"] is None

    r = await client.put("/devices/preferences", json={
        "ticket_completed": False,
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "07:00",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["ticket_completed"] is False
    assert body["quiet_hours_start"] == "22:00"
    assert body["push_enabled"] is True  # lo no enviado no cambia

    # formato inválido -> 422
    r = await client.put("/devices/preferences", json={"quiet_hours_start": "25:99", "quiet_hours_end": "07:00"})
    assert r.status_code == 422


# ---------------------------------------------------------------- §6.1 assign

async def test_developer_no_puede_asignar(ctx, client):
    dev = ctx.users["DEVELOPER"]
    _, _, ticket = await _create_app_epic_ticket(ctx)

    ctx.set_current_user(dev)
    r = await client.post(f"/tickets/{ticket.id}/assign", json={"assignee_id": str(dev.id)})
    assert r.status_code == 403
    assert r.json()["detail"] == "Requiere rol ADMIN o GROUP_LEADER"


async def test_lider_asigna_y_notifica(ctx, client):
    from sqlalchemy import select
    from app.models import Notification

    dev = ctx.users["DEVELOPER"]
    _, _, ticket = await _create_app_epic_ticket(ctx)

    ctx.set_current_user(ctx.users["GROUP_LEADER"])
    r = await client.post(
        f"/tickets/{ticket.id}/assign",
        json={"assignee_id": str(dev.id), "comment": "Tiene contexto del módulo"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["assignee_id"] == str(dev.id)

    # Se creó la notificación in-app para el asignado
    async with ctx.session_factory() as session:
        notifs = (await session.execute(
            select(Notification).where(
                Notification.user_id == dev.id,
                Notification.ticket_id == ticket.id,
            )
        )).scalars().all()
    assert len(notifs) == 1
    assert "te asignó" in notifs[0].message


async def test_no_se_asigna_ticket_completado(ctx, client):
    dev = ctx.users["DEVELOPER"]
    _, _, ticket = await _create_app_epic_ticket(ctx, assignee=dev, status="DONE")

    ctx.set_current_user(ctx.users["ADMIN"])
    r = await client.post(f"/tickets/{ticket.id}/assign", json={"assignee_id": str(dev.id)})
    assert r.status_code == 409
    assert r.json()["detail"] == "No se puede asignar un ticket completado"


async def test_asignar_usuario_inexistente(ctx, client):
    _, _, ticket = await _create_app_epic_ticket(ctx)
    ctx.set_current_user(ctx.users["ADMIN"])
    r = await client.post(f"/tickets/{ticket.id}/assign", json={"assignee_id": str(uuid.uuid4())})
    assert r.status_code == 404
    assert r.json()["detail"] == "Usuario no encontrado"


# ---------------------------------------------------------------- §5 mobile

async def test_dashboard_por_rol(ctx, client):
    dev = ctx.users["DEVELOPER"]
    await _create_app_epic_ticket(ctx, assignee=dev, status="IN_PROGRESS")

    ctx.set_current_user(ctx.users["ADMIN"])
    r = await client.get("/mobile/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "ADMIN"
    assert "applications" in body["stats"]
    assert isinstance(body["projects"], list)

    ctx.set_current_user(dev)
    r = await client.get("/mobile/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "DEVELOPER"
    assert body["stats"]["my_open"] >= 1
    assert any(t["status"] == "IN_PROGRESS" for t in body["my_tickets"])


async def test_board_agregado(ctx, client):
    dev = ctx.users["DEVELOPER"]
    app_row, epic, ticket = await _create_app_epic_ticket(ctx, assignee=dev)

    ctx.set_current_user(ctx.users["GROUP_LEADER"])
    r = await client.get(f"/mobile/applications/{app_row.id}/board")
    assert r.status_code == 200
    body = r.json()
    assert body["application"]["id"] == str(app_row.id)
    epics = {e["id"]: e for e in body["epics"]}
    assert str(epic.id) in epics
    tickets = epics[str(epic.id)]["tickets"]
    assert any(t["id"] == str(ticket.id) and t["assignee"]["id"] == str(dev.id) for t in tickets)

    r = await client.get(f"/mobile/applications/{uuid.uuid4()}/board")
    assert r.status_code == 404


async def test_detalle_con_permisos(ctx, client):
    dev = ctx.users["DEVELOPER"]
    _, _, ticket = await _create_app_epic_ticket(ctx, assignee=dev, status="IN_PROGRESS")

    ctx.set_current_user(dev)
    r = await client.get(f"/mobile/tickets/{ticket.id}/detail")
    assert r.status_code == 200
    body = r.json()
    assert body["permissions"]["can_complete"] is True
    assert body["permissions"]["can_assign"] is False
    assert body["timer"]["is_running"] is True

    ctx.set_current_user(ctx.users["ADMIN"])
    r = await client.get(f"/mobile/tickets/{ticket.id}/detail")
    body = r.json()
    assert body["permissions"]["can_assign"] is True
    assert body["permissions"]["can_complete"] is False


async def test_workload_solo_lideres(ctx, client):
    ctx.set_current_user(ctx.users["DEVELOPER"])
    r = await client.get("/mobile/team/workload")
    assert r.status_code == 403

    ctx.set_current_user(ctx.users["GROUP_LEADER"])
    r = await client.get("/mobile/team/workload")
    assert r.status_code == 200
    names = [m["user"]["full_name"] for m in r.json()]
    assert any("Test Developer" in n for n in names)
