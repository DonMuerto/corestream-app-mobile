"""
Pagination and count on GET /users/ — the frontend fix for TeamView's
member table silently truncating at 20 rows (limit's default) depends on
these behaving correctly: skip/limit for the table's pages, /count for the
stat cards (which must not depend on which page is currently shown).
"""

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_list_users_respects_limit(client, admin_headers):
    res = await client.get("/api/users/", params={"limit": 1}, headers=admin_headers)
    assert res.status_code == 200
    assert len(res.json()) <= 1


async def test_list_users_skip_moves_the_window(client, admin_headers):
    primera = await client.get("/api/users/", params={"skip": 0, "limit": 1}, headers=admin_headers)
    segunda = await client.get("/api/users/", params={"skip": 1, "limit": 1}, headers=admin_headers)
    assert primera.status_code == 200
    assert segunda.status_code == 200
    if primera.json() and segunda.json():
        assert primera.json()[0]["id"] != segunda.json()[0]["id"]


async def test_count_no_depende_de_la_pagina_actual(client, admin_headers):
    """
    El total de /count debe cubrir a todos los usuarios activos, no solo a
    los que trae la página pedida a /users/ (con limit=1 estarían en las
    antípodas si compartieran la misma consulta).
    """
    pagina = await client.get("/api/users/", params={"limit": 1}, headers=admin_headers)
    conteo = await client.get("/api/users/count", headers=admin_headers)

    assert pagina.status_code == 200
    assert conteo.status_code == 200
    body = conteo.json()
    assert body["total"] >= len(pagina.json())
    assert body["total"] == sum(body["by_role"].values())


async def test_count_accesible_para_team_leader(client, leader_headers):
    res = await client.get("/api/users/count", headers=leader_headers)
    assert res.status_code == 200


async def test_count_prohibido_para_developer(client, dev_headers):
    res = await client.get("/api/users/count", headers=dev_headers)
    assert res.status_code == 403
