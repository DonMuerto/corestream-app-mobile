"""
Self-service password reset flow.

SMTP isn't configured in the test environment, so send_password_reset_email
is a noop — the reset link is captured by patching it, the same way a real
client would get it from their inbox.
"""

from unittest.mock import AsyncMock, patch

import pytest

from .conftest import DEV

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _extract_token(reset_url: str) -> str:
    return reset_url.rsplit("/", 1)[-1]


async def _request_reset(client, email: str) -> str | None:
    with patch("app.routers.auth.send_password_reset_email", new=AsyncMock(return_value=True)) as mocked:
        res = await client.post("/api/auth/password-reset/request", json={"email": email})
        assert res.status_code == 200
        if not mocked.await_args:
            return None
        return _extract_token(mocked.await_args.kwargs["reset_url"])


async def test_pide_reset_y_confirma_con_password_nueva(client):
    token = await _request_reset(client, DEV["email"])
    assert token

    nueva = "ClaveDeReset123!@#"
    res = await client.post(
        "/api/auth/password-reset/confirm", json={"token": token, "new_password": nueva}
    )
    assert res.status_code == 200

    client.cookies.clear()
    assert (
        await client.post("/api/auth/login", json={"email": DEV["email"], "password": nueva})
    ).status_code == 200

    # Restore so other tests relying on DEV's original password keep working.
    tokens = (
        await client.post("/api/auth/login", json={"email": DEV["email"], "password": nueva})
    ).json()
    await client.post(
        "/api/auth/change-password",
        json={"old_password": nueva, "new_password": DEV["password"]},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )


async def test_pedir_reset_para_correo_inexistente_no_revela_nada(client):
    """Same 200 response whether or not the account exists — avoids enumerating emails."""
    res = await client.post(
        "/api/auth/password-reset/request", json={"email": "nadie@corestream-tests.com"}
    )
    assert res.status_code == 200


async def test_token_de_reset_es_de_un_solo_uso(client):
    token = await _request_reset(client, DEV["email"])
    assert token

    primera = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token, "new_password": "PrimerCambio123!@#"},
    )
    assert primera.status_code == 200

    segunda = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token, "new_password": "SegundoCambio123!@#"},
    )
    assert segunda.status_code == 410

    # Restore DEV's password for other tests.
    client.cookies.clear()
    tokens = (
        await client.post(
            "/api/auth/login", json={"email": DEV["email"], "password": "PrimerCambio123!@#"}
        )
    ).json()
    await client.post(
        "/api/auth/change-password",
        json={"old_password": "PrimerCambio123!@#", "new_password": DEV["password"]},
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )


async def test_token_de_reset_invalido_da_404(client):
    res = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": "token-que-no-existe", "new_password": "ClaveValida123!@#"},
    )
    assert res.status_code == 404


async def test_password_reset_valida_longitud_minima(client):
    token = await _request_reset(client, DEV["email"])
    assert token

    res = await client.post(
        "/api/auth/password-reset/confirm", json={"token": token, "new_password": "corta"}
    )
    assert res.status_code == 422
