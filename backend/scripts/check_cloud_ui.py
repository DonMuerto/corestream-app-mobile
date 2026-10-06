"""Verifica un ticket temporal creado MANUALMENTE desde Flutter y el socket.

No crea tickets ni imprime credenciales. --cleanup solo puede borrar un ticket
con el prefijo de prueba en la aplicación de verificación, después de validarlo.
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env.vercel.local", override=True)
load_dotenv(BACKEND / ".env.cloud.admin.local", override=True)


async def main(args):
    from sqlalchemy import select
    from app.database import dispose_engine, get_session_maker
    from app.models import Application, Epic, Ticket

    base = "https://corestream-app-base-grupo1.vercel.app/api"
    async with httpx.AsyncClient(base_url=base, timeout=35) as client:
        login = await client.post("/auth/login", json={
            "email": os.environ["CLOUD_ADMIN_EMAIL"],
            "password": os.environ["CLOUD_ADMIN_PASSWORD"],
        })
        assert login.status_code == 200, f"Login HTTP {login.status_code}"
        client.headers["Authorization"] = "Bearer " + login.json()["access_token"]
        try:
            if args.title:
                assert args.title.startswith("Prueba Flutter UI "), "Prefijo de prueba obligatorio"
                async with get_session_maker()() as db:
                    rows = (await db.execute(select(Ticket).join(Epic).join(Application).where(
                        Ticket.title == args.title,
                        Application.name == "Verificación técnica Grupo 1",
                    ))).scalars().all()
                    assert len(rows) == 1, f"Se esperaba un ticket de prueba, encontrados {len(rows)}"
                    saved = rows[0]
                    ticket_id = saved.id
                    assert saved.priority.value == "MEDIUM" and saved.assignee_id is None
                    assert saved.status.value == "TODO"
                detail = await client.get(f"/mobile/tickets/{ticket_id}/detail")
                assert detail.status_code == 200, f"Detalle HTTP {detail.status_code}"
                assert detail.json()["ticket"]["title"] == args.title
                print("Ticket creado desde Flutter -> PostgreSQL -> detalle BFF: OK")
                if args.cleanup:
                    removed = await client.delete(f"/tickets/{ticket_id}")
                    assert removed.status_code == 204, f"Cleanup HTTP {removed.status_code}"
                    async with get_session_maker()() as db:
                        assert await db.get(Ticket, ticket_id) is None
                    print("Solo el ticket temporal de UI fue eliminado de API y PostgreSQL: OK")
            if args.websocket:
                import websockets
                from app.redis_client import (TICKETS_UPDATES_CHANNEL, close_redis,
                                              init_redis, publish_message)
                me = await client.get("/auth/me")
                assert me.status_code == 200
                host = "corestream-app-api-grupo1"
                ticket = await client.post("/auth/ws-ticket")
                assert ticket.status_code == 200
                url = f"wss://{host}.vercel.app/api/ws/{me.json()['id']}?ticket={ticket.json()['ticket']}"
                async with websockets.connect(url, open_timeout=15) as ws:
                    data = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                    assert data.get("type") == "connected"
                    print("WebSocket API directa: conectado con ticket de un uso")
                    # PUT de prioridad no publica un cambio de estado en el
                    # backend oficial. Probar el transporte no equivale a
                    # afirmar que toda mutación o los jobs ARQ entregan push.
                    await init_redis()
                    try:
                        await publish_message(TICKETS_UPDATES_CHANNEL,
                                              {"type": "BASE_CONNECTION_CHECK", "verification": True})
                        event = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                        assert event.get("type") == "update"
                        assert event.get("data", {}).get("verification") is True
                        print("Sonda de transporte Redis pub/sub -> WebSocket: OK (no prueba de jobs ARQ)")
                    finally:
                        await close_redis()
        finally:
            await client.post("/auth/logout", json={})
    await dispose_engine()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--websocket", action="store_true")
    args = parser.parse_args()
    if args.cleanup and not args.title:
        parser.error("--cleanup requiere --title")
    try:
        asyncio.run(main(args))
    except Exception as exc:
        message = str(exc) if isinstance(exc, AssertionError) else type(exc).__name__
        print("Verificación incompleta: " + message)
        raise SystemExit(1) from None
