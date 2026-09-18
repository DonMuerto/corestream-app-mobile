"""
Integration tests for the invitation flow, in particular the permission
split between ADMIN and TEAM_LEADER (see docs/RBAC.md): a TEAM_LEADER can
invite DEVELOPER for their own team, but not another TEAM_LEADER or ADMIN,
and only sees/manages the invitations they themselves created.
"""

import uuid

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@duoc.cl"


async def test_admin_puede_invitar_con_cualquier_rol(client, admin_headers):
    res = await client.post(
        "/api/invitations/",
        json={"email": _unique_email("admin-invita"), "role": "TEAM_LEADER"},
        headers=admin_headers,
    )
    assert res.status_code == 201, res.text[:300]
    assert res.json()["role"] == "TEAM_LEADER"


async def test_leader_puede_invitar_developer(client, leader_headers):
    res = await client.post(
        "/api/invitations/",
        json={"email": _unique_email("leader-invita-dev"), "role": "DEVELOPER"},
        headers=leader_headers,
    )
    assert res.status_code == 201, res.text[:300]
    assert res.json()["role"] == "DEVELOPER"


async def test_leader_no_puede_invitar_team_leader(client, leader_headers):
    res = await client.post(
        "/api/invitations/",
        json={"email": _unique_email("leader-invita-leader"), "role": "TEAM_LEADER"},
        headers=leader_headers,
    )
    assert res.status_code == 403


async def test_leader_no_puede_invitar_admin(client, leader_headers):
    res = await client.post(
        "/api/invitations/",
        json={"email": _unique_email("leader-invita-admin"), "role": "ADMIN"},
        headers=leader_headers,
    )
    assert res.status_code == 403


async def test_developer_no_puede_invitar(client, dev_headers):
    res = await client.post(
        "/api/invitations/",
        json={"email": _unique_email("dev-invita"), "role": "DEVELOPER"},
        headers=dev_headers,
    )
    assert res.status_code == 403


async def test_leader_solo_ve_sus_propias_invitaciones_pendientes(client, admin_headers, leader_headers):
    admin_email = _unique_email("admin-crea")
    leader_email = _unique_email("leader-crea")

    await client.post(
        "/api/invitations/", json={"email": admin_email, "role": "DEVELOPER"}, headers=admin_headers
    )
    await client.post(
        "/api/invitations/", json={"email": leader_email, "role": "DEVELOPER"}, headers=leader_headers
    )

    res = await client.get("/api/invitations/pending", headers=leader_headers)
    assert res.status_code == 200
    emails = {inv["email"] for inv in res.json()}
    assert leader_email in emails
    assert admin_email not in emails


async def test_admin_ve_todas_las_invitaciones_pendientes(client, admin_headers, leader_headers):
    leader_email = _unique_email("leader-crea-2")
    await client.post(
        "/api/invitations/", json={"email": leader_email, "role": "DEVELOPER"}, headers=leader_headers
    )

    res = await client.get("/api/invitations/pending", headers=admin_headers)
    assert res.status_code == 200
    emails = {inv["email"] for inv in res.json()}
    assert leader_email in emails


async def test_leader_puede_reenviar_su_propia_invitacion(client, leader_headers):
    email = _unique_email("leader-reenvia")
    creada = await client.post(
        "/api/invitations/", json={"email": email, "role": "DEVELOPER"}, headers=leader_headers
    )
    invitation_id = creada.json()["id"]
    original_token = creada.json()["token"]

    res = await client.post(f"/api/invitations/{invitation_id}/resend", headers=leader_headers)
    assert res.status_code == 200, res.text[:300]
    body = res.json()
    assert body["email"] == email
    # New token: the original is never stored in plaintext, so there's no
    # way to resend the same link.
    assert body["token"] != original_token


async def test_leader_no_puede_reenviar_invitacion_ajena(client, admin_headers, leader_headers):
    creada = await client.post(
        "/api/invitations/",
        json={"email": _unique_email("admin-reenvio-ajeno"), "role": "DEVELOPER"},
        headers=admin_headers,
    )
    invitation_id = creada.json()["id"]

    res = await client.post(f"/api/invitations/{invitation_id}/resend", headers=leader_headers)
    assert res.status_code == 403


async def test_admin_puede_reenviar_cualquier_invitacion(client, admin_headers, leader_headers):
    creada = await client.post(
        "/api/invitations/",
        json={"email": _unique_email("leader-crea-3"), "role": "DEVELOPER"},
        headers=leader_headers,
    )
    invitation_id = creada.json()["id"]

    res = await client.post(f"/api/invitations/{invitation_id}/resend", headers=admin_headers)
    assert res.status_code == 200, res.text[:300]


async def test_developer_no_puede_listar_ni_reenviar_invitaciones(client, dev_headers):
    res = await client.get("/api/invitations/pending", headers=dev_headers)
    assert res.status_code == 403

    res = await client.post(
        f"/api/invitations/{uuid.uuid4()}/resend", headers=dev_headers
    )
    assert res.status_code == 403
