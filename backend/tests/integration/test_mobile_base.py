"""BFF oficial móvil adaptado al backend compartido de septiembre."""
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_dashboard_roles(client, admin_headers, leader_headers, dev_headers, ticket):
    for headers, role in ((admin_headers, "ADMIN"), (leader_headers, "TEAM_LEADER"),
                          (dev_headers, "DEVELOPER")):
        res = await client.get("/api/mobile/dashboard", headers=headers)
        assert res.status_code == 200, res.text[:200]
        assert res.json()["role"] == role


async def test_mobile_board_and_detail(client, admin_headers, dev_headers, application, ticket):
    board = await client.get(f"/api/mobile/applications/{application['id']}/board", headers=admin_headers)
    assert board.status_code == 200, board.text[:200]
    assert board.json()["epics"][0]["tickets"][0]["id"] == ticket["id"]
    detail = await client.get(f"/api/mobile/tickets/{ticket['id']}/detail", headers=dev_headers)
    assert detail.status_code == 200, detail.text[:200]
    assert detail.json()["assignee"]["role"] == "DEVELOPER"
    assert detail.json()["permissions"]["can_start"]


async def test_mobile_timer_uses_persisted_start(client, dev_headers, ticket):
    started = await client.post(f"/api/tickets/{ticket['id']}/start", headers=dev_headers)
    assert started.status_code == 200, started.text[:200]
    detail = await client.get(f"/api/mobile/tickets/{ticket['id']}/detail", headers=dev_headers)
    assert detail.status_code == 200, detail.text[:200]
    timer = detail.json()["timer"]
    assert timer["is_running"] and timer["started_at"] is not None
    assert detail.json()["events"]


async def test_workload_leader_and_developer(client, leader_headers, dev_headers, ticket):
    res = await client.get("/api/mobile/team/workload", headers=leader_headers)
    assert res.status_code == 200, res.text[:200]
    assert any(member["active_tickets"] > 0 for member in res.json())
    denied = await client.get("/api/mobile/team/workload", headers=dev_headers)
    assert denied.status_code == 403


async def test_mobile_preferences_persist(client, dev_headers):
    res = await client.put("/api/devices/preferences", json={"push_enabled": False}, headers=dev_headers)
    assert res.status_code == 200, res.text[:200]
    saved = await client.get("/api/devices/preferences", headers=dev_headers)
    assert saved.json()["push_enabled"] is False


async def test_device_owner_is_database_user(client, dev_headers, dev2_headers):
    device = await client.post("/api/devices/", json={"fcm_token": "integration-only", "platform": "ANDROID"}, headers=dev_headers)
    assert device.status_code == 201, device.text[:200]
    device_id = device.json()["id"]
    denied = await client.delete(f"/api/devices/{device_id}", headers=dev2_headers)
    assert denied.status_code == 403
    removed = await client.delete(f"/api/devices/{device_id}", headers=dev_headers)
    assert removed.status_code == 204


async def test_mobile_endpoints_need_login(client):
    res = await client.get("/api/mobile/dashboard")
    assert res.status_code in (401, 403)
